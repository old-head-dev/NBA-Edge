"""
pipeline.py — NBA Edge V3 pipeline orchestrator.

Wires together all stages: load, validate, schedule context, signal analysis.

Run from the backtest/ directory:
    python -m v3.pipeline

Stages:
  1.  Load data      (load_data.py)
  1b. Validate data  (validate_data.py)
  2.  Schedule ctx   (schedule.py)
  3.  Signal audit   (analyze.py)
"""

import os
import sys

import pandas as pd

from v3.load_data import load_kaggle, load_sbr
from v3.validate_data import quality_report, cross_reference
from v3.schedule import compute_schedule_context
from v3.analyze import assign_season, run_signal_analysis

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(__file__)
RAW_DIR = os.path.join(SCRIPT_DIR, "data", "raw")
OUT_DIR = os.path.join(SCRIPT_DIR, "data", "processed")

# Modern era seasons only. Excludes 2019-20 (COVID bubble) and 2020-21 (shortened).
VALID_SEASONS = {"2018-19", "2021-22", "2022-23", "2023-24", "2024-25"}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    # =========================================================================
    print("=" * 72)
    print("STAGE 1: Load Data")
    print("=" * 72)
    # =========================================================================

    kaggle_csv = os.path.join(RAW_DIR, "nba_2008-2025.csv")
    if not os.path.exists(kaggle_csv):
        print(f"ERROR: Missing data file: {kaggle_csv}")
        print("Download from: https://www.kaggle.com/datasets/wyattowalsh/basketball")
        print("  Expected file: nba_2008-2025.csv  →  place in backtest/v3/data/raw/")
        sys.exit(1)

    print(f"Loading Kaggle CSV: {kaggle_csv}")
    kaggle_df = load_kaggle("nba_2008-2025.csv")

    # Add season column via assign_season for any rows that are missing it,
    # but load_kaggle already derives 'season' from the Kaggle integer column.
    # Re-derive as a safety check using assign_season on the date column.
    kaggle_df["season"] = kaggle_df["date"].astype(str).apply(assign_season)

    total_before = len(kaggle_df)
    all_games = kaggle_df[kaggle_df["season"].isin(VALID_SEASONS)].copy()
    total_after = len(all_games)
    print(f"Games before season filter: {total_before}")
    print(f"Games after  season filter: {total_after}  (VALID_SEASONS: {sorted(VALID_SEASONS)})")

    # Optional: load SBR JSON if present (Kaggle-only mode if missing)
    sbr_path = os.path.join(RAW_DIR, "sbr_archive_10y.json")
    sbr_df = None
    if os.path.exists(sbr_path):
        print(f"\nLoading SBR JSON: {sbr_path}")
        try:
            sbr_df = load_sbr("sbr_archive_10y.json")
            print(f"SBR loaded: {len(sbr_df)} games")
        except Exception as exc:
            print(f"WARNING: SBR load failed ({exc}). Continuing in Kaggle-only mode.")
            sbr_df = None
    else:
        print(f"\nSBR JSON not found — running in Kaggle-only mode.")

    # =========================================================================
    print()
    print("=" * 72)
    print("STAGE 1b: Validate Data Quality")
    print("=" * 72)
    # =========================================================================

    report_text = quality_report(all_games, "Kaggle Primary")
    print(report_text)

    quality_report_path = os.path.join(OUT_DIR, "quality_report.txt")
    with open(quality_report_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    print(f"\nQuality report written: {quality_report_path}")

    if sbr_df is not None:
        print("\nRunning cross-reference (Kaggle vs SBR)...")
        discrepancies = cross_reference(all_games, sbr_df)
        if len(discrepancies) > 0:
            disc_path = os.path.join(OUT_DIR, "cross_reference_discrepancies.csv")
            discrepancies.to_csv(disc_path, index=False)
            print(f"Discrepancies saved: {disc_path}")
        else:
            print("No discrepancies found.")

    # =========================================================================
    print()
    print("=" * 72)
    print("STAGE 2: Compute Schedule Context")
    print("=" * 72)
    # =========================================================================

    enriched_frames = []

    for season in sorted(VALID_SEASONS):
        season_df = all_games[all_games["season"] == season].copy()
        season_df = season_df.sort_values("date").reset_index(drop=True)

        print(f"  Processing {season}: {len(season_df)} games...", end=" ")
        enriched = compute_schedule_context(season_df)
        print("done")

        out_path = os.path.join(OUT_DIR, f"full_season_{season}.csv")
        enriched.to_csv(out_path, index=False)
        enriched_frames.append(enriched)

    all_enriched = pd.concat(enriched_frames, ignore_index=True)
    print(f"\nAll seasons concatenated: {len(all_enriched)} games total")

    # =========================================================================
    print()
    print("=" * 72)
    print("STAGE 3: Signal Analysis")
    print("=" * 72)
    # =========================================================================

    audit_path = os.path.join(OUT_DIR, "signal_audit_report.txt")
    run_signal_analysis(all_enriched, audit_path)
    print(f"\nSignal audit report written: {audit_path}")

    # =========================================================================
    print()
    print("=" * 72)
    print("STAGE 4: Next Steps")
    print("=" * 72)
    # =========================================================================

    print("Review signal_audit_report.txt to identify promising signals.")
    print(f"  Location: {audit_path}")
    print()
    print("Then run validation with: python -m v3.validate_signals")

    # =========================================================================
    print()
    print("=" * 72)
    print(f"PIPELINE COMPLETE — outputs in: {OUT_DIR}")
    print("=" * 72)


if __name__ == "__main__":
    main()
