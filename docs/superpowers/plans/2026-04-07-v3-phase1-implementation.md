# NBA Edge V3 Phase 1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a data pipeline that loads 6 seasons (2018-19, 2021-22 through 2024-25) of NBA game data with closing lines, computes schedule context (B2B, travel, distance, sleep, density, altitude), and runs a direction-agnostic signal analysis across the full signal matrix — producing a per-season audit report with Wilson CIs that answers whether any fatigue-based schedule condition provides a consistent betting edge. Excludes 2019-20 (COVID bubble) and 2020-21 (shortened/abnormal schedule).

**Architecture:** Python data pipeline. Three stages: (1) load/merge free datasets into normalized DataFrames, (2) compute schedule context for every game, (3) run signal analysis per season with validation. No composite scores, no pre-assumed bet directions, no threshold mining.

**Tech Stack:** Python 3.10+, pandas, scipy (Wilson CI), math (Haversine). No external ML libraries in Phase 1. pytest for tests.

**Spec:** `docs/superpowers/specs/2026-04-07-v3-fresh-start-design.md`

---

## File Structure

```
backtest/v3/
├── arenas.py              # Arena coordinates, Haversine distance, timezone offsets, team name normalization
├── load_data.py           # Parse Kaggle CSV + SBR JSON into unified DataFrames
├── validate_data.py       # Spot-check data quality, cross-reference sources, generate quality report
├── schedule.py            # Compute B2B, traveled, distance, sleep estimate, density, altitude, win%
├── signals.py             # Wilson CI, signal condition definitions, per-season split computation
├── analyze.py             # Run full signal matrix across all seasons, generate audit report
├── validate_signals.py    # Leave-one-season-out cross-validation, monotonicity checks
├── pipeline.py            # Orchestrator: load → validate → schedule → analyze → validate_signals
├── data/
│   ├── raw/               # Downloaded datasets — gitignored
│   │   ├── kaggle_nba_betting.csv
│   │   └── sbr_archive_10y.json
│   └── processed/         # Output CSVs + reports — gitignored
│       ├── full_season_YYYY_YY.csv  (one per season)
│       ├── signal_audit_report.txt
│       └── validation_report.txt
└── tests/
    ├── test_arenas.py
    ├── test_schedule.py
    └── test_signals.py
```

**Responsibilities:**
- `arenas.py` — Pure math/data. No I/O. Contains all 30 NBA arena coordinates, Haversine formula, UTC offset lookup, and team abbreviation normalization (handles historical name changes like NJN→BKN, NOH→NOP, SEA→OKC, CHA/CHH→CHA).
- `load_data.py` — File I/O only. Reads raw CSV/JSON, normalizes column names and team abbreviations, computes ATS/OU results from scores+spreads, returns clean DataFrames. No business logic.
- `validate_data.py` — Quality assurance. Spot-checks scores against expectations, cross-references Kaggle vs SBR for overlapping seasons, logs discrepancies.
- `schedule.py` — Core computation. Takes a season DataFrame sorted by date, walks through each team's games chronologically, computes all schedule context fields. This is the engine that replaces V2's fatigue scoring.
- `signals.py` — Analysis primitives. Wilson CI function, signal condition filter functions (one per signal ID), ATS/OU split computation. No I/O.
- `analyze.py` — Orchestrates signal analysis. Loops signal matrix × seasons × segments (full/pre-ASB/post-ASB), applies tanking filter to post-ASB, generates the audit report.
- `validate_signals.py` — Statistical validation. Leave-one-season-out CV, monotonicity via Spearman correlation. Only runs on signals that pass Stage 2.
- `pipeline.py` — CLI entry point. Wires stages together, handles file paths, prints progress.

---

### Task 1: Project scaffolding and arena module

**Files:**
- Create: `backtest/v3/arenas.py`
- Create: `backtest/v3/tests/test_arenas.py`
- Modify: `backtest/.gitignore` (add v3/data/)

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p backtest/v3/data/raw backtest/v3/data/processed backtest/v3/tests
```

- [ ] **Step 2: Add gitignore for v3 data**

Add to `backtest/.gitignore`:
```
v3/data/raw/
v3/data/processed/
```

- [ ] **Step 3: Write test_arenas.py**

```python
"""Tests for arena data, Haversine distance, and team name normalization."""
import pytest
from v3.arenas import haversine_miles, normalize_team, get_tz_offset, ARENAS

def test_haversine_known_distance():
    # BOS to LAL ≈ 2611 miles (well-known)
    dist = haversine_miles(42.3662, -71.0621, 34.0430, -118.2673)
    assert 2550 < dist < 2650, f"BOS-LAL should be ~2611mi, got {dist}"

def test_haversine_same_point():
    dist = haversine_miles(40.0, -74.0, 40.0, -74.0)
    assert dist == 0.0

def test_haversine_lal_lac():
    # Same city, short distance
    dist = haversine_miles(34.0430, -118.2673, 33.8958, -118.3386)
    assert dist < 15, f"LAL-LAC should be <15mi, got {dist}"

def test_all_30_teams_present():
    assert len(ARENAS) == 30

def test_normalize_modern_abbrevs():
    assert normalize_team("BOS") == "BOS"
    assert normalize_team("LAL") == "LAL"
    assert normalize_team("GSW") == "GSW"

def test_normalize_historical_names():
    assert normalize_team("NJN") == "BKN"   # NJ Nets → Brooklyn Nets (2012)
    assert normalize_team("SEA") == "OKC"   # Seattle → OKC (2008)
    assert normalize_team("NOH") == "NOP"   # New Orleans Hornets → Pelicans
    assert normalize_team("NOK") == "NOP"   # NO/OKC Hornets (Katrina)
    assert normalize_team("CHH") == "CHA"   # Charlotte Hornets (original)
    assert normalize_team("CHO") == "CHA"   # Charlotte (alternate)
    assert normalize_team("VAN") == "MEM"   # Vancouver Grizzlies → Memphis

def test_normalize_is_case_insensitive():
    assert normalize_team("bos") == "BOS"
    assert normalize_team("Bos") == "BOS"

def test_get_tz_offset():
    assert get_tz_offset("BOS") == -5
    assert get_tz_offset("LAL") == -8
    assert get_tz_offset("DEN") == -7
    assert get_tz_offset("CHI") == -6

def test_travel_distance_via_arenas():
    bos = ARENAS["BOS"]
    cle = ARENAS["CLE"]
    dist = haversine_miles(bos["lat"], bos["lon"], cle["lat"], cle["lon"])
    assert 550 < dist < 650, f"BOS-CLE should be ~554mi, got {dist}"
```

- [ ] **Step 4: Run tests — expect FAIL (module doesn't exist yet)**

```bash
cd backtest && python -m pytest v3/tests/test_arenas.py -v
```
Expected: `ModuleNotFoundError`

- [ ] **Step 5: Write arenas.py**

```python
"""NBA arena coordinates, distances, timezones, and team name normalization."""
import math

ARENAS = {
    "ATL": {"city": "Atlanta",        "lat": 33.7573, "lon": -84.3963, "tz": -5},
    "BOS": {"city": "Boston",         "lat": 42.3662, "lon": -71.0621, "tz": -5},
    "BKN": {"city": "Brooklyn",       "lat": 40.6826, "lon": -73.9754, "tz": -5},
    "CHA": {"city": "Charlotte",      "lat": 35.2251, "lon": -80.8392, "tz": -5},
    "CHI": {"city": "Chicago",        "lat": 41.8807, "lon": -87.6742, "tz": -6},
    "CLE": {"city": "Cleveland",      "lat": 41.4965, "lon": -81.6882, "tz": -5},
    "DAL": {"city": "Dallas",         "lat": 32.7905, "lon": -96.8103, "tz": -6},
    "DEN": {"city": "Denver",         "lat": 39.7487, "lon": -105.0077, "tz": -7},
    "DET": {"city": "Detroit",        "lat": 42.3410, "lon": -83.0552, "tz": -5},
    "GSW": {"city": "San Francisco",  "lat": 37.7680, "lon": -122.3877, "tz": -8},
    "HOU": {"city": "Houston",        "lat": 29.7508, "lon": -95.3621, "tz": -6},
    "IND": {"city": "Indianapolis",   "lat": 39.7640, "lon": -86.1555, "tz": -5},
    "LAC": {"city": "Los Angeles",    "lat": 33.8958, "lon": -118.3386, "tz": -8},
    "LAL": {"city": "Los Angeles",    "lat": 34.0430, "lon": -118.2673, "tz": -8},
    "MEM": {"city": "Memphis",        "lat": 35.1383, "lon": -90.0505, "tz": -6},
    "MIA": {"city": "Miami",          "lat": 25.7814, "lon": -80.1870, "tz": -5},
    "MIL": {"city": "Milwaukee",      "lat": 43.0450, "lon": -87.9170, "tz": -6},
    "MIN": {"city": "Minneapolis",    "lat": 44.9795, "lon": -93.2762, "tz": -6},
    "NOP": {"city": "New Orleans",    "lat": 29.9490, "lon": -90.0812, "tz": -6},
    "NYK": {"city": "New York",       "lat": 40.7505, "lon": -73.9934, "tz": -5},
    "OKC": {"city": "Oklahoma City",  "lat": 35.4634, "lon": -97.5151, "tz": -6},
    "ORL": {"city": "Orlando",        "lat": 28.5392, "lon": -81.3839, "tz": -5},
    "PHI": {"city": "Philadelphia",   "lat": 39.9012, "lon": -75.1720, "tz": -5},
    "PHX": {"city": "Phoenix",        "lat": 33.4457, "lon": -112.0712, "tz": -7},
    "POR": {"city": "Portland",       "lat": 45.5316, "lon": -122.6668, "tz": -8},
    "SAC": {"city": "Sacramento",     "lat": 38.5802, "lon": -121.4997, "tz": -8},
    "SAS": {"city": "San Antonio",    "lat": 29.4270, "lon": -98.4375, "tz": -6},
    "TOR": {"city": "Toronto",        "lat": 43.6435, "lon": -79.3791, "tz": -5},
    "UTA": {"city": "Salt Lake City", "lat": 40.7683, "lon": -111.9011, "tz": -7},
    "WAS": {"city": "Washington DC",  "lat": 38.8981, "lon": -77.0209, "tz": -5},
}

