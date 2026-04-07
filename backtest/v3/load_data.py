"""
load_data.py — NBA Edge V3 data loading pipeline.

Loads historical game data from two sources:
  - Kaggle CSV  (nba_2008-2025.csv):  2007-08 through 2024-25 regular season
  - SBR JSON    (sbr_archive_10y.json): 2011-12 through 2021-22

Both loaders return a normalized pd.DataFrame with consistent columns:
  date, season, home_team, away_team, home_score, away_score,
  home_spread, total, ats_result, ou_result, source

Run from the backtest/ directory:
    python -c "from v3.load_data import load_kaggle, load_sbr; print(load_kaggle().shape)"
"""

import math
import os

import pandas as pd

from v3.arenas import normalize_team

# Data directory: backtest/v3/data/raw/
DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "raw")

# ---------------------------------------------------------------------------
# SBR team name → modern 3-letter abbreviation
# ---------------------------------------------------------------------------

SBR_TEAM_NAMES: dict[str, str] = {
    "Hawks": "ATL",
    "Celtics": "BOS",
    "Nets": "BKN",
    "Hornets": "CHA",
    "Bulls": "CHI",
    "Cavaliers": "CLE",
    "Mavericks": "DAL",
    "Nuggets": "DEN",
    "Pistons": "DET",
    "Warriors": "GSW",
    "Golden State": "GSW",
    "Rockets": "HOU",
    "Pacers": "IND",
    "Clippers": "LAC",
    "LA Clippers": "LAC",
    "Lakers": "LAL",
    "Grizzlies": "MEM",
    "Heat": "MIA",
    "Bucks": "MIL",
    "Timberwolves": "MIN",
    "Pelicans": "NOP",
    "Knicks": "NYK",
    "Thunder": "OKC",
    "Oklahoma City": "OKC",
    "Magic": "ORL",
    "Seventysixers": "PHI",
    "Suns": "PHX",
    "Trailblazers": "POR",
    "Kings": "SAC",
    "Spurs": "SAS",
    "Raptors": "TOR",
    "Jazz": "UTA",
    "Wizards": "WAS",
    "NewJersey": "BKN",
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _safe_float(val) -> float | None:
    """Convert val to float. Returns None for empty strings, None, or NaN."""
    if val is None:
        return None
    if isinstance(val, float) and math.isnan(val):
        return None
    if isinstance(val, str) and val.strip() == "":
        return None
    try:
        result = float(val)
        if math.isnan(result):
            return None
        return result
    except (ValueError, TypeError):
        return None


def _safe_int(val) -> int | None:
    """Convert val to int. Returns None for empty strings, None, or NaN."""
    f = _safe_float(val)
    if f is None:
        return None
    return int(f)


def compute_ats_result(home_score, away_score, home_spread) -> str | None:
    """Determine ATS result from the home team's perspective.

    Args:
        home_score: Final home team score.
        away_score: Final away team score.
        home_spread: The spread from home team's perspective (negative = home favored).
            e.g. home_spread=-8 means home is favored by 8.

    Returns:
        "home"  — home team covered the spread
        "away"  — away team covered the spread
        "push"  — exactly on the number
        None    — if home_spread is None
    """
    if home_score is None or away_score is None or home_spread is None:
        return None
    adjusted = home_score + home_spread
    if adjusted > away_score:
        return "home"
    elif adjusted < away_score:
        return "away"
    else:
        return "push"


def compute_ou_result(home_score, away_score, total) -> str | None:
    """Determine over/under result.

    Args:
        home_score: Final home team score.
        away_score: Final away team score.
        total: The game total (over/under line).

    Returns:
        "over"  — combined score exceeds total
        "under" — combined score is below total
        "push"  — combined score equals total exactly
        None    — if total is None
    """
    if home_score is None or away_score is None or total is None:
        return None
    combined = home_score + away_score
    if combined > total:
        return "over"
    elif combined < total:
        return "under"
    else:
        return "push"


def normalize_game_row(row: dict) -> dict:
    """Normalize team abbreviations in a game row using normalize_team().

    Modifies 'home_team' and 'away_team' keys if they exist.
    All other fields are preserved unchanged.
    """
    result = dict(row)
    if "home_team" in result:
        result["home_team"] = normalize_team(str(result["home_team"]))
    if "away_team" in result:
        result["away_team"] = normalize_team(str(result["away_team"]))
    return result


def _season_label_kaggle(season_int: int) -> str:
    """Convert Kaggle season int to label string.

    Kaggle: 2025 means 2024-25 season (the year the season ends).
    """
    start_year = int(season_int) - 1
    end_year = int(season_int)
    return f"{start_year}-{str(end_year)[-2:]}"


def _season_label_sbr(season_int: int) -> str:
    """Convert SBR season int to label string.

    SBR: 2011 means 2011-12 season (the year the season starts).
    """
    start_year = int(season_int)
    end_year = int(season_int) + 1
    return f"{start_year}-{str(end_year)[-2:]}"


# ---------------------------------------------------------------------------
# load_kaggle
# ---------------------------------------------------------------------------

def load_kaggle(filename: str = "nba_2008-2025.csv") -> pd.DataFrame:
    """Load and normalize the Kaggle NBA game history CSV.

    Filters to regular-season games only. Converts lowercase team abbreviations
    to canonical 3-letter codes. Derives home_spread from whos_favored + spread.
    Computes ats_result and ou_result from final scores.

    Returns a pd.DataFrame sorted by date with a reset index.
    """
    filepath = os.path.join(DATA_DIR, filename)
    df = pd.read_csv(filepath, dtype=str)

    # Filter to regular season only
    df = df[df["regular"] == "True"].copy()

    # Parse dates
    df["date"] = pd.to_datetime(df["date"])

    # Convert season to label: 2025 -> "2024-25"
    df["season"] = df["season"].apply(lambda s: _season_label_kaggle(int(s)))

    # Rename score columns
    df = df.rename(columns={"score_away": "away_score", "score_home": "home_score"})

    # Convert scores to int
    df["home_score"] = df["home_score"].apply(_safe_int)
    df["away_score"] = df["away_score"].apply(_safe_int)

    # Convert spread and total to float
    df["spread"] = df["spread"].apply(_safe_float)
    df["total"] = df["total"].apply(_safe_float)

    # Derive home_spread from whos_favored + spread
    # spread is always POSITIVE in the CSV; whos_favored indicates direction
    def _to_home_spread(row):
        spread = row["spread"]
        if spread is None:
            return None
        whos = row["whos_favored"]
        if whos == "home":
            return -spread
        elif whos == "away":
            return +spread
        else:
            return None

    df["home_spread"] = df.apply(_to_home_spread, axis=1)

    # Normalize team abbreviations (lowercase kaggle → canonical)
    df["home_team"] = df["home"].apply(lambda t: normalize_team(str(t)))
    df["away_team"] = df["away"].apply(lambda t: normalize_team(str(t)))

    # Compute ATS and OU results
    df["ats_result"] = df.apply(
        lambda r: compute_ats_result(r["home_score"], r["away_score"], r["home_spread"]),
        axis=1,
    )
    df["ou_result"] = df.apply(
        lambda r: compute_ou_result(r["home_score"], r["away_score"], r["total"]),
        axis=1,
    )

    # Add source tag
    df["source"] = "kaggle"

    # Sort and reset index
    df = df.sort_values("date").reset_index(drop=True)

    return df


# ---------------------------------------------------------------------------
# load_sbr
# ---------------------------------------------------------------------------

def load_sbr(filename: str = "sbr_archive_10y.json") -> pd.DataFrame:
    """Load and normalize the SBR archive JSON.

    Skips records with team name '0' (bad data). Maps full team names to
    3-letter abbreviations. Derives home_spread from home_close_spread.
    Computes ats_result and ou_result from final scores.

    Returns a pd.DataFrame sorted by date with a reset index.
    """
    filepath = os.path.join(DATA_DIR, filename)
    raw = pd.read_json(filepath)

    # Drop records where home_team or away_team is '0' (bad data)
    raw = raw[
        (raw["home_team"].astype(str) != "0") &
        (raw["away_team"].astype(str) != "0")
    ].copy()

    # Parse date: float 20111225.0 -> datetime 2011-12-25
    raw["date"] = raw["date"].apply(
        lambda d: pd.to_datetime(str(int(d)), format="%Y%m%d")
    )

    # Convert season to label: 2011 -> "2011-12"
    raw["season"] = raw["season"].apply(lambda s: _season_label_sbr(int(s)))

    # Map team names to abbreviations
    def _map_team(name: str) -> str:
        name_str = str(name)
        if name_str in SBR_TEAM_NAMES:
            return SBR_TEAM_NAMES[name_str]
        # Fallback: try normalize_team (handles abbreviations)
        return normalize_team(name_str)

    raw["home_team"] = raw["home_team"].apply(_map_team)
    raw["away_team"] = raw["away_team"].apply(_map_team)

    # Convert final scores to int
    raw["home_score"] = raw["home_final"].apply(_safe_int)
    raw["away_score"] = raw["away_final"].apply(_safe_int)

    # home_close_spread is already from the home perspective (negative = home favored)
    raw["home_spread"] = raw["home_close_spread"].apply(_safe_float)

    # Closing total
    raw["total"] = raw["close_over_under"].apply(_safe_float)

    # Opening lines (keep as extra columns)
    raw["open_spread"] = raw["home_open_spread"].apply(_safe_float)
    raw["open_total"] = raw["open_over_under"].apply(_safe_float)

    # Compute ATS and OU results
    raw["ats_result"] = raw.apply(
        lambda r: compute_ats_result(r["home_score"], r["away_score"], r["home_spread"]),
        axis=1,
    )
    raw["ou_result"] = raw.apply(
        lambda r: compute_ou_result(r["home_score"], r["away_score"], r["total"]),
        axis=1,
    )

    # Add source tag
    raw["source"] = "sbr"

    # Sort and reset index
    raw = raw.sort_values("date").reset_index(drop=True)

    return raw
