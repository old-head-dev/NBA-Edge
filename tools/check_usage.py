import requests
import os

API_KEY = os.environ.get("SGO_API_KEY", "")
if not API_KEY:
    print("Set SGO_API_KEY environment variable first")
    exit(1)

r = requests.get(
    "https://api.sportsgameodds.com/v2/account/usage/",
    headers={"X-Api-Key": API_KEY},
    timeout=10
)
print(f"Status: {r.status_code}")
print(r.json())
