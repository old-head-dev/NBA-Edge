"""
validate_signals.py — Cross-validation and monotonicity checks for NBA V3 signals.

Provides:
- leave_one_season_out: Leave-one-season-out cross-validation for a signal
- monotonicity_check: Spearman-rho monotonicity check for a continuous variable
- generate_validation_report: Full validation report across all passing signals
"""

from __future__ import annotations

import io
import sys
from pathlib import Path
from typing import Optional

import pandas as pd
from scipy.stats import spearmanr

from v3.signals import SIGNAL_CONDITIONS, compute_split, wilson_ci
from v3.analyze import assign_season


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BREAK_EVEN = 52.38  # ATS break-even at -110 juice


# ---------------------------------------------------------------------------
# Leave-one-season-out cross-validation
# ---------------------------------------------------------------------------

def leave_one_season_out(
    all_games: pd.DataFrame,
    sig_id: str,
    market: str = "ats",
) -> list[dict]:
    """Leave-one-season-out cross-validation for a signal.

    For each season S:
      1. Train = all games NOT in season S
      2. Test  = all games in season S
      3. Apply the signal filter to both train and test
      4. Determine "winning direction" from training data (higher win rate side)
      5. Test that direction on the held-out season
      6. Record whether it beats the 52.38% break-even

    Args:
        all_games: DataFrame with schedule context + season column.
                   If "season" column is absent it is derived from "date".
        sig_id:    Signal ID from SIGNAL_CONDITIONS (e.g. "S1", "B2").
        market:    "ats" or "ou".

    Returns:
        List of dicts, one per held-out season:
        {
            "held_out":       "2024-25",
            "train_direction": "home" / "away" / "over" / "under",
            "train_pct":      54.2,
            "test_n":         45,
            "test_pct":       51.8,
            "test_ci_lo":     37.2,
            "test_ci_hi":     66.0,
            "above_breakeven": False,
        }
    """
    if market not in ("ats", "ou"):
        raise ValueError(f"market must be 'ats' or 'ou', got {market!r}")
    if sig_id not in SIGNAL_CONDITIONS:
        raise ValueError(f"Unknown signal ID: {sig_id!r}")

    # Ensure season column is present
    if "season" not in all_games.columns:
        all_games = all_games.copy()
        all_games["season"] = all_games["date"].astype(str).apply(assign_season)

    sig_filter = SIGNAL_CONDITIONS[sig_id]["filter"]
    result_col = "ats_result" if market == "ats" else "ou_result"

    seasons = sorted(all_games["season"].unique().tolist())
    records: list[dict] = []

    for held_out in seasons:
        train_df = all_games[all_games["season"] != held_out]
        test_df  = all_games[all_games["season"] == held_out]

        # Apply signal filter to train and test
        train_matched = train_df[train_df.apply(sig_filter, axis=1)]
        test_matched  = test_df[test_df.apply(sig_filter, axis=1)]

        # Determine winning direction from training data
        train_results = train_matched[result_col].tolist()
        train_split = compute_split(train_results)

        if train_split["total"] == 0:
            # No training data — skip this fold
            continue

        # For ATS: "home" / "away"; for O/U: "over" (home_wins) / "under" (away_wins)
        if train_split["home_pct"] >= train_split["away_pct"]:
            if market == "ats":
                train_direction = "home"
            else:
                train_direction = "over"
            train_pct = train_split["home_pct"]
            train_wins_key = "home_wins"
        else:
            if market == "ats":
                train_direction = "away"
            else:
                train_direction = "under"
            train_pct = train_split["away_pct"]
            train_wins_key = "away_wins"

        # Score the held-out season in that direction
        test_results = test_matched[result_col].tolist()
        test_split = compute_split(test_results)
        test_n = test_split["total"]

        if test_n == 0:
            # No test games matched — record with zeros
            records.append({
                "held_out": held_out,
                "train_direction": train_direction,
                "train_pct": round(train_pct, 1),
                "test_n": 0,
                "test_pct": 0.0,
                "test_ci_lo": 0.0,
                "test_ci_hi": 0.0,
                "above_breakeven": False,
            })
            continue

        test_wins = test_split[train_wins_key]
        test_pct = 100.0 * test_wins / test_n
        ci_lo, ci_hi = wilson_ci(test_wins, test_n)

        records.append({
            "held_out": held_out,
            "train_direction": train_direction,
            "train_pct": round(train_pct, 1),
            "test_n": test_n,
            "test_pct": round(test_pct, 1),
            "test_ci_lo": round(ci_lo * 100.0, 1),
            "test_ci_hi": round(ci_hi * 100.0, 1),
            "above_breakeven": test_pct > _BREAK_EVEN,
        })

    return records


# ---------------------------------------------------------------------------
# Monotonicity check
# ---------------------------------------------------------------------------