ALTITUDE_ARENAS = {"DEN", "UTA"}

# Historical team abbreviation → current abbreviation
_TEAM_ALIASES = {
    "NJN": "BKN",   # New Jersey Nets → Brooklyn (2012)
    "SEA": "OKC",   # Seattle SuperSonics → OKC (2008)
    "NOH": "NOP",   # New Orleans Hornets → Pelicans (2013)
    "NOK": "NOP",   # NO/OKC Hornets (Katrina era, 2005-07)
    "CHH": "CHA",   # Charlotte Hornets (original, pre-2002 → Bobcats → Hornets again)
    "CHO": "CHA",   # Charlotte alternate abbreviation
    "CHP": "CHA",   # Charlotte alternate
    "VAN": "MEM",   # Vancouver Grizzlies → Memphis (2001)
    "GOS": "GSW",   # Golden State alternate
    "PHO": "PHX",   # Phoenix alternate (used in some datasets)
    "SA":  "SAS",   # San Antonio alternate
    "NY":  "NYK",   # New York alternate
    "NO":  "NOP",   # New Orleans alternate
    "GS":  "GSW",   # Golden State alternate
    "WSH": "WAS",   # Washington alternate
    "BRK": "BKN",   # Brooklyn alternate
    "UTH": "UTA",   # Utah alternate
}


def normalize_team(abbr: str) -> str:
    """Normalize a team abbreviation to the current 3-letter code."""
    upper = abbr.strip().upper()
    return _TEAM_ALIASES.get(upper, upper)


def get_tz_offset(team: str) -> int:
    """Get standard UTC offset for a team's arena (non-DST)."""
    return ARENAS[normalize_team(team)]["tz"]


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in miles between two lat/lon points."""
    R = 3959  # Earth radius in miles
    lat1, lon1, lat2, lon2 = (math.radians(x) for x in [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def travel_distance(from_team: str, to_team: str) -> float:
    """Distance in miles between two teams' arenas."""
    a = ARENAS[normalize_team(from_team)]
    b = ARENAS[normalize_team(to_team)]
    return haversine_miles(a["lat"], a["lon"], b["lat"], b["lon"])
```

- [ ] **Step 6: Create `backtest/v3/__init__.py` and `backtest/v3/tests/__init__.py`**

Both files empty (needed for pytest discovery).

- [ ] **Step 7: Run tests — expect PASS**

```bash
cd backtest && python -m pytest v3/tests/test_arenas.py -v
```
Expected: All tests pass.

- [ ] **Step 8: Commit**

```bash
git add backtest/v3/ backtest/.gitignore
git commit -m "feat(v3): project scaffolding and arena module with Haversine, team normalization"
```

---

### Task 2: Download datasets and inspect schemas

**Files:**
- Create: `backtest/v3/inspect_data.py` (temporary utility — can delete after inspection)

This task requires user action (downloading from Kaggle). The inspect script helps confirm the exact column names before writing the loader.

- [ ] **Step 1: Download the Kaggle dataset**

User action — go to https://www.kaggle.com/datasets/cviaxmiwnptr/nba-betting-data-october-2007-to-june-2024, download the ZIP, extract the CSV to `backtest/v3/data/raw/kaggle_nba_betting.csv`.

- [ ] **Step 2: Download the SBR GitHub data file**

Download ONLY the data file (not the repo):
```bash
curl -L "https://raw.githubusercontent.com/flancast90/sportsbookreview-scraper/main/data/nba_archive_10Y.json" -o backtest/v3/data/raw/sbr_archive_10y.json
```

Do NOT clone the repo. Do NOT run any Python code from it. We only want the pre-scraped JSON data file.

- [ ] **Step 3: Write and run inspect_data.py**

```python
"""Inspect downloaded datasets to confirm column names and data shape."""
import csv
import json
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "raw")

def inspect_kaggle():
    path = os.path.join(DATA_DIR, "kaggle_nba_betting.csv")
    if not os.path.exists(path):
        print(f"KAGGLE: File not found at {path}")
        return
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        print(f"KAGGLE: {len(headers)} columns")
        print(f"  Columns: {headers}")
        rows = list(reader)
        print(f"  Total rows: {len(rows)}")
        print(f"  First row: {rows[0]}")
        print(f"  Last row: {rows[-1]}")
        # Count seasons
        seasons = set()
        for r in rows:
            for key in headers:
                if "season" in key.lower():
                    seasons.add(r[key])
                    break
        if seasons:
            print(f"  Seasons: {sorted(seasons)}")

def inspect_sbr():
    path = os.path.join(DATA_DIR, "sbr_archive_10y.json")
    if not os.path.exists(path):
        print(f"SBR: File not found at {path}")
        return
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        print(f"SBR: {len(data)} records (list)")
        print(f"  Keys: {list(data[0].keys())}")
        print(f"  First record: {data[0]}")
        print(f"  Last record: {data[-1]}")
    elif isinstance(data, dict):
        print(f"SBR: dict with keys {list(data.keys())[:10]}")

if __name__ == "__main__":
    inspect_kaggle()
    print()
    inspect_sbr()
```

```bash
cd backtest/v3 && python inspect_data.py
```

- [ ] **Step 4: Record the actual column names**

Update the loader code in Task 3 if column names differ from assumptions. The key fields we need from Kaggle: date, away team, home team, away score, home score, spread, total, season identifier, regular/playoff flag. From SBR: date, teams, scores, close_spread, close_over_under, open_spread, open_over_under.

- [ ] **Step 5: Commit**

```bash
git add backtest/v3/inspect_data.py
git commit -m "feat(v3): data inspection script — confirms Kaggle and SBR schemas"
```

---

### Task 3: Data loading pipeline

**Files:**
- Create: `backtest/v3/load_data.py`
- Create: `backtest/v3/tests/test_load_data.py`

**Important:** The exact column names below are based on the Kaggle dataset description. After running Task 2's inspection, update the column mappings if they differ.

- [ ] **Step 1: Write test_load_data.py**

```python
"""Tests for data loading and normalization."""
import pytest
import pandas as pd
from v3.load_data import compute_ats_result, compute_ou_result, normalize_game_row

def test_ats_home_covers():
    # Home favored by 5 (-5 spread), home wins by 10 → home covers
    assert compute_ats_result(home_score=110, away_score=100, home_spread=-5.0) == "home"

def test_ats_away_covers():
    # Home favored by 5 (-5 spread), home wins by 3 → away covers
    assert compute_ats_result(home_score=103, away_score=100, home_spread=-5.0) == "away"

def test_ats_push():
    # Home favored by 5 (-5 spread), home wins by 5 → push
    assert compute_ats_result(home_score=105, away_score=100, home_spread=-5.0) == "push"

def test_ats_away_favored():
    # Away favored (home spread is +3), away wins by 10 → away covers
    assert compute_ats_result(home_score=90, away_score=100, home_spread=3.0) == "away"

def test_ats_none_spread():
    # Missing spread → None
    assert compute_ats_result(home_score=100, away_score=95, home_spread=None) is None

def test_ou_over():
    assert compute_ou_result(home_score=115, away_score=110, total=220.0) == "over"

def test_ou_under():
    assert compute_ou_result(home_score=100, away_score=95, total=200.0) == "under"

def test_ou_push():
    assert compute_ou_result(home_score=110, away_score=110, total=220.0) == "push"

def test_ou_none_total():
    assert compute_ou_result(home_score=110, away_score=110, total=None) is None

def test_normalize_game_row_team_names():
    row = {"away": "NJN", "home": "SEA", "away_score": 100, "home_score": 95}
    result = normalize_game_row(row)
    assert result["away"] == "BKN"
    assert result["home"] == "OKC"
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd backtest && python -m pytest v3/tests/test_load_data.py -v
```

- [ ] **Step 3: Write load_data.py**

```python
"""Load and normalize NBA game data from Kaggle CSV and SBR JSON."""
import csv
import json
import os
from typing import Optional
import pandas as pd
from v3.arenas import normalize_team

DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "raw")


def compute_ats_result(home_score: int, away_score: int, home_spread: Optional[float]) -> Optional[str]:
    """Determine ATS result. home_spread is from the home team's perspective (negative = favored)."""
    if home_spread is None:
        return None
    adjusted = home_score + home_spread
    if adjusted > away_score:
        return "home"
    elif adjusted < away_score:
        return "away"
    return "push"


def compute_ou_result(home_score: int, away_score: int, total: Optional[float]) -> Optional[str]:
    """Determine over/under result."""
    if total is None:
        return None
    game_total = home_score + away_score
    if game_total > total:
        return "over"
    elif game_total < total:
        return "under"
    return "push"


def normalize_game_row(row: dict) -> dict:
    """Normalize team abbreviations in a game row."""
    row["away"] = normalize_team(row["away"])
    row["home"] = normalize_team(row["home"])
    return row


def _safe_float(val) -> Optional[float]:
    """Convert to float, return None for empty/invalid."""
    if val is None or val == "" or val == "NaN":
        return None
    try:
        f = float(val)
        if pd.isna(f):
            return None
        return f
    except (ValueError, TypeError):
        return None


def _safe_int(val) -> Optional[int]:
    """Convert to int, return None for empty/invalid."""
    f = _safe_float(val)
    return int(f) if f is not None else None


def load_kaggle(filename: str = "kaggle_nba_betting.csv") -> pd.DataFrame:
    """Load Kaggle NBA Betting Data CSV into a normalized DataFrame.

    Column mapping must be verified against actual data in Task 2.
    Update the column name mappings below if the actual headers differ.
    """
    path = os.path.join(DATA_DIR, filename)
    df = pd.read_csv(path, encoding="utf-8")

    # --- COLUMN MAPPING (verify after Task 2 inspection) ---
    # These are best-guess names from the dataset description.
    # After running inspect_data.py, update if actual names differ.
    col_map = {
        "date": "date",
        "away_team": "away",  # Adjust key to actual column name
        "home_team": "home",  # Adjust key to actual column name
        "away_score": "away_score",  # Adjust key to actual column name
        "home_score": "home_score",  # Adjust key to actual column name
        "spread": "home_spread",
        "total": "close_total",
        "season": "season",
    }

    # Rename columns to our standard names
    rename = {}
    for src, dst in col_map.items():
        if src in df.columns and src != dst:
            rename[src] = dst
    df = df.rename(columns=rename)

    # Normalize team names
    df["away"] = df["away"].apply(normalize_team)
    df["home"] = df["home"].apply(normalize_team)

    # Filter regular season only (check actual column name for this flag)
    if "is_regular" in df.columns:
        df = df[df["is_regular"] == True].copy()
    elif "type" in df.columns:
        df = df[df["type"].str.lower() == "regular"].copy()

    # Ensure numeric types
    df["away_score"] = df["away_score"].apply(_safe_int)
    df["home_score"] = df["home_score"].apply(_safe_int)
    df["home_spread"] = df["home_spread"].apply(_safe_float)
    df["close_total"] = df["close_total"].apply(_safe_float)

    # Compute ATS and O/U results
    df["ats_result"] = df.apply(
        lambda r: compute_ats_result(r["home_score"], r["away_score"], r["home_spread"]),
        axis=1,
    )
    df["ou_result"] = df.apply(
        lambda r: compute_ou_result(r["home_score"], r["away_score"], r["close_total"]),
        axis=1,
    )

    # Parse date
    df["date"] = pd.to_datetime(df["date"])

    # Add source tag
    df["source"] = "kaggle"

    return df.sort_values("date").reset_index(drop=True)


