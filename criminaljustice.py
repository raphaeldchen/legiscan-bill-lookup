# python3 criminaljustice.py "C:\Users\rapha\Box\LegiScan\Legislative Tracking\criminal_justice"

import requests
import csv
import argparse
import os
import json
import pandas as pd
import logging
import time
import re

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

print('Retrieving directory path...')
parser = argparse.ArgumentParser()
parser.add_argument('folder_path', type=str, help='Path to the file')
args = parser.parse_args()

def get_path(file_name, start_dir='/'):
    for root, dirs, files in os.walk(start_dir):
        if file_name in files or file_name in dirs:
            return os.path.join(root, file_name)
    return None

folder = args.folder_path
if folder is None:
    raise FileNotFoundError("Could not find directory.")

def load_key(json_path):
    with open(json_path) as f:
        data = json.load(f)
    return data["API_KEY"]
API_KEY = load_key(get_path('key.json', start_dir=folder))
BASE_URL = "https://api.legiscan.com/?key=" + API_KEY

cache_file = os.path.join(folder, "bill_cache.json")
if os.path.exists(cache_file):
    with open(cache_file, "r", encoding="utf-8") as f:
        bill_cache = json.load(f)
else:
    bill_cache = {}

params = {
    "op": "getMasterList",
    "state": "IL"
}
logging.info('Requesting master bill list...')
response = requests.get(BASE_URL, params=params)

if response.status_code != 200:
    logging.error(f"Error fetching master list: {response.status_code}, {response.text}")
    exit(1)

data = response.json()
if "masterlist" not in data:
    logging.error("No bills found in response.")
    exit(1)

bills = list(data["masterlist"].values())[1:]
csv_filename = "illinois_legislation.csv"
file_path = os.path.join(folder, csv_filename)
csv_columns = ['bill_id', 'number', 'title', 'description', 'status', 'chamber', 'committee', 'sponsors', 'last_action', 'last_action_date']

def extract_committees(history):
    patterns = [
        r'referred to (.+?) committee',
        r'assigned to (.+?) committee',
        r'to (.+?) committee'
    ]

    for event in reversed(history):
        action = event.get("action", "").lower()
        for pattern in patterns:
            match = re.search(pattern, action)
            if match:
                name = match.group(1).strip().title() + " Committee"
                return name
    return None

logging.info('Writing CSV...')
with open(file_path, mode="w", newline="", encoding="utf-8") as file:
    writer = csv.writer(file)
    writer.writerow(csv_columns)

    count = 0
    for bill in bills:
        count += 1
        if (count == 1000000000):
            break
        bill_id = str(bill.get('bill_id'))
        last_action_date = bill.get('last_action_date')

        use_cached = (
            bill_id in bill_cache and
            bill_cache[bill_id].get("last_action_date") == last_action_date
        )
        success = False

        if use_cached:
            logging.info(f"Using cached data for bill {bill.get('number')}.")
            full_bill = bill_cache[bill_id]
            success = True
        else:
            retries = 3
            while retries > 0 and not success:
                try:
                    url = f"https://api.legiscan.com/?key={API_KEY}&op=getBill&id={bill_id}"
                    res = requests.get(url).json()
                    if "bill" not in res:
                        logging.warning(f"[WARN] No bill found for ID {bill_id}")
                        break
                    full_bill = res["bill"]
                    full_bill["last_action_date"] = last_action_date
                    bill_cache[bill_id] = full_bill
                    success = True
                    logging.info(f"Successfully fetched data for bill {bill.get('number')}.")
                except Exception as e:
                    retries -= 1
                    logging.error(f"Failed to fetch bill {bill_id} (attempt {4 - retries}): {e}")
                    if retries > 0:
                        logging.info(f"Retrying in 3 seconds... (remaining retries: {retries})")
                        time.sleep(3)
                    else:
                        logging.error(f"All retries failed for bill {bill_id}. Skipping.")

        if success:
            sponsors = [s["name"] for s in full_bill.get("sponsors", []) if isinstance(s, dict) and "name" in s]
            sponsors_str = "; ".join(sponsors) if sponsors else ""
            committees_str = extract_committees(full_bill.get("history", [])) or ""
            bill_number = bill.get('number', '')
            if bill_number.startswith('H'):
                chamber = "House"
            elif bill_number.startswith('S'):
                chamber = "Senate"
            else:
                chamber = "Unknown"

            writer.writerow([
                bill_id,
                bill.get('number'),
                bill.get('title'),
                bill.get('description', '').replace('\n', ' '),
                bill.get('status'),
                chamber,
                committees_str,
                sponsors_str,
                bill.get('last_action', '').replace('\n', ' '),
                last_action_date
            ])

with open(cache_file, "w", encoding="utf-8") as f:
    json.dump(bill_cache, f, indent=2)

logging.info(f"Data saved to {csv_filename}")

logging.info('Filtering to criminal justice bills...')
df = pd.read_csv(file_path)

def filter(string):
    string = str(string).lower()
    keywords = [
        'incarcerated', 'criminal', 'code of corrections', 'juvenile court',
        'firearm', 'gun', 'crime', 'law enforcement', 'police', 'prisoner',
        'justice', 'offender', 'judiciary', 'judicial', 'misdemeanor',
        'felony', 'trust act', 'immigration'
    ]
    return any(keyword in string for keyword in keywords)

df['filter?'] = df['description'].apply(filter)
filtered_df = df[df['filter?']]
copy = filtered_df.drop(columns=['filter?'])
filtered_csv = 'criminal_justice.csv'
filtered_path = os.path.join(folder, filtered_csv)
copy.to_csv(filtered_path, index=False)
logging.info(f'Filtered bills saved to {filtered_csv}')