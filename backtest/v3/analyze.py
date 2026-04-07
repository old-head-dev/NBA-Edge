"""
analyze.py — Signal audit report generator for NBA V3 backtest.

Entry point:
    run_signal_analysis(all_games, output_path) -> str

For each signal in SIGNAL_CONDITIONS:
  - Full season, Pre-ASB, Post-ASB breakdowns
  - Post-ASB with tanking filters (0.250 / 0.300 / 0.350)
  - Per-season tables with combined Wilson CI summary
"""

from __future__ import annotations

import io
import sys
from pathlib import Path
from typing import Optional

import pandas as pd

from v3.signals import SIGNAL_CONDITIONS, compute_split

# ---------------------------------------------------------------------------
# All-Star Break dates (first day after the break / break date)
# ---------------------------------------------------------------------------

ALL_STAR_BREAK_DATES: dict[str, str] = {
    "2018-19": "2019-02-17",
    "2019-20": "2020-02-16",
    "2020-21": "2021-03-07",
    "2021-22": "2022-02-20",
    "2022-23": "2023-02-19",
    "2023-24": "2024-02-18",
    "2024-25": "2025-02-16",
}


# ---------------------------------------------------------------------------
# Season label assignment
# ---------------------------------------------------------------------------

def assign_season(date: str) -> str:
    """Convert a game date string (YYYY-MM-DD) to a season label.

    If month >= 10 (Oct/Nov/Dec): season starts THIS year → "YYYY-YY"
    Else (Jan–Sep):               season started LAST year → "YYYY-YY"

    The second part is always 2-digit zero-padded modulo 100.
    """
    ts = pd.Timestamp(date)
    year = ts.year
    month = ts.month
    if month >= 10:
        start_year = year
    else:
        start_year = year - 1
    end_yy = (start_year + 1) % 100
    return f"{start_year}-{end_yy:02d}"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_BREAK_THRESHOLD = 52.38  # 52.38% = breakeven ATS at -110


def _print_separator(title: str = "", char: str = "─", width: int = 72) -> None:
    if title:
        pad = max(0, width - len(title) - 2)
        left = pad // 2
        right = pad - left
        print(f"{char * left} {title} {char * right}")
    else:
        print(char * width)


def _season_asb_date(season: str) -> Optional[pd.Timestamp]:
    """Return the ASB date as a Timestamp, or None if not in the dict."""
    date_str = ALL_STAR_BREAK_DATES.get(season)
    if date_str is None:
        return None
    return pd.Timestamp(date_str)


def _get_season_games(all_games: pd.DataFrame, season: str) -> pd.DataFrame:
    """Filter all_games to a single season."""
    return all_games[all_games["season"] == season].copy()


def _apply_segment_filter(
    season_games: pd.DataFrame,
    season: str,
    segment: str,
) -> pd.DataFrame:
    """Apply pre/post-ASB or full-season filter to a single season's games."""
    if segment == "full":
        return season_games

    asb_date = _season_asb_date(season)
    if asb_date is None:
        # No ASB date for this season → return empty for pre/post
        return season_games.iloc[0:0]

    dates = pd.to_datetime(season_games["date"])
    if segment == "pre":
        return season_games[dates < asb_date].copy()
    elif segment == "post":
        return season_games[dates >= asb_date].copy()
    else:
        raise ValueError(f"Unknown segment: {segment!r}")


def _apply_tanking_filter(
    games: pd.DataFrame,
    threshold: float,
) -> pd.DataFrame:
    """Exclude games where EITHER team's win_pct is below the threshold.

    Uses cumulative win_pct at game time (away_win_pct, home_win_pct columns).
    This is an approximation of ASB-time win%; exact computation would require
    additional logic.
    """
    mask = (games["away_win_pct"] >= threshold) & (games["home_win_pct"] >= threshold)
    return games[mask].copy()


# ---------------------------------------------------------------------------
# Per-season table printer
# ---------------------------------------------------------------------------

def _print_per_season_table(season_rows: list[dict]) -> None:
    """Print a formatted per-season breakdown table."""
    header = f"{'Season':<10} {'N':>5}  {'Home ATS%':>10} {'Away ATS%':>10}  {'Over%':>7} {'Under%':>7}"
    print(header)
    print("─" * len(header))
    for row in season_rows:
        print(
            f"{row['season']:<10} {row['n']:>5}  "
            f"{row['home_ats_pct']:>10.1f} {row['away_ats_pct']:>10.1f}  "
            f"{row['over_pct']:>7.1f} {row['under_pct']:>7.1f}"
        )


# ---------------------------------------------------------------------------
# Core analysis function for one signal × one segment
# ---------------------------------------------------------------------------