def load_sbr(filename: str = "sbr_archive_10y.json") -> pd.DataFrame:
    """Load SBR pre-scraped JSON into a normalized DataFrame.

    Column mapping must be verified against actual data in Task 2.
    """
    path = os.path.join(DATA_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        records = json.load(f)

    rows = []
    for rec in records:
        row = {
            "date": rec.get("date"),
            "away": normalize_team(rec.get("away_team", "")),
            "home": normalize_team(rec.get("home_team", "")),
            "away_score": _safe_int(rec.get("away_score")),
            "home_score": _safe_int(rec.get("home_score")),
            "home_spread": _safe_float(rec.get("home_close_spread")),
            "close_total": _safe_float(rec.get("close_over_under")),
            "open_spread": _safe_float(rec.get("home_open_spread")),
            "open_total": _safe_float(rec.get("open_over_under")),
            "source": "sbr",
        }
        row["ats_result"] = compute_ats_result(row["away_score"], row["home_score"], row["home_spread"])
        row["ou_result"] = compute_ou_result(row["away_score"], row["home_score"], row["close_total"])
        rows.append(row)

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
cd backtest && python -m pytest v3/tests/test_load_data.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backtest/v3/load_data.py backtest/v3/tests/test_load_data.py
git commit -m "feat(v3): data loader for Kaggle CSV and SBR JSON with ATS/OU computation"
```

---

### Task 4: Data validation and quality checks

**Files:**
- Create: `backtest/v3/validate_data.py`

- [ ] **Step 1: Write validate_data.py**

```python
"""Validate data quality: spot-check scores, cross-reference sources, log issues."""
import pandas as pd


def spot_check_game(df: pd.DataFrame, date: str, away: str, home: str,
                    expected_away_score: int, expected_home_score: int) -> dict:
    """Check a specific game against expected scores. Returns dict with pass/fail and details."""
    mask = (df["date"].dt.strftime("%Y-%m-%d") == date) & (df["away"] == away) & (df["home"] == home)
    matches = df[mask]
    if len(matches) == 0:
        return {"pass": False, "error": "game not found", "date": date, "away": away, "home": home}
    row = matches.iloc[0]
    score_ok = row["away_score"] == expected_away_score and row["home_score"] == expected_home_score
    return {
        "pass": score_ok,
        "date": date, "away": away, "home": home,
        "expected": f"{expected_away_score}-{expected_home_score}",
        "actual": f"{row['away_score']}-{row['home_score']}",
        "spread": row.get("home_spread"),
        "total": row.get("close_total"),
    }


def cross_reference(kaggle_df: pd.DataFrame, sbr_df: pd.DataFrame) -> pd.DataFrame:
    """Cross-reference Kaggle and SBR data for overlapping games.
    Returns DataFrame of discrepancies."""
    # Merge on date + teams
    kaggle_df = kaggle_df.copy()
    sbr_df = sbr_df.copy()
    kaggle_df["date_str"] = kaggle_df["date"].dt.strftime("%Y-%m-%d")
    sbr_df["date_str"] = sbr_df["date"].dt.strftime("%Y-%m-%d")

    merged = kaggle_df.merge(
        sbr_df, on=["date_str", "away", "home"], suffixes=("_kg", "_sbr"), how="inner"
    )

    discrepancies = []
    for _, row in merged.iterrows():
        issues = []
        if row["away_score_kg"] != row["away_score_sbr"]:
            issues.append(f"away_score: kg={row['away_score_kg']} sbr={row['away_score_sbr']}")
        if row["home_score_kg"] != row["home_score_sbr"]:
            issues.append(f"home_score: kg={row['home_score_kg']} sbr={row['home_score_sbr']}")
        if row["home_spread_kg"] is not None and row["home_spread_sbr"] is not None:
            if abs(row["home_spread_kg"] - row["home_spread_sbr"]) > 0.5:
                issues.append(f"spread: kg={row['home_spread_kg']} sbr={row['home_spread_sbr']}")
        if issues:
            discrepancies.append({
                "date": row["date_str"], "away": row["away"], "home": row["home"],
                "issues": "; ".join(issues)
            })

    print(f"Cross-reference: {len(merged)} matching games, {len(discrepancies)} discrepancies")
    return pd.DataFrame(discrepancies)


def quality_report(df: pd.DataFrame, label: str) -> str:
    """Generate a text quality report for a dataset."""
    lines = [f"=== Quality Report: {label} ==="]
    lines.append(f"Total games: {len(df)}")
    lines.append(f"Date range: {df['date'].min()} to {df['date'].max()}")
    lines.append(f"Unique teams: {sorted(df['away'].unique().tolist())}")
    lines.append(f"Missing spreads: {df['home_spread'].isna().sum()} ({df['home_spread'].isna().mean()*100:.1f}%)")
    lines.append(f"Missing totals: {df['close_total'].isna().sum()} ({df['close_total'].isna().mean()*100:.1f}%)")
    lines.append(f"Missing scores: {df['away_score'].isna().sum()}")

    # Games per season (approximate by year)
    df_copy = df.copy()
    df_copy["year"] = df_copy["date"].dt.year
    lines.append(f"\nGames per year:")
    for year, count in df_copy.groupby("year").size().items():
        lines.append(f"  {year}: {count}")

    return "\n".join(lines)
```

- [ ] **Step 2: Commit**

```bash
git add backtest/v3/validate_data.py
git commit -m "feat(v3): data validation — spot checks, cross-reference, quality reports"
```

---

### Task 5: Schedule context engine

**Files:**
- Create: `backtest/v3/schedule.py`
- Create: `backtest/v3/tests/test_schedule.py`

- [ ] **Step 1: Write test_schedule.py**

```python
"""Tests for schedule context computation."""
import pytest
import pandas as pd
from v3.schedule import compute_schedule_context

def _make_games(game_list):
    """Helper: create a DataFrame from a list of (date, away, home, away_score, home_score) tuples."""
    rows = []
    for g in game_list:
        rows.append({
            "date": pd.Timestamp(g[0]),
            "away": g[1], "home": g[2],
            "away_score": g[3], "home_score": g[4],
            "home_spread": -5.0, "close_total": 220.0,
            "ats_result": "home", "ou_result": "under",
        })
    return pd.DataFrame(rows)

def test_b2b_detection():
    # BOS plays 2024-11-01 and 2024-11-02 (back-to-back)
    games = _make_games([
        ("2024-11-01", "BOS", "NYK", 100, 95),
        ("2024-11-02", "BOS", "BKN", 105, 98),  # BOS away B2B
        ("2024-11-04", "BOS", "MIA", 110, 100),  # 1 day rest
    ])
    result = compute_schedule_context(games)
    # Game 0: first game, no B2B
    assert result.loc[0, "away_b2b"] == False
    # Game 1: BOS played yesterday → away_b2b = True
    assert result.loc[1, "away_b2b"] == True
    # Game 2: BOS had 1 day rest → not B2B
    assert result.loc[2, "away_b2b"] == False

def test_home_b2b():
    # CLE plays at home 11-01, then at home 11-02
    games = _make_games([
        ("2024-11-01", "ATL", "CLE", 90, 100),
        ("2024-11-02", "CHI", "CLE", 95, 105),  # CLE home B2B
    ])
    result = compute_schedule_context(games)
    assert result.loc[1, "home_b2b"] == True
    assert result.loc[1, "home_traveled"] == False  # Home-home, no travel

def test_traveled_flag():
    # BOS plays at NYK (away), then at BKN (away) — traveled
    games = _make_games([
        ("2024-11-01", "BOS", "NYK", 100, 95),
        ("2024-11-02", "BOS", "BKN", 105, 98),
    ])
    result = compute_schedule_context(games)
    assert result.loc[1, "away_traveled"] == True
    assert result.loc[1, "away_travel_dist"] > 0  # NYK to BKN ≈ 8 miles

def test_home_traveled():
    # CLE plays at BOS (away) on 11-01, then hosts ATL on 11-02
    games = _make_games([
        ("2024-11-01", "CLE", "BOS", 100, 95),
        ("2024-11-02", "ATL", "CLE", 90, 105),  # CLE home, but played away yesterday
    ])
    result = compute_schedule_context(games)
    assert result.loc[1, "home_b2b"] == True
    assert result.loc[1, "home_traveled"] == True  # Was in BOS yesterday
    assert result.loc[1, "home_travel_dist"] > 500  # BOS to CLE ≈ 554 miles

def test_days_rest():
    games = _make_games([
        ("2024-11-01", "BOS", "NYK", 100, 95),
        ("2024-11-04", "BOS", "MIA", 110, 100),  # 2 days rest
    ])
    result = compute_schedule_context(games)
    assert result.loc[1, "away_days_rest"] == 2

def test_sleep_estimate_short_trip():
    # BOS at NYK (8 miles), tip ~7:30pm → should get good sleep
    games = _make_games([
        ("2024-11-01", "BOS", "NYK", 100, 95),
        ("2024-11-02", "BOS", "BKN", 105, 98),
    ])
    result = compute_schedule_context(games)
    # Short trip, default tip → ~7.5 hrs sleep
    est_sleep = result.loc[1, "away_est_sleep"]
    assert est_sleep is not None
    assert est_sleep > 5  # Short trip should yield decent sleep
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd backtest && python -m pytest v3/tests/test_schedule.py -v
```

- [ ] **Step 3: Write schedule.py**

```python
"""Compute schedule context for every game in a season.

For each team in each game, computes: days_rest, b2b flag, traveled flag,
travel_distance, estimated_sleep, tz_change, schedule density (3in4, 4in6),
altitude flag, and season win% at game time.
"""
import pandas as pd
from v3.arenas import ARENAS, ALTITUDE_ARENAS, haversine_miles, normalize_team, get_tz_offset

DEFAULT_TIP_HOUR_ET = 19.5  # 7:30pm ET default when tip time unknown


def _get_tip_hour_et(row) -> float:
    """Extract tip time in ET hours from a game row. Returns default if unavailable."""
    # If the dataset has a datetime with time, use it. Otherwise default.
    if hasattr(row["date"], "hour") and row["date"].hour > 0:
        return row["date"].hour + row["date"].minute / 60.0
    return DEFAULT_TIP_HOUR_ET


def _estimate_sleep(prev_arena: str, curr_arena: str, prev_tip_et: float) -> float:
    """Estimate sleep hours for a traveling B2B team.

    Formula (from spec):
    - Game ends = tip + 2.5 hrs
    - Post-game departure = game end + 2.5 hrs (= tip + 5.0)
    - Flight time = distance / 500 mph
    - Hotel arrival = landing + 0.75 hrs
    - Wake-up = 10am local (34.0 on 24hr ET scale for ET teams, adjusted for TZ)
    - Sleep = max(0, wake-up - arrival)
    """
    prev = ARENAS.get(prev_arena)
    curr = ARENAS.get(curr_arena)
    if not prev or not curr:
        return None

    dist = haversine_miles(prev["lat"], prev["lon"], curr["lat"], curr["lon"])
    flight_hrs = dist / 500.0

    # All times in ET-equivalent hours (24hr scale, can exceed 24 = next day)
    departure_et = prev_tip_et + 5.0  # tip + 2.5 (game) + 2.5 (post-game)
    landing_et = departure_et + flight_hrs
    hotel_arrival_et = landing_et + 0.75

    # Wake-up at 10am LOCAL time of game venue, converted to ET
    tz_diff = curr["tz"] - (-5)  # Diff from ET (ET = -5)
    wakeup_et = 10.0 - tz_diff + 24.0  # +24 to ensure next day

    sleep = max(0.0, wakeup_et - hotel_arrival_et)
    # Cap at reasonable max (can't sleep more than ~12 hrs)
    sleep = min(sleep, 12.0)
    return round(sleep, 1)


def _estimate_sleep_home_home(prev_tip_et: float, home_team: str) -> float:
    """Sleep estimate for home-home B2B (sleep at home both nights).
    Bed time ≈ tip + 5.0 hrs. Wake-up ≈ 10am local."""
    bed_time = prev_tip_et + 5.0
    # Wake-up at 10am LOCAL time, converted to ET scale
    tz_diff = ARENAS[home_team]["tz"] - (-5)  # Diff from ET
    wakeup_et = 10.0 - tz_diff + 24.0  # 10am local on next-day ET scale
    sleep = max(0.0, wakeup_et - bed_time)
    return round(min(sleep, 12.0), 1)


def compute_schedule_context(games_df: pd.DataFrame) -> pd.DataFrame:
    """Add schedule context columns to a season's game DataFrame.

    Input: DataFrame with date, away, home, away_score, home_score (sorted by date).
    Output: Same DataFrame with added columns for both away and home teams.
    """
    df = games_df.copy().sort_values("date").reset_index(drop=True)

    # Track each team's game history: list of (date, arena, tip_hour_et, opponent, is_home)
    team_history = {}

    # Initialize output columns
    for prefix in ["away", "home"]:
        df[f"{prefix}_days_rest"] = None
        df[f"{prefix}_b2b"] = False
        df[f"{prefix}_traveled"] = False
        df[f"{prefix}_travel_dist"] = 0.0
        df[f"{prefix}_est_sleep"] = None
        df[f"{prefix}_tz_change"] = 0
        df[f"{prefix}_3in4"] = False
        df[f"{prefix}_4in6"] = False
        df[f"{prefix}_at_altitude"] = False
    df["home_is_altitude"] = False

    # Track wins/losses for win% computation
    team_records = {}  # team → {"wins": int, "losses": int}

    for idx, row in df.iterrows():
        away = row["away"]
        home = row["home"]
        game_date = row["date"]
        home_arena = home  # Home team plays at their own arena
        tip_et = _get_tip_hour_et(row)

        # Mark altitude arenas
        df.at[idx, "home_is_altitude"] = home in ALTITUDE_ARENAS

        for team, prefix, is_home in [(away, "away", False), (home, "home", True)]:
            arena = home_arena  # Game is at home team's arena
            prev_games = team_history.get(team, [])

            # Win% at game time
            rec = team_records.get(team, {"wins": 0, "losses": 0})
            total_games = rec["wins"] + rec["losses"]
            df.at[idx, f"{prefix}_win_pct"] = rec["wins"] / total_games if total_games > 0 else 0.5

            if prev_games:
                last = prev_games[-1]
                days_rest = (game_date - last["date"]).days - 1  # 0 = B2B
                df.at[idx, f"{prefix}_days_rest"] = days_rest

                is_b2b = days_rest == 0
                df.at[idx, f"{prefix}_b2b"] = is_b2b

                # Traveled = previous game was at a different arena
                prev_arena = last["arena"]
                traveled = prev_arena != arena
                df.at[idx, f"{prefix}_traveled"] = traveled

                if traveled:
                    dist = haversine_miles(
                        ARENAS[prev_arena]["lat"], ARENAS[prev_arena]["lon"],
                        ARENAS[arena]["lat"], ARENAS[arena]["lon"],
                    )
                    df.at[idx, f"{prefix}_travel_dist"] = round(dist, 0)

                    # Timezone change
                    tz_from = ARENAS[prev_arena]["tz"]
                    tz_to = ARENAS[arena]["tz"]
                    df.at[idx, f"{prefix}_tz_change"] = tz_to - tz_from

                # Sleep estimation (only for B2B)
                if is_b2b:
                    if traveled:
                        sleep = _estimate_sleep(prev_arena, arena, last["tip_et"])
                        df.at[idx, f"{prefix}_est_sleep"] = sleep
                    elif is_home and not traveled:
                        # Home-home B2B
                        sleep = _estimate_sleep_home_home(last["tip_et"], team)
                        df.at[idx, f"{prefix}_est_sleep"] = sleep

                # Altitude: visiting team at DEN/UTA, no recent altitude game
                if not is_home and home in ALTITUDE_ARENAS:
                    recent_altitude = any(
                        pg["arena"] in ALTITUDE_ARENAS
                        for pg in prev_games[-4:]
                        if (game_date - pg["date"]).days <= 4
                    )
                    df.at[idx, f"{prefix}_at_altitude"] = not recent_altitude

                # Schedule density
                if len(prev_games) >= 2:
                    games_in_4_days = sum(
                        1 for pg in prev_games
                        if 0 <= (game_date - pg["date"]).days <= 3
                    ) + 1  # +1 for current game
                    df.at[idx, f"{prefix}_3in4"] = games_in_4_days >= 3

                if len(prev_games) >= 3:
                    games_in_6_days = sum(
                        1 for pg in prev_games
                        if 0 <= (game_date - pg["date"]).days <= 5
                    ) + 1
                    df.at[idx, f"{prefix}_4in6"] = games_in_6_days >= 4

            # Update history
            if team not in team_history:
                team_history[team] = []
            team_history[team].append({
                "date": game_date,
                "arena": arena,
                "tip_et": tip_et,
                "is_home": is_home,
            })

            # Update record after the game
            if team not in team_records:
                team_records[team] = {"wins": 0, "losses": 0}
            if row["away_score"] is not None and row["home_score"] is not None:
                if is_home:
                    if row["home_score"] > row["away_score"]:
                        team_records[team]["wins"] += 1
                    else:
                        team_records[team]["losses"] += 1
                else:
                    if row["away_score"] > row["home_score"]:
                        team_records[team]["wins"] += 1
                    else:
                        team_records[team]["losses"] += 1

    return df
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
cd backtest && python -m pytest v3/tests/test_schedule.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backtest/v3/schedule.py backtest/v3/tests/test_schedule.py
git commit -m "feat(v3): schedule context engine — B2B, travel, distance, sleep, density, altitude, win%"
```

---

### Task 6: Signal analysis engine

**Files:**
- Create: `backtest/v3/signals.py`
- Create: `backtest/v3/analyze.py`
- Create: `backtest/v3/tests/test_signals.py`

- [ ] **Step 1: Write test_signals.py**

```python
"""Tests for Wilson CI and signal condition filters."""
import pytest
import pandas as pd
from v3.signals import wilson_ci, compute_split, SIGNAL_CONDITIONS

def test_wilson_ci_basic():
    lo, hi = wilson_ci(60, 100)
    assert 0.50 < lo < 0.55
    assert 0.65 < hi < 0.70

def test_wilson_ci_zero():
    lo, hi = wilson_ci(0, 0)
    assert lo == 0.0
    assert hi == 0.0

def test_wilson_ci_perfect():
    lo, hi = wilson_ci(10, 10)
    assert hi == 1.0

def test_compute_split_basic():
    results = ["home", "home", "away", "push", "home"]
    split = compute_split(results)
    assert split["home_wins"] == 3
    assert split["away_wins"] == 1
    assert split["pushes"] == 1
    assert split["total"] == 4  # pushes excluded from total
    assert abs(split["home_pct"] - 75.0) < 0.1
    assert abs(split["away_pct"] - 25.0) < 0.1

def test_compute_split_all_none():
    results = [None, None]
    split = compute_split(results)
    assert split["total"] == 0

def test_all_signal_conditions_defined():
    # Verify all signal IDs from spec exist
    expected = ["S1", "S2", "S3", "S4", "S5", "S6", "B1", "B2", "D1", "D2", "A1", "C1"]
    for sig_id in expected:
        assert sig_id in SIGNAL_CONDITIONS, f"Missing signal {sig_id}"

def test_signal_s1_filter():
    """S1: Home on B2B, away NOT on B2B."""
    row = pd.Series({"home_b2b": True, "away_b2b": False})
    assert SIGNAL_CONDITIONS["S1"]["filter"](row) == True

    row2 = pd.Series({"home_b2b": True, "away_b2b": True})
    assert SIGNAL_CONDITIONS["S1"]["filter"](row2) == False  # Both B2B → excluded

    row3 = pd.Series({"home_b2b": False, "away_b2b": False})
    assert SIGNAL_CONDITIONS["S1"]["filter"](row3) == False  # Home not B2B

def test_signal_c1_filter():
    """C1: Neither team on B2B (control)."""
    row = pd.Series({"home_b2b": False, "away_b2b": False})
    assert SIGNAL_CONDITIONS["C1"]["filter"](row) == True

    row2 = pd.Series({"home_b2b": True, "away_b2b": False})
    assert SIGNAL_CONDITIONS["C1"]["filter"](row2) == False
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd backtest && python -m pytest v3/tests/test_signals.py -v
```

- [ ] **Step 3: Write signals.py**

```python
"""Signal condition definitions, Wilson CI, and ATS/OU split computation."""
import math
from typing import Optional


def wilson_ci(wins: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score 95% confidence interval for a binomial proportion.
    Returns (lower, upper) bounds as fractions [0, 1]."""
    if total == 0:
        return 0.0, 0.0
    p = wins / total
    denom = 1 + z**2 / total
    centre = (p + z**2 / (2 * total)) / denom
    spread = z * math.sqrt((p * (1 - p) + z**2 / (4 * total)) / total) / denom
    return max(0.0, centre - spread), min(1.0, centre + spread)


def compute_split(results: list) -> dict:
    """Compute ATS or O/U split from a list of result strings.

    For ATS: results are 'home', 'away', 'push', or None.
    For O/U: results are 'over', 'under', 'push', or None.
    Pushes excluded from denominator per spec.
    """
    valid = [r for r in results if r is not None and r != "push"]
    pushes = sum(1 for r in results if r == "push")
    total = len(valid)

    if total == 0:
        return {"home_wins": 0, "away_wins": 0, "pushes": pushes, "total": 0,
                "home_pct": 0.0, "away_pct": 0.0, "home_ci": (0, 0), "away_ci": (0, 0)}

    # For ATS: count home/away. For O/U: count over (as "home_wins") / under (as "away_wins")
    side_a = sum(1 for r in valid if r in ("home", "over"))
    side_b = sum(1 for r in valid if r in ("away", "under"))

    return {
        "home_wins": side_a, "away_wins": side_b,
        "pushes": pushes, "total": total,
        "home_pct": side_a / total * 100,
        "away_pct": side_b / total * 100,
        "home_ci": wilson_ci(side_a, total),
        "away_ci": wilson_ci(side_b, total),
    }


# --- Signal Condition Definitions ---
# Each signal is a dict with:
#   "id": signal ID from spec
#   "name": human-readable description
#   "filter": function(row) -> bool, where row is a pandas Series with schedule context columns

SIGNAL_CONDITIONS = {
    "S1": {
        "name": "Home on B2B, away NOT on B2B",
        "filter": lambda r: bool(r["home_b2b"]) and not bool(r["away_b2b"]),
    },
    "S2": {
        "name": "Home on B2B + traveled, away NOT on B2B",
        "filter": lambda r: bool(r["home_b2b"]) and bool(r["home_traveled"]) and not bool(r["away_b2b"]),
    },
    "S3": {
        "name": "Home on B2B + long travel (>1000mi), away NOT on B2B",
        "filter": lambda r: (bool(r["home_b2b"]) and bool(r["home_traveled"])
                             and r["home_travel_dist"] >= 1000 and not bool(r["away_b2b"])),
    },
    "S4": {
        "name": "Away on B2B, home NOT on B2B",
        "filter": lambda r: bool(r["away_b2b"]) and not bool(r["home_b2b"]),
    },
    "S5": {
        "name": "Away on B2B + traveled, home NOT on B2B",
        "filter": lambda r: bool(r["away_b2b"]) and bool(r["away_traveled"]) and not bool(r["home_b2b"]),
    },
    "S6": {
        "name": "Away on B2B + long travel (>1000mi), home NOT on B2B",
        "filter": lambda r: (bool(r["away_b2b"]) and bool(r["away_traveled"])
                             and r["away_travel_dist"] >= 1000 and not bool(r["home_b2b"])),
    },
    "B1": {
        "name": "Both B2B, only road team traveled (home had home-home B2B)",
        "filter": lambda r: (bool(r["away_b2b"]) and bool(r["home_b2b"])
                             and not bool(r["home_traveled"])),
    },
    "B2": {
        "name": "Both B2B, both teams traveled (home also played away yesterday)",
        "filter": lambda r: (bool(r["away_b2b"]) and bool(r["home_b2b"])
                             and bool(r["home_traveled"])),
    },
    "D1": {
        "name": "Home on 3-in-4 or 4-in-6",
        "filter": lambda r: bool(r["home_3in4"]) or bool(r["home_4in6"]),
    },
    "D2": {
        "name": "Away on 3-in-4 or 4-in-6",
        "filter": lambda r: bool(r["away_3in4"]) or bool(r["away_4in6"]),
    },
    "A1": {
        "name": "Visitor at DEN/UTA on B2B with travel",
        "filter": lambda r: (bool(r["away_b2b"]) and bool(r["away_traveled"])
                             and bool(r["away_at_altitude"])),
    },
    "C1": {
        "name": "Neither team on B2B (control)",
        "filter": lambda r: not bool(r["away_b2b"]) and not bool(r["home_b2b"]),
    },
}
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
cd backtest && python -m pytest v3/tests/test_signals.py -v
```

- [ ] **Step 5: Write analyze.py**

```python
"""Run full signal matrix across all seasons, generate audit report."""
import os
import pandas as pd
from v3.signals import SIGNAL_CONDITIONS, compute_split

ALL_STAR_BREAK_DATES = {
    "2007-08": "2008-02-17", "2008-09": "2009-02-15", "2009-10": "2010-02-14",
    "2010-11": "2011-02-20", "2011-12": "2012-02-26", "2012-13": "2013-02-17",
    "2013-14": "2014-02-16", "2014-15": "2015-02-15", "2015-16": "2016-02-14",
    "2016-17": "2017-02-19", "2017-18": "2018-02-18", "2018-19": "2019-02-17",
    "2019-20": "2020-02-16", "2020-21": "2021-03-07", "2021-22": "2022-02-20",
    "2022-23": "2023-02-19", "2023-24": "2024-02-18", "2024-25": "2025-02-16",
}


def assign_season(date) -> str:
    """Convert a game date to season label (e.g., '2024-25')."""
    if date.month >= 10:
        return f"{date.year}-{str(date.year + 1)[2:]}"
    return f"{date.year - 1}-{str(date.year)[2:]}"


def run_signal_analysis(all_games: pd.DataFrame, output_path: str):
    """Run the full signal matrix and generate the audit report."""
    all_games = all_games.copy()
    all_games["season"] = all_games["date"].apply(assign_season)
    seasons = sorted(all_games["season"].unique())

    lines = []
    lines.append("=" * 70)
    lines.append("  NBA EDGE V3 — SIGNAL AUDIT REPORT")
    lines.append("  Direction-agnostic analysis. No pre-assumed bets.")
    lines.append("  Generated from free historical datasets.")
    lines.append("=" * 70)
    lines.append(f"\nSeasons: {len(seasons)} ({seasons[0]} to {seasons[-1]})")
    lines.append(f"Total games: {len(all_games)}")

    for sig_id, sig in SIGNAL_CONDITIONS.items():
        lines.append(f"\n{'='*70}")
        lines.append(f"  SIGNAL {sig_id}: {sig['name']}")
        lines.append(f"{'='*70}")

        # Full season analysis
        lines.append("\n--- Full Season ---")
        _analyze_segment(all_games, seasons, sig, lines, "full")

        # Pre/Post ASB (only for non-control signals)
        if sig_id != "C1":
            lines.append("\n--- Pre-All-Star Break ---")
            _analyze_segment(all_games, seasons, sig, lines, "pre_asb")

            lines.append("\n--- Post-All-Star Break ---")
            _analyze_segment(all_games, seasons, sig, lines, "post_asb")

            # Post-ASB with tanking filter (using win% at ASB, not at game time)
            for threshold in [0.250, 0.300, 0.350]:
                lines.append(f"\n--- Post-ASB, exclude teams <{threshold:.3f} win% ---")
                _analyze_segment(all_games, seasons, sig, lines, "post_asb",
                                 tank_threshold=threshold)

    report = "\n".join(lines)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Report written to {output_path}")
    return report


def _analyze_segment(all_games, seasons, sig, lines, segment, tank_threshold=None):
    """Analyze a signal across all seasons for a given segment."""
    season_results_ats = {}
    season_results_ou = {}

    for season in seasons:
        season_df = all_games[all_games["season"] == season].copy()

        # Apply segment filter
        if segment == "pre_asb" and season in ALL_STAR_BREAK_DATES:
            asb = pd.Timestamp(ALL_STAR_BREAK_DATES[season])
            season_df = season_df[season_df["date"] < asb]
        elif segment == "post_asb" and season in ALL_STAR_BREAK_DATES:
            asb = pd.Timestamp(ALL_STAR_BREAK_DATES[season])
            season_df = season_df[season_df["date"] >= asb]

        # Apply tanking filter (exclude games involving low-win% teams, post-ASB only)
        if tank_threshold is not None:
            season_df = season_df[
                (season_df["away_win_pct"] >= tank_threshold) &
                (season_df["home_win_pct"] >= tank_threshold)
            ]

        # Apply signal filter
        mask = season_df.apply(sig["filter"], axis=1)
        matched = season_df[mask]
        n = len(matched)

        if n == 0:
            season_results_ats[season] = None
            season_results_ou[season] = None
            continue

        ats_split = compute_split(matched["ats_result"].tolist())
        ou_split = compute_split(matched["ou_result"].tolist())
        season_results_ats[season] = ats_split
        season_results_ou[season] = ou_split

    # Print per-season results
    lines.append(f"\n  {'Season':<10} {'N':>4}  {'Home ATS':>10}  {'Away ATS':>10}  {'Over':>10}  {'Under':>10}")
    lines.append(f"  {'-'*10} {'-'*4}  {'-'*10}  {'-'*10}  {'-'*10}  {'-'*10}")

    for season in seasons:
        ats = season_results_ats.get(season)
        ou = season_results_ou.get(season)
        if ats is None:
            lines.append(f"  {season:<10} {'0':>4}  {'--':>10}  {'--':>10}  {'--':>10}  {'--':>10}")
            continue
        lines.append(
            f"  {season:<10} {ats['total']:>4}  "
            f"{ats['home_pct']:>9.1f}%  {ats['away_pct']:>9.1f}%  "
            f"{ou['home_pct']:>9.1f}%  {ou['away_pct']:>9.1f}%"
        )

    # Combined summary with CIs
    all_ats = [r for r in season_results_ats.values() if r is not None]
    if all_ats:
        total_home = sum(r["home_wins"] for r in all_ats)
        total_away = sum(r["away_wins"] for r in all_ats)
        total_n = sum(r["total"] for r in all_ats)
        total_over = sum(r["home_wins"] for r in [season_results_ou[s] for s in seasons if season_results_ou.get(s)])
        total_under = sum(r["away_wins"] for r in [season_results_ou[s] for s in seasons if season_results_ou.get(s)])
        total_ou_n = sum(r["total"] for r in [season_results_ou[s] for s in seasons if season_results_ou.get(s)])

        from v3.signals import wilson_ci
        ats_home_ci = wilson_ci(total_home, total_n)
        ats_away_ci = wilson_ci(total_away, total_n)

        lines.append(f"\n  COMBINED: Home {total_home}W/{total_n} = {total_home/total_n*100:.1f}% "
                     f"[CI: {ats_home_ci[0]*100:.1f}-{ats_home_ci[1]*100:.1f}%]  "
                     f"Away {total_away}W/{total_n} = {total_away/total_n*100:.1f}% "
                     f"[CI: {ats_away_ci[0]*100:.1f}-{ats_away_ci[1]*100:.1f}%]")

        if total_ou_n > 0:
            ou_over_ci = wilson_ci(total_over, total_ou_n)
            ou_under_ci = wilson_ci(total_under, total_ou_n)
            lines.append(f"  O/U:      Over {total_over}W/{total_ou_n} = {total_over/total_ou_n*100:.1f}% "
                         f"[CI: {ou_over_ci[0]*100:.1f}-{ou_over_ci[1]*100:.1f}%]  "
                         f"Under {total_under}W/{total_ou_n} = {total_under/total_ou_n*100:.1f}% "
                         f"[CI: {ou_under_ci[0]*100:.1f}-{ou_under_ci[1]*100:.1f}%]")

        # Count seasons above 52.38% for each side
        above_home = sum(1 for r in all_ats if r["total"] > 0 and r["home_pct"] > 52.38)
        above_away = sum(1 for r in all_ats if r["total"] > 0 and r["away_pct"] > 52.38)
        n_seasons = sum(1 for r in all_ats if r["total"] > 0)
        lines.append(f"  Seasons home >52.38%: {above_home}/{n_seasons}  "
                     f"Seasons away >52.38%: {above_away}/{n_seasons}")
```

- [ ] **Step 6: Run tests — expect PASS**

```bash
cd backtest && python -m pytest v3/tests/test_signals.py -v
```

- [ ] **Step 7: Commit**

```bash
git add backtest/v3/signals.py backtest/v3/analyze.py backtest/v3/tests/test_signals.py
git commit -m "feat(v3): signal analysis engine — Wilson CI, all signal conditions, audit report generator"
```

---

### Task 7: Validation engine

**Files:**
- Create: `backtest/v3/validate_signals.py`

- [ ] **Step 1: Write validate_signals.py**

```python
"""Leave-one-season-out cross-validation and monotonicity checks."""
import pandas as pd
from scipy.stats import spearmanr
from v3.signals import SIGNAL_CONDITIONS, compute_split, wilson_ci
from v3.analyze import assign_season


def leave_one_season_out(all_games: pd.DataFrame, sig_id: str, market: str = "ats") -> list[dict]:
    """Leave-one-season-out cross-validation for a signal.

    For each season S:
    1. Determine the winning direction from all OTHER seasons
    2. Test that direction on season S
    3. Record whether it holds

    Args:
        market: 'ats' or 'ou'
    Returns: list of dicts with per-season validation results
    """
    sig = SIGNAL_CONDITIONS[sig_id]
    all_games = all_games.copy()
    all_games["season"] = all_games["date"].apply(assign_season)
    seasons = sorted(all_games["season"].unique())
    result_col = "ats_result" if market == "ats" else "ou_result"

    results = []
    for held_out in seasons:
        train = all_games[all_games["season"] != held_out]
        test = all_games[all_games["season"] == held_out]

        # Get matched games in train and test
        train_matched = train[train.apply(sig["filter"], axis=1)]
        test_matched = test[test.apply(sig["filter"], axis=1)]

        if len(train_matched) == 0 or len(test_matched) == 0:
            continue

        # Determine direction from training data
        train_split = compute_split(train_matched[result_col].tolist())
        if market == "ats":
            train_direction = "home" if train_split["home_pct"] > train_split["away_pct"] else "away"
            train_pct = max(train_split["home_pct"], train_split["away_pct"])
        else:
            train_direction = "over" if train_split["home_pct"] > train_split["away_pct"] else "under"
            train_pct = max(train_split["home_pct"], train_split["away_pct"])

        # Test on held-out season
        test_split = compute_split(test_matched[result_col].tolist())
        if market == "ats":
            test_pct = test_split["home_pct"] if train_direction == "home" else test_split["away_pct"]
            test_wins = test_split["home_wins"] if train_direction == "home" else test_split["away_wins"]
        else:
            test_pct = test_split["home_pct"] if train_direction == "over" else test_split["away_pct"]
            test_wins = test_split["home_wins"] if train_direction == "over" else test_split["away_wins"]

        test_ci = wilson_ci(test_wins, test_split["total"])

        results.append({
            "held_out": held_out,
            "train_direction": train_direction,
            "train_pct": train_pct,
            "test_n": test_split["total"],
            "test_pct": test_pct,
            "test_ci_lo": test_ci[0] * 100,
            "test_ci_hi": test_ci[1] * 100,
            "above_breakeven": test_pct > 52.38,
        })

    return results


def monotonicity_check(all_games: pd.DataFrame, sig_id: str, continuous_col: str,
                       buckets: list[tuple[float, float]], market: str = "ats") -> dict:
    """Check if a continuous variable shows monotonic relationship with outcomes.

    Args:
        continuous_col: column name (e.g., 'away_travel_dist', 'away_est_sleep')
        buckets: list of (low, high) boundaries
        market: 'ats' or 'ou'
    Returns: dict with Spearman rho, p-value, and per-bucket results
    """
    sig = SIGNAL_CONDITIONS[sig_id]
    result_col = "ats_result" if market == "ats" else "ou_result"
    matched = all_games[all_games.apply(sig["filter"], axis=1)].copy()

    bucket_results = []
    for lo, hi in buckets:
        bucket = matched[(matched[continuous_col] >= lo) & (matched[continuous_col] < hi)]
        split = compute_split(bucket[result_col].tolist())
        bucket_results.append({
            "range": f"{lo}-{hi}",
            "n": split["total"],
            "home_pct": split["home_pct"],
            "away_pct": split["away_pct"],
        })

    # Spearman correlation on bucket midpoints vs win rates
    midpoints = [(lo + hi) / 2 for lo, hi in buckets]
    pcts = [b["home_pct"] for b in bucket_results if b["n"] > 0]
    valid_midpoints = [m for m, b in zip(midpoints, bucket_results) if b["n"] > 0]

    if len(valid_midpoints) >= 3:
        rho, p_value = spearmanr(valid_midpoints, pcts)
    else:
        rho, p_value = 0.0, 1.0

    return {
        "spearman_rho": rho,
        "p_value": p_value,
        "buckets": bucket_results,
        "monotonic": abs(rho) > 0.6,
    }


def generate_validation_report(all_games: pd.DataFrame, passing_signals: list[str],
                                output_path: str):
    """Generate validation report for signals that passed Stage 2."""
    import os
    lines = []
    lines.append("=" * 70)
    lines.append("  NBA EDGE V3 — VALIDATION REPORT")
    lines.append("  Leave-one-season-out cross-validation + monotonicity")
    lines.append("=" * 70)

    for sig_id in passing_signals:
        sig = SIGNAL_CONDITIONS[sig_id]
        lines.append(f"\n{'='*70}")
        lines.append(f"  {sig_id}: {sig['name']}")
        lines.append(f"{'='*70}")

        for market, label in [("ats", "ATS"), ("ou", "O/U")]:
            lines.append(f"\n--- {label} Leave-One-Season-Out ---")
            results = leave_one_season_out(all_games, sig_id, market)
            above_count = sum(1 for r in results if r["above_breakeven"])

            lines.append(f"  {'Season':<10} {'Dir':>6} {'Train%':>7} {'TestN':>6} {'Test%':>7} {'CI':>15} {'Pass':>5}")
            for r in results:
                lines.append(
                    f"  {r['held_out']:<10} {r['train_direction']:>6} {r['train_pct']:>6.1f}% "
                    f"{r['test_n']:>6} {r['test_pct']:>6.1f}% "
                    f"[{r['test_ci_lo']:>5.1f}-{r['test_ci_hi']:>5.1f}%] "
                    f"{'YES' if r['above_breakeven'] else ' NO':>5}"
                )
            lines.append(f"  Seasons above 52.38%: {above_count}/{len(results)}")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Validation report written to {output_path}")
```

- [ ] **Step 2: Commit**

```bash
git add backtest/v3/validate_signals.py
git commit -m "feat(v3): validation engine — leave-one-season-out CV and monotonicity checks"
```

---

### Task 8: Pipeline orchestrator

**Files:**
- Create: `backtest/v3/pipeline.py`

- [ ] **Step 1: Write pipeline.py**

```python
"""V3 pipeline orchestrator: load → validate → schedule → analyze → validate_signals."""
import os
import sys
import pandas as pd

SCRIPT_DIR = os.path.dirname(__file__)
RAW_DIR = os.path.join(SCRIPT_DIR, "data", "raw")
OUT_DIR = os.path.join(SCRIPT_DIR, "data", "processed")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    # ── Stage 1: Load data ──
    print("=" * 60)
    print("STAGE 1: Loading data")
    print("=" * 60)

    from v3.load_data import load_kaggle, load_sbr

    kaggle_path = os.path.join(RAW_DIR, "kaggle_nba_betting.csv")
    sbr_path = os.path.join(RAW_DIR, "sbr_archive_10y.json")

    if not os.path.exists(kaggle_path):
        print(f"ERROR: Kaggle data not found at {kaggle_path}")
        print("Download from: https://www.kaggle.com/datasets/cviaxmiwnptr/nba-betting-data-october-2007-to-june-2024")
        sys.exit(1)

    kaggle_df = load_kaggle()
    print(f"Kaggle: {len(kaggle_df)} games loaded")

    # Filter to target seasons (modern era, exclude COVID-compromised years)
    VALID_SEASONS = {"2018-19", "2021-22", "2022-23", "2023-24", "2024-25"}
    from v3.analyze import assign_season
    kaggle_df["season"] = kaggle_df["date"].apply(assign_season)
    kaggle_df = kaggle_df[kaggle_df["season"].isin(VALID_SEASONS)].copy()
    print(f"After season filter (excludes 2019-20 bubble, 2020-21 shortened): {len(kaggle_df)} games")

    sbr_df = None
    if os.path.exists(sbr_path):
        sbr_df = load_sbr()
        print(f"SBR: {len(sbr_df)} games loaded")
    else:
        print("SBR data not found — skipping (Kaggle-only mode)")

    # Use Kaggle as primary source
    all_games = kaggle_df

    # ── Stage 1b: Validate data quality ──
    print("\n" + "=" * 60)
    print("STAGE 1b: Validating data quality")
    print("=" * 60)

    from v3.validate_data import quality_report, cross_reference

    report = quality_report(all_games, "Kaggle Primary")
    print(report)
    with open(os.path.join(OUT_DIR, "quality_report.txt"), "w") as f:
        f.write(report)

    if sbr_df is not None:
        disc = cross_reference(kaggle_df, sbr_df)
        if len(disc) > 0:
            disc.to_csv(os.path.join(OUT_DIR, "discrepancies.csv"), index=False)
            print(f"Discrepancies saved to discrepancies.csv")

    # ── Stage 2: Compute schedule context ──
    print("\n" + "=" * 60)
    print("STAGE 2: Computing schedule context")
    print("=" * 60)

    from v3.schedule import compute_schedule_context
    from v3.analyze import assign_season

    all_games["season"] = all_games["date"].apply(assign_season)
    seasons = sorted(all_games["season"].unique())
    print(f"Seasons found: {len(seasons)}")

    enriched_frames = []
    for season in seasons:
        season_df = all_games[all_games["season"] == season].copy()
        print(f"  Processing {season}: {len(season_df)} games...", end="", flush=True)
        enriched = compute_schedule_context(season_df)
        enriched_frames.append(enriched)
        # Save per-season CSV
        enriched.to_csv(os.path.join(OUT_DIR, f"full_season_{season.replace('-', '_')}.csv"), index=False)
        print(" done")

    all_enriched = pd.concat(enriched_frames, ignore_index=True)
    print(f"Total enriched games: {len(all_enriched)}")

    # ── Stage 3: Signal analysis ──
    print("\n" + "=" * 60)
    print("STAGE 3: Running signal analysis")
    print("=" * 60)

    from v3.analyze import run_signal_analysis

    report_path = os.path.join(OUT_DIR, "signal_audit_report.txt")
    run_signal_analysis(all_enriched, report_path)

    # ── Stage 4: Validation (identify passing signals first) ──
    print("\n" + "=" * 60)
    print("STAGE 4: Validation")
    print("=" * 60)
    print("Review signal_audit_report.txt to identify passing signals.")
    print("Then run validate_signals.py on those signals.")
    print("(Automated passing-signal detection can be added once we see the data.)")

    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print(f"Outputs in: {OUT_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit**

```bash
git add backtest/v3/pipeline.py
git commit -m "feat(v3): pipeline orchestrator — wires load, validate, schedule, analyze stages"
```

---

### Task 9: First run with real data

**Prerequisites:** Tasks 1-8 complete. Kaggle CSV downloaded to `backtest/v3/data/raw/kaggle_nba_betting.csv`.

- [ ] **Step 1: Inspect data (from Task 2) and fix column mappings**

Run `inspect_data.py`, compare actual column names against the assumed names in `load_data.py`. Update the `col_map` dict in `load_kaggle()` and field names in `load_sbr()` to match reality.

- [ ] **Step 2: Run the pipeline**

```bash
cd backtest && python -m v3.pipeline
```

This will take several minutes (computing schedule context for 18 seasons × ~1,230 games each).

- [ ] **Step 3: Review quality report**

Read `backtest/v3/data/processed/quality_report.txt`. Check:
- Total game count per season (~1,230 expected)
- Missing spread/total percentages (some early seasons may have gaps)
- Team abbreviation list (should be 30 modern abbreviations)

- [ ] **Step 4: Spot-check 5 known games**

Manually verify 5 games against basketball-reference.com:
- Pick 1 game from 2008, 2012, 2016, 2020, 2024
- Check scores match
- Check spread is plausible

- [ ] **Step 5: Review signal audit report**

Read `backtest/v3/data/processed/signal_audit_report.txt`. This is the main output of the entire pipeline — the per-season signal analysis. Look for:
- Any signal with consistent direction above 52.38% across majority of seasons
- Any signal that clearly fails (below 50% combined)
- Anomalies (seasons with 0 matched games, unexpected patterns)

- [ ] **Step 6: Run validation on promising signals**

For any signal that looks promising in the audit report, run leave-one-season-out:

```python
from v3.validate_signals import leave_one_season_out, generate_validation_report
# Example: if S4 (away B2B) looks promising
results = leave_one_season_out(all_enriched, "S4", "ats")
for r in results:
    print(f"{r['held_out']}: {r['test_pct']:.1f}% (n={r['test_n']}) {'PASS' if r['above_breakeven'] else 'FAIL'}")
```

- [ ] **Step 7: Commit all processed outputs and final adjustments**

```bash
git add backtest/v3/
git commit -m "feat(v3): first full pipeline run — column mappings finalized, pipeline verified"
```

---

### Task 10: Sleep estimation layer comparison

**Prerequisite:** Task 9 complete with working pipeline.

This task tests whether sleep estimation adds value over simple distance.

- [ ] **Step 1: Add sleep-layer analysis to analyze.py**

Add a new function after `run_signal_analysis`:

```python
def run_sleep_layer_analysis(all_games: pd.DataFrame, output_path: str):
    """Compare signal performance across three granularity layers:
    1. Binary (B2B yes/no)
    2. Distance buckets (<500mi, 500-1500mi, >1500mi)
    3. Estimated sleep buckets (<4hrs, 4-6hrs, 6+hrs)

    Tests whether sleep estimation adds predictive value over simpler proxies.
    """
    lines = []
    lines.append("=" * 70)
    lines.append("  SLEEP ESTIMATION LAYER COMPARISON")
    lines.append("=" * 70)

    # Filter to B2B games with travel only (where sleep estimation applies)
    b2b_away = all_games[all_games["away_b2b"] & all_games["away_traveled"]].copy()
    b2b_home = all_games[all_games["home_b2b"] & all_games["home_traveled"]].copy()

    for label, df, dist_col, sleep_col in [
        ("Away B2B + traveled", b2b_away, "away_travel_dist", "away_est_sleep"),
        ("Home B2B + traveled", b2b_home, "home_travel_dist", "home_est_sleep"),
    ]:
        lines.append(f"\n--- {label} (n={len(df)}) ---")

        # Layer 2: Distance buckets
        lines.append("\n  Distance buckets (ATS):")
        for lo, hi, lbl in [(0, 500, "<500mi"), (500, 1500, "500-1500mi"), (1500, 5000, ">1500mi")]:
            bucket = df[(df[dist_col] >= lo) & (df[dist_col] < hi)]
            split = compute_split(bucket["ats_result"].tolist())
            lines.append(f"    {lbl}: Home {split['home_pct']:.1f}% / Away {split['away_pct']:.1f}% (n={split['total']})")

        # Layer 3: Sleep buckets
        sleep_data = df[df[sleep_col].notna()]
        lines.append(f"\n  Sleep buckets (ATS) [n with sleep data: {len(sleep_data)}]:")
        for lo, hi, lbl in [(0, 4, "<4hrs"), (4, 6, "4-6hrs"), (6, 20, "6+hrs")]:
            bucket = sleep_data[(sleep_data[sleep_col] >= lo) & (sleep_data[sleep_col] < hi)]
            split = compute_split(bucket["ats_result"].tolist())
            lines.append(f"    {lbl}: Home {split['home_pct']:.1f}% / Away {split['away_pct']:.1f}% (n={split['total']})")

    report = "\n".join(lines)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Sleep layer report written to {output_path}")
```

- [ ] **Step 2: Run sleep layer analysis**

```python
from v3.analyze import run_sleep_layer_analysis
run_sleep_layer_analysis(all_enriched, "backtest/v3/data/processed/sleep_layer_report.txt")
```

- [ ] **Step 3: Compare results**

If sleep buckets show a stronger gradient than distance buckets (e.g., <4hrs sleep has a meaningfully different ATS rate than 6+ hrs, and this gradient is stronger than the distance gradient), sleep estimation earns its place in Phase 2. If distance alone performs equally, kill sleep estimation.

- [ ] **Step 4: Commit**

```bash
git add backtest/v3/analyze.py
git commit -m "feat(v3): sleep estimation layer comparison — tests whether sleep adds value over distance"
```

---

## Decision Gate

After completing all tasks, review the three output files:

1. **`signal_audit_report.txt`** — Which signals show consistent direction above 52.38%?
2. **`validation_report.txt`** — Do promising signals survive leave-one-season-out?
3. **`sleep_layer_report.txt`** — Does sleep estimation add value?

**If at least one signal passes validation:** Proceed to Phase 2 (empirical model). The validated signals become features. Write a new spec for Phase 2.

**If no signals pass validation:** The fatigue thesis does not beat the market. Do not mine for new thresholds. Consider: (a) the lineup/injury intelligence approach (Phase 3), or (b) accepting that NBA schedule spots are efficiently priced and redirecting effort elsewhere.

**If UNDER signals pass but SPREAD signals don't:** Focus V3 live tool on totals market only. Accept that the spread market prices fatigue correctly but the totals market may not.
