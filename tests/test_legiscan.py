from unittest.mock import patch, MagicMock
import pytest
from services.legiscan import fetch_master_list, _extract_committee, _fetch_bill

def _mock_response(payload):
    m = MagicMock()
    m.json.return_value = payload
    m.raise_for_status = MagicMock()
    return m

def test_extract_committee_found():
    history = [{"action": "First reading"}, {"action": "Referred to Judiciary Committee"}]
    assert _extract_committee(history) == "Judiciary Committee"

def test_extract_committee_uses_most_recent():
    history = [
        {"action": "Referred to Agriculture Committee"},
        {"action": "Re-referred to Judiciary Committee"},
    ]
    assert _extract_committee(history) == "Judiciary Committee"

def test_extract_committee_none():
    assert _extract_committee([]) is None
    assert _extract_committee([{"action": "passed"}]) is None

def test_fetch_master_list_returns_stubs():
    payload = {
        "masterlist": {
            "session": {"session_id": 1},
            "1": {"bill_id": 1, "number": "HB 100", "last_action_date": "2025-01-01"},
            "2": {"bill_id": 2, "number": "SB 200", "last_action_date": "2025-01-02"},
        }
    }
    with patch("services.legiscan.requests.get", return_value=_mock_response(payload)):
        stubs = fetch_master_list()
    assert len(stubs) == 2
    assert stubs[0]["number"] == "HB 100"

def test_fetch_master_list_raises_on_missing_key():
    with patch("services.legiscan.requests.get", return_value=_mock_response({"status": "ERROR"})):
        with pytest.raises(ValueError, match="No masterlist"):
            fetch_master_list()

def test_fetch_bill_returns_none_on_missing_key():
    with patch("services.legiscan.requests.get", return_value=_mock_response({"status": "ERROR"})):
        assert _fetch_bill("999", "testkey", retries=1) is None

def test_fetch_bill_returns_bill_dict():
    payload = {"bill": {"bill_id": 1, "number": "HB 100", "sponsors": [], "history": []}}
    with patch("services.legiscan.requests.get", return_value=_mock_response(payload)):
        result = _fetch_bill("1", "testkey", retries=1)
    assert result["number"] == "HB 100"