def monotonicity_check(
    all_games: pd.DataFrame,
    sig_id: str,
    continuous_col: str,
    buckets: list[tuple[float, float]],
    market: str = "ats",
) -> dict:
    """Check if a continuous variable shows a monotonic relationship with outcomes.

    Args:
        all_games:      DataFrame with schedule context.
        sig_id:         Signal ID from SIGNAL_CONDITIONS.
        continuous_col: Column name (e.g. "away_travel_dist", "away_est_sleep").
        buckets:        List of (low, high) tuples defining bin edges (inclusive low,
                        exclusive high, except the last bucket which is inclusive).
        market:         "ats" or "ou".

    Returns:
        {
            "spearman_rho": float,
            "p_value":      float,
            "buckets": [
                {"range": "0-500", "n": 120, "home_pct": 52.1, "away_pct": 47.9},
                ...
            ],
            "monotonic": bool,   # abs(rho) > 0.6
        }

        Returns {"spearman_rho": None, "p_value": None, "buckets": [], "monotonic": False}
        when fewer than 3 non-empty buckets are available.
    """
    if market not in ("ats", "ou"):
        raise ValueError(f"market must be 'ats' or 'ou', got {market!r}")
    if sig_id not in SIGNAL_CONDITIONS:
        raise ValueError(f"Unknown signal ID: {sig_id!r}")

    sig_filter = SIGNAL_CONDITIONS[sig_id]["filter"]
    result_col = "ats_result" if market == "ats" else "ou_result"

    # Filter to signal-matched rows
    matched = all_games[all_games.apply(sig_filter, axis=1)].copy()

    bucket_rows: list[dict] = []
    midpoints: list[float] = []
    winning_pcts: list[float] = []

    for i, (lo, hi) in enumerate(buckets):
        is_last = i == len(buckets) - 1
        if is_last:
            mask = (matched[continuous_col] >= lo) & (matched[continuous_col] <= hi)
        else:
            mask = (matched[continuous_col] >= lo) & (matched[continuous_col] < hi)

        bucket_games = matched[mask]
        n = len(bucket_games)

        split = compute_split(bucket_games[result_col].tolist()) if n > 0 else compute_split([])

        bucket_rows.append({
            "range": f"{lo:.0f}-{hi:.0f}",
            "n": n,
            "home_pct": round(split["home_pct"], 1),
            "away_pct": round(split["away_pct"], 1),
        })

        if n > 0 and split["total"] > 0:
            midpoints.append((lo + hi) / 2.0)
            winning_pcts.append(split["home_pct"])

    # Need at least 3 non-empty buckets for Spearman
    if len(midpoints) < 3:
        return {
            "spearman_rho": None,
            "p_value": None,
            "buckets": bucket_rows,
            "monotonic": False,
        }

    rho, p_value = spearmanr(midpoints, winning_pcts)

    return {
        "spearman_rho": round(float(rho), 4),
        "p_value": round(float(p_value), 4),
        "buckets": bucket_rows,
        "monotonic": abs(rho) > 0.6,
    }


# ---------------------------------------------------------------------------
# Validation report
# ---------------------------------------------------------------------------

def generate_validation_report(
    all_games: pd.DataFrame,
    passing_signals: list[str],
    output_path: str,
) -> str:
    """Run leave-one-season-out CV for each passing signal and write a report.

    For each signal in passing_signals:
      - Run LOSO for both "ats" and "ou"
      - Print per-season table: Season | Direction | TrainPct | TestN | TestPct | CI | Pass
      - Print summary line: "Seasons above 52.38%: X/Y"

    Output is written to output_path AND printed to stdout.

    Args:
        all_games:       Enriched games DataFrame with schedule context.
        passing_signals: List of signal IDs to validate (e.g. ["S1", "S4"]).
        output_path:     File path to write the report.

    Returns:
        output_path as a string.
    """
    buffer = io.StringIO()
    original_stdout = sys.stdout
    sys.stdout = buffer

    try:
        for sig_id in passing_signals:
            sig_name = SIGNAL_CONDITIONS[sig_id]["name"]
            _print_separator(f"Signal {sig_id}: {sig_name}", char="═")
            print()

            for market in ("ats", "ou"):
                _print_separator(f"Market: {market.upper()}", char="─")
                records = leave_one_season_out(all_games, sig_id, market=market)

                if not records:
                    print("  (no data)")
                    print()
                    continue

                # Header
                print(
                    f"  {'Season':<10} {'Direction':<10} {'TrainPct':>9} "
                    f"{'TestN':>6} {'TestPct':>8} {'CI':>17}  {'Pass':>5}"
                )
                print("  " + "─" * 75)

                above_count = 0
                eligible_count = 0

                for rec in records:
                    if rec["test_n"] == 0:
                        ci_str = "      N/A"
                        pass_str = "  —"
                    else:
                        ci_str = f"[{rec['test_ci_lo']:.1f}–{rec['test_ci_hi']:.1f}]"
                        pass_str = "YES" if rec["above_breakeven"] else " no"
                        eligible_count += 1
                        if rec["above_breakeven"]:
                            above_count += 1

                    print(
                        f"  {rec['held_out']:<10} {rec['train_direction']:<10} "
                        f"{rec['train_pct']:>9.1f} "
                        f"{rec['test_n']:>6} {rec['test_pct']:>8.1f} "
                        f"{ci_str:>17}  {pass_str:>5}"
                    )

                print()
                print(f"  Seasons above {_BREAK_EVEN}%: {above_count}/{eligible_count}")
                print()

            _print_separator(char="═")
            print()

    finally:
        sys.stdout = original_stdout

    report = buffer.getvalue()

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(report, end="")

    return output_path


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _print_separator(title: str = "", char: str = "─", width: int = 72) -> None:
    if title:
        pad = max(0, width - len(title) - 2)
        left = pad // 2
        right = pad - left
        print(f"{char * left} {title} {char * right}")
    else:
        print(char * width)
