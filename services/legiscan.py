import json
import logging
import os
import re
import time
from typing import Optional

import requests

import database

logger = logging.getLogger(__name__)
BASE_URL = "https://api.legiscan.com/"


def _get_api_key() -> str:
    return os.environ["LEGISCAN_API_KEY"]


def fetch_master_list() -> list:
    """Call LegiScan getMasterList for IL; return list of bill stubs."""
    resp = requests.get(
        BASE_URL, params={"key": _get_api_key(), "op": "getMasterList", "state": "IL"}
    )
    resp.raise_for_status()
    data = resp.json()
    if "masterlist" not in data:
        raise ValueError("No masterlist in LegiScan response")
    return [v for v in data["masterlist"].values() if "bill_id" in v]


def _extract_committee(history: list) -> Optional[str]:
    """Scan history in reverse; return most recent committee name or None."""
    patterns = [
        r"referred to (.+?) committee",
        r"assigned to (.+?) committee",
        r"to (.+?) committee",
    ]
    for event in reversed(history):
        action = event.get("action", "").lower()
        for pattern in patterns:
            match = re.search(pattern, action)
            if match:
                return match.group(1).strip().title() + " Committee"
    return None


def _fetch_bill(bill_id: str, api_key: str, retries: int = 3) -> Optional[dict]:
    """Fetch one bill from LegiScan; returns bill dict or None on failure."""
    for attempt in range(retries):
        try:
            resp = requests.get(
                BASE_URL, params={"key": api_key, "op": "getBill", "id": bill_id}
            )
            resp.raise_for_status()
            data = resp.json()
            if "bill" not in data:
                return None
            return data["bill"]
        except requests.exceptions.RequestException as e:
            if attempt < retries - 1:
                time.sleep(3)
            else:
                logger.error("Failed bill %s after %d attempts: %s", bill_id, retries, e)
    return None


def _update_job_progress(job_id: int, fetched: int, updated: int) -> None:
    with database.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE fetch_jobs SET bills_fetched=%s, bills_updated=%s WHERE id=%s",
                (fetched, updated, job_id),
            )


def sync_bills(stubs: list, job_id: int) -> None:
    """
    Upsert all bills from stubs into the DB.
    Re-fetches from LegiScan only when last_action_date has changed.
    Updates fetch_jobs progress row as it goes.
    """
    try:
        api_key = _get_api_key()
        total = len(stubs)

        with database.get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE fetch_jobs SET status='running', started_at=now(), total_bills=%s WHERE id=%s",
                    (total, job_id),
                )

        fetched = updated = 0

        for stub in stubs:
            bill_id = str(stub.get("bill_id"))
            last_action_date = stub.get("last_action_date", "")

            with database.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT last_action_date FROM bills WHERE bill_id = %s", (bill_id,)
                    )
                    cached = cur.fetchone()

            if cached and cached[0] == last_action_date:
                fetched += 1
                if fetched % 50 == 0:
                    _update_job_progress(job_id, fetched, updated)
                continue

            full_bill = _fetch_bill(bill_id, api_key)
            if not full_bill:
                logger.warning("Skipping bill %s: fetch returned None", bill_id)
                fetched += 1
                if fetched % 50 == 0:
                    _update_job_progress(job_id, fetched, updated)
                continue

            sponsors = "; ".join(
                s["name"]
                for s in full_bill.get("sponsors", [])
                if isinstance(s, dict) and "name" in s
            )
            number = stub.get("number", "")
            if number.startswith("H"):
                chamber = "House"
            elif number.startswith("S"):
                chamber = "Senate"
            else:
                chamber = "Unknown"

            with database.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO bills
                           (bill_id, number, title, description, status, chamber,
                            committee, sponsors, last_action, last_action_date, raw_json, fetched_at)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())
                           ON CONFLICT (bill_id) DO UPDATE SET
                             title=EXCLUDED.title, description=EXCLUDED.description,
                             status=EXCLUDED.status, chamber=EXCLUDED.chamber,
                             committee=EXCLUDED.committee, sponsors=EXCLUDED.sponsors,
                             last_action=EXCLUDED.last_action,
                             last_action_date=EXCLUDED.last_action_date,
                             raw_json=EXCLUDED.raw_json, fetched_at=now()""",
                        (
                            bill_id, number,
                            stub.get("title", ""),
                            stub.get("description", "").replace("\n", " "),
                            str(stub.get("status", "")),
                            chamber,
                            _extract_committee(full_bill.get("history", [])) or "",
                            sponsors,
                            stub.get("last_action", "").replace("\n", " "),
                            last_action_date,
                            json.dumps(full_bill),
                        ),
                    )

            fetched += 1
            updated += 1
            if fetched % 50 == 0:
                _update_job_progress(job_id, fetched, updated)

        # Final progress update
        _update_job_progress(job_id, fetched, updated)

        with database.get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE fetch_jobs SET status='done', finished_at=now() WHERE id=%s",
                    (job_id,),
                )
    except Exception as e:
        logger.error("sync_bills job %s failed: %s", job_id, e)
        try:
            with database.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE fetch_jobs SET status='failed', finished_at=now(), error_msg=%s WHERE id=%s",
                        (str(e), job_id),
                    )
        except Exception:
            logger.exception("Failed to mark job %s as failed", job_id)
