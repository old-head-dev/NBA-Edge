"""
signals.py — Signal analysis primitives for NBA V3 backtest.

Provides:
- wilson_ci: Wilson score 95% confidence interval for binomial proportions
- compute_split: Aggregate ATS/O/U results into a summary dict
- SIGNAL_CONDITIONS: All 12 signal condition definitions (name + filter callable)
"""

from __future__ import annotations

import math
from typing import Callable

import pandas as pd


# ---------------------------------------------------------------------------
# Wilson score confidence interval
# ---------------------------------------------------------------------------

def wilson_ci(wins: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """Compute Wilson score 95% CI for a binomial proportion.

    Args:
        wins:  Number of successes.
        total: Total trials (excluding pushes/None — caller's responsibility).
        z:     Z-score for the desired confidence level (default 1.96 = 95%).

    Returns:
        (lower, upper) as fractions in [0, 1].
        Returns (0.0, 0.0) when total == 0.
    """
    if total == 0:
        return (0.0, 0.0)

    p = wins / total
    z2 = z * z
    denom = 1 + z2 / total
    centre = (p + z2 / (2 * total)) / denom
    spread = z * math.sqrt((p * (1 - p) + z2 / (4 * total)) / total) / denom

    lower = max(0.0, centre - spread)
    upper = min(1.0, centre + spread)
    return (lower, upper)


# ---------------------------------------------------------------------------
# Aggregate ATS / O/U results
# ---------------------------------------------------------------------------

def compute_split(results: list) -> dict:
    """Summarise a list of result strings into a split dictionary.

    Accepted strings:
        ATS:   "home" | "away" | "push" | None
        O/U:   "over" | "under" | "push" | None

    "over"  counts as home_wins, "under" counts as away_wins.
    Pushes and None values are excluded from the denominator.

    Returns dict with keys:
        home_wins, away_wins, pushes, total,
        home_pct, away_pct,
        home_ci, away_ci
    """
    home_wins = 0
    away_wins = 0
    pushes = 0

    for r in results:
        if r is None:
            continue
        if r in ("home", "over"):
            home_wins += 1
        elif r in ("away", "under"):
            away_wins += 1
        elif r == "push":
            pushes += 1

    total = home_wins + away_wins

    if total == 0:
        home_pct = 0.0
        away_pct = 0.0
        home_ci = (0.0, 0.0)
        away_ci = (0.0, 0.0)
    else:
        home_pct = 100.0 * home_wins / total
        away_pct = 100.0 * away_wins / total
        home_ci = wilson_ci(home_wins, total)
        away_ci = wilson_ci(away_wins, total)

    return {
        "home_wins": home_wins,
        "away_wins": away_wins,
        "pushes": pushes,
        "total": total,
        "home_pct": home_pct,
        "away_pct": away_pct,
        "home_ci": home_ci,
        "away_ci": away_ci,
    }


# ---------------------------------------------------------------------------
# Signal condition definitions
# ---------------------------------------------------------------------------
# Each filter receives a pandas Series (one row) with schedule context columns
# from schedule.py.  Boolean columns may be numpy.bool_, so we use bool()
# to convert before any Python boolean logic.

def _s1(r: pd.Series) -> bool:
    """S1: Home on B2B, away NOT on B2B."""
    return bool(r["home_b2b"]) and not bool(r["away_b2b"])


def _s2(r: pd.Series) -> bool:
    """S2: Home on B2B + traveled, away NOT on B2B."""
    return bool(r["home_b2b"]) and bool(r["home_traveled"]) and not bool(r["away_b2b"])


def _s3(r: pd.Series) -> bool:
    """S3: Home on B2B + long travel (>=1000mi), away NOT on B2B."""
    return (
        bool(r["home_b2b"])
        and bool(r["home_traveled"])
        and float(r["home_travel_dist"]) >= 1000.0
        and not bool(r["away_b2b"])
    )


def _s4(r: pd.Series) -> bool:
    """S4: Away on B2B, home NOT on B2B."""
    return bool(r["away_b2b"]) and not bool(r["home_b2b"])


def _s5(r: pd.Series) -> bool:
    """S5: Away on B2B + traveled, home NOT on B2B."""
    return bool(r["away_b2b"]) and bool(r["away_traveled"]) and not bool(r["home_b2b"])


def _s6(r: pd.Series) -> bool:
    """S6: Away on B2B + long travel (>=1000mi), home NOT on B2B."""
    return (
        bool(r["away_b2b"])
        and bool(r["away_traveled"])
        and float(r["away_travel_dist"]) >= 1000.0
        and not bool(r["home_b2b"])
    )


def _b1(r: pd.Series) -> bool:
    """B1: Both B2B, only road traveled (home home-home B2B)."""
    return bool(r["away_b2b"]) and bool(r["home_b2b"]) and not bool(r["home_traveled"])


def _b2(r: pd.Series) -> bool:
    """B2: Both B2B, both traveled (home also played away yesterday)."""
    return bool(r["away_b2b"]) and bool(r["home_b2b"]) and bool(r["home_traveled"])


def _d1(r: pd.Series) -> bool:
    """D1: Home on 3-in-4 or 4-in-6."""
    return bool(r["home_3in4"]) or bool(r["home_4in6"])


def _d2(r: pd.Series) -> bool:
    """D2: Away on 3-in-4 or 4-in-6."""
    return bool(r["away_3in4"]) or bool(r["away_4in6"])


def _a1(r: pd.Series) -> bool:
    """A1: Visitor at DEN/UTA on B2B with travel."""
    return bool(r["away_b2b"]) and bool(r["away_traveled"]) and bool(r["away_at_altitude"])


def _c1(r: pd.Series) -> bool:
    """C1: Neither team on B2B (control group)."""
    return not bool(r["away_b2b"]) and not bool(r["home_b2b"])


SIGNAL_CONDITIONS: dict[str, dict] = {
    "S1": {"name": "Home on B2B, away NOT on B2B", "filter": _s1},
    "S2": {"name": "Home on B2B + traveled, away NOT on B2B", "filter": _s2},
    "S3": {"name": "Home on B2B + long travel (>=1000mi), away NOT on B2B", "filter": _s3},
    "S4": {"name": "Away on B2B, home NOT on B2B", "filter": _s4},
    "S5": {"name": "Away on B2B + traveled, home NOT on B2B", "filter": _s5},
    "S6": {"name": "Away on B2B + long travel (>=1000mi), home NOT on B2B", "filter": _s6},
    "B1": {"name": "Both B2B, only road traveled (home home-home B2B)", "filter": _b1},
    "B2": {"name": "Both B2B, both traveled (home also played away yesterday)", "filter": _b2},
    "D1": {"name": "Home on 3-in-4 or 4-in-6", "filter": _d1},
    "D2": {"name": "Away on 3-in-4 or 4-in-6", "filter": _d2},
    "A1": {"name": "Visitor at DEN/UTA on B2B with travel", "filter": _a1},
    "C1": {"name": "Neither team on B2B (control)", "filter": _c1},
}