def _analyze_segment(
    all_games: pd.DataFrame,
    seasons: list[str],
    sig: dict,
    lines: pd.DataFrame,
    segment: str,
    tank_threshold: Optional[float] = None,
) -> None:
    """Run analysis for one signal condition on one segment (full/pre/post-ASB).

    Prints a per-season table and a combined summary with Wilson CIs.

    Args:
        all_games:      Full enriched games DataFrame (with schedule context).
        seasons:        List of season labels to iterate over.
        sig:            Signal dict with keys "name" and "filter".
        lines:          Not used directly — ATS/O/U results are in all_games.
        segment:        "full" | "pre" | "post"
        tank_threshold: If set, exclude games where either team's win_pct < threshold.
    """
    sig_filter = sig["filter"]

    all_ats_results: list = []
    all_ou_results: list = []
    season_rows: list[dict] = []

    seasons_home_above: int = 0
    seasons_away_above: int = 0
    seasons_over_above: int = 0
    seasons_under_above: int = 0
    seasons_with_data: int = 0

    for season in seasons:
        season_games = _get_season_games(all_games, season)
        season_games = _apply_segment_filter(season_games, season, segment)

        if tank_threshold is not None:
            season_games = _apply_tanking_filter(season_games, tank_threshold)

        # Apply signal filter
        matched = season_games[season_games.apply(sig_filter, axis=1)]
        n = len(matched)

        if n == 0:
            season_rows.append({
                "season": season,
                "n": 0,
                "home_ats_pct": 0.0,
                "away_ats_pct": 0.0,
                "over_pct": 0.0,
                "under_pct": 0.0,
            })
            continue

        seasons_with_data += 1

        ats_results = matched["ats_result"].tolist()
        ou_results = matched["ou_result"].tolist()

        ats_split = compute_split(ats_results)
        ou_split = compute_split(ou_results)

        all_ats_results.extend(ats_results)
        all_ou_results.extend(ou_results)

        if ats_split["home_pct"] > _BREAK_THRESHOLD:
            seasons_home_above += 1
        if ats_split["away_pct"] > _BREAK_THRESHOLD:
            seasons_away_above += 1
        if ou_split["home_pct"] > _BREAK_THRESHOLD:
            seasons_over_above += 1
        if ou_split["away_pct"] > _BREAK_THRESHOLD:
            seasons_under_above += 1

        season_rows.append({
            "season": season,
            "n": n,
            "home_ats_pct": ats_split["home_pct"],
            "away_ats_pct": ats_split["away_pct"],
            "over_pct": ou_split["home_pct"],
            "under_pct": ou_split["away_pct"],
        })

    # Print per-season table
    _print_per_season_table(season_rows)
    print()

    # Combined summary
    combined_ats = compute_split(all_ats_results)
    combined_ou = compute_split(all_ou_results)
    total_n = combined_ats["total"] + combined_ats["pushes"]

    print(f"  Combined N (incl pushes): {total_n}")
    print(f"  ATS  — Home: {combined_ats['home_pct']:.1f}%  "
          f"[{combined_ats['home_ci'][0]*100:.1f}–{combined_ats['home_ci'][1]*100:.1f}%]  |  "
          f"Away: {combined_ats['away_pct']:.1f}%  "
          f"[{combined_ats['away_ci'][0]*100:.1f}–{combined_ats['away_ci'][1]*100:.1f}%]")
    print(f"  O/U  — Over: {combined_ou['home_pct']:.1f}%  "
          f"[{combined_ou['home_ci'][0]*100:.1f}–{combined_ou['home_ci'][1]*100:.1f}%]  |  "
          f"Under: {combined_ou['away_pct']:.1f}%  "
          f"[{combined_ou['away_ci'][0]*100:.1f}–{combined_ou['away_ci'][1]*100:.1f}%]")

    if seasons_with_data > 0:
        print(f"  Seasons home >52.38%:  {seasons_home_above}/{seasons_with_data}")
        print(f"  Seasons away >52.38%:  {seasons_away_above}/{seasons_with_data}")
        print(f"  Seasons over >52.38%:  {seasons_over_above}/{seasons_with_data}")
        print(f"  Seasons under >52.38%: {seasons_under_above}/{seasons_with_data}")


# ---------------------------------------------------------------------------
# Main analysis entry point
# ---------------------------------------------------------------------------

def run_signal_analysis(all_games: pd.DataFrame, output_path: str) -> str:
    """Run the full signal audit for all 12 signals.

    For each signal:
      - Full season breakdown
      - Pre-ASB breakdown (skipped for C1)
      - Post-ASB breakdown (skipped for C1)
      - Post-ASB with tanking filters [0.250, 0.300, 0.350] (skipped for C1)

    Output is written to output_path AND printed to stdout.

    Args:
        all_games:   Enriched games DataFrame with schedule context + season column.
                     Must have columns: season, date, ats_result, ou_result,
                     plus all schedule context columns from schedule.py.
        output_path: File path to write the report text.

    Returns:
        output_path (as a string).
    """
    # Ensure season column exists
    if "season" not in all_games.columns:
        all_games = all_games.copy()
        all_games["season"] = all_games["date"].astype(str).apply(assign_season)

    seasons = sorted(all_games["season"].unique().tolist())
    tanking_thresholds = [0.250, 0.300, 0.350]

    # Capture output
    buffer = io.StringIO()
    original_stdout = sys.stdout
    sys.stdout = buffer

    try:
        for sig_id, sig in SIGNAL_CONDITIONS.items():
            is_control = sig_id == "C1"

            _print_separator(f"Signal {sig_id}: {sig['name']}", char="═")
            print()

            # ---- Full Season ----
            _print_separator("Full Season", char="─")
            _analyze_segment(all_games, seasons, sig, all_games, "full")
            print()

            if is_control:
                continue

            # ---- Pre-ASB ----
            _print_separator("Pre-All-Star Break", char="─")
            _analyze_segment(all_games, seasons, sig, all_games, "pre")
            print()

            # ---- Post-ASB ----
            _print_separator("Post-All-Star Break", char="─")
            _analyze_segment(all_games, seasons, sig, all_games, "post")
            print()

            # ---- Post-ASB with tanking filters ----
            for threshold in tanking_thresholds:
                label = f"Post-ASB (tank filter: win% >= {threshold:.3f})"
                _print_separator(label, char="·")
                _analyze_segment(
                    all_games, seasons, sig, all_games, "post",
                    tank_threshold=threshold,
                )
                print()

            _print_separator(char="═")
            print()

    finally:
        sys.stdout = original_stdout

    report = buffer.getvalue()

    # Write to file
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    # Also print to stdout (handle Windows encoding)
    try:
        print(report, end="")
    except UnicodeEncodeError:
        print(report.encode("ascii", errors="replace").decode("ascii"), end="")

    return output_path
