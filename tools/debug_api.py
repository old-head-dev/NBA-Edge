#!/usr/bin/env python3
"""
Quick debug script — prints the first few events from a historical snapshot
so we can see the exact data structure and commence_time format.
"""
import os
import requests

API_KEY  = os.environ.get("ODDS_API_KEY", "")
BASE_URL = "https://api.the-odds-api.com/v4"

if not API_KEY:
    print("ERROR: set $env:ODDS_API_KEY first")
    exit()

# Pull snapshot for Nov 2, 2025 (day after our first game Nov 1)
snapshot = "2025-11-02T12:00:00Z"

r = requests.get(
    f"{BASE_URL}/historical/sports/basketball_nba/odds",
    params={
        "apiKey":     API_KEY,
        "regions":    "us",
        "markets":    "spreads",
        "oddsFormat": "american",
        "date":       snapshot,
    },
    timeout=20
)

print(f"Status: {r.status_code}")
print(f"Quota used={r.headers.get('x-requests-used')}  remaining={r.headers.get('x-requests-remaining')}")

data = r.json()
events = data.get("data", [])
print(f"Total events in snapshot: {len(events)}")
print(f"Snapshot timestamp: {data.get('timestamp')}")
print()

print("First 5 events (team names + commence_time + scores):")
for ev in events[:5]:
    print(f"  {ev.get('away_team')} @ {ev.get('home_team')}")
    print(f"    commence_time: {ev.get('commence_time')}")
    print(f"    scores: {ev.get('scores')}")
    print()
