"""
validate_data.py — NBA Edge V3 data validation and quality checks.

Provides three public functions:
  - spot_check_game:  Verify a specific game's scores match expected values.
  - cross_reference:  Compare Kaggle and SBR DataFrames for discrepancies.
  - quality_report:   Generate a text summary of a dataset's completeness.

Column name conventions:
  DataFrames produced by load_data.py use 'home_team'/'away_team' and 'total'.
  This module also accepts 'home'/'away' and 'close_total' as aliases, handling
  both naming conventions transparently.

Run from the backtest/ directory:
    python -c "from v3.validate_data import quality_report; print('ok')"
"""

import pandas as pd


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _away_col(df: pd.DataFrame) -> str:
    """Return the away-team column name used in this DataFrame."""
    if "away" in df.columns:
        return "away"
    if "away_team" in df.columns:
        return "away_team"
    raise KeyError("DataFrame has neither 'away' nor 'away_team' column")


def _home_col(df: pd.DataFrame) -> str:
    """Return the home-team column name used in this DataFrame."""
    if "home" in df.columns:
        return "home"
    if "home_team" in df.columns:
        return "home_team"
    raise KeyError("DataFrame has neither 'home' nor 'home_team' column")


def _total_col(df: pd.DataFrame) -> str | None:
    """Return the total column name, or None if absent."""
    if "close_total" in df.columns:
        return "close_total"
    if "total" in df.columns:
        return "total"
    return None


# ---------------------------------------------------------------------------
# 1. spot_check_game
# ---------------------------------------------------------------------------

def spot_check_game(
    df: pd.DataFrame,
    date: str,
    away: str,
    home: str,
    expected_away_score: int,
    expected_home_score: int,
) -> dict:
    """Look up a specific game and verify its scores match expectations.

    Args:
        df: DataFrame with game records.
        date: Date string in any format pandas can parse (e.g. "2023-01-15").
        away: Away team abbreviation (e.g. "BOS").
        home: Home team abbreviation (e.g. "LAL").
        expected_away_score: Expected final score for the away team.
        expected_home_score: Expected final score for the home team.

    Returns:
        dict with keys:
          - pass (bool): True if both scores match exactly.
          - expected_away_score, expected_home_score: what was provided.
          - actual_away_score, actual_home_score: what is in the data.
          - home_spread (float|None): closing spread from the data.
          - total (float|None): closing total from the data.
          - error (str): present only when game is not found or columns missing.
    """
    try:
        away_col = _away_col(df)
        home_col = _home_col(df)
    except KeyError as e:
        return {"pass": False, "error": str(e)}

    try:
        target_date = pd.to_datetime(date)
    except Exception:
        return {"pass": False, "error": f"unparseable date: {date!r}"}

    # Normalise df dates to date-only for comparison
    df_dates = pd.to_datetime(df["date"]).dt.normalize()

    mask = (
        (df_dates == target_date)
        & (df[away_col].str.upper() == away.upper())
        & (df[home_col].str.upper() == home.upper())
    )
    matches = df[mask]

    if matches.empty:
        return {
            "pass": False,
            "error": (
                f"game not found: {away} @ {home} on {target_date.date()}"
            ),
        }

    row = matches.iloc[0]
    actual_away = row.get("away_score")
    actual_home = row.get("home_score")

    # Coerce pandas NA/NaN to None
    actual_away = None if pd.isna(actual_away) else int(actual_away)
    actual_home = None if pd.isna(actual_home) else int(actual_home)

    spread_val = None
    if "home_spread" in df.columns:
        v = row.get("home_spread")
        spread_val = None if pd.isna(v) else float(v)

    total_col = _total_col(df)
    total_val = None
    if total_col is not None:
        v = row.get(total_col)
        total_val = None if pd.isna(v) else float(v)

    scores_match = (actual_away == expected_away_score) and (
        actual_home == expected_home_score
    )

    return {
        "pass": scores_match,
        "expected_away_score": expected_away_score,
        "expected_home_score": expected_home_score,
        "actual_away_score": actual_away,
        "actual_home_score": actual_home,
        "home_spread": spread_val,
        "total": total_val,
    }


# ---------------------------------------------------------------------------
# 2. cross_reference
# ---------------------------------------------------------------------------

def cross_reference(kaggle_df: pd.DataFrame, sbr_df: pd.DataFrame) -> pd.DataFrame:
    """Merge Kaggle and SBR data and flag discrepancies.

    Matches records on date + away team + home team.  Compares:
      - away_score and home_score (any difference is flagged)
      - home_spread  (flagged when |kaggle - sbr| > 0.5)

    Prints:
        "Cross-reference: X matching games, Y discrepancies"

    Args:
        kaggle_df: DataFrame from load_kaggle().
        sbr_df:    DataFrame from load_sbr().

    Returns:
        pd.DataFrame of discrepant rows with columns:
          date, away, home,
          away_score_kaggle, away_score_sbr,
          home_score_kaggle, home_score_sbr,
          home_spread_kaggle, home_spread_sbr,
          score_mismatch (bool), spread_diff (float|None),
          spread_mismatch (bool).
        Empty DataFrame if no discrepancies.
    """
    # ---- Normalise column names to a common schema -------------------------
    def _prep(df: pd.DataFrame, label: str) -> pd.DataFrame:
        out = df.copy()
        # Ensure 'away' and 'home' columns exist (rename from *_team if needed)
        if "away" not in out.columns and "away_team" in out.columns:
            out = out.rename(columns={"away_team": "away"})
        if "home" not in out.columns and "home_team" in out.columns:
            out = out.rename(columns={"home_team": "home"})
        # Normalise date to date-only
        out["date"] = pd.to_datetime(out["date"]).dt.normalize()
        # Keep only the columns we care about
        keep = ["date", "away", "home", "away_score", "home_score"]
        if "home_spread" in out.columns:
            keep.append("home_spread")
        out = out[keep].copy()
        # Suffix so merging produces unambiguous column names
        rename = {
            "away_score": f"away_score_{label}",
            "home_score": f"home_score_{label}",
        }
        if "home_spread" in keep:
            rename["home_spread"] = f"home_spread_{label}"
        out = out.rename(columns=rename)
        return out

    kdf = _prep(kaggle_df, "kaggle")
    sdf = _prep(sbr_df, "sbr")

    merged = kdf.merge(sdf, on=["date", "away", "home"], how="inner")
    total_matching = len(merged)

    if total_matching == 0:
        print("Cross-reference: 0 matching games, 0 discrepancies")
        return pd.DataFrame()

    # ---- Score comparison --------------------------------------------------
    def _scores_match(row) -> bool:
        try:
            away_ok = int(row["away_score_kaggle"]) == int(row["away_score_sbr"])
            home_ok = int(row["home_score_kaggle"]) == int(row["home_score_sbr"])
            return away_ok and home_ok
        except (TypeError, ValueError):
            # If either score is None/NaN the scores cannot be confirmed equal
            return False

    merged["score_mismatch"] = ~merged.apply(_scores_match, axis=1)

    # ---- Spread comparison -------------------------------------------------
    has_kaggle_spread = "home_spread_kaggle" in merged.columns
    has_sbr_spread = "home_spread_sbr" in merged.columns

    if has_kaggle_spread and has_sbr_spread:
        def _spread_diff(row) -> float | None:
            try:
                k = float(row["home_spread_kaggle"])
                s = float(row["home_spread_sbr"])
                return abs(k - s)
            except (TypeError, ValueError):
                return None

        merged["spread_diff"] = merged.apply(_spread_diff, axis=1)
        merged["spread_mismatch"] = merged["spread_diff"].apply(
            lambda d: bool(d is not None and d > 0.5)
        )
    else:
        merged["spread_diff"] = None
        merged["spread_mismatch"] = False

    # ---- Filter to discrepancies ------------------------------------------
    discrepancies = merged[
        merged["score_mismatch"] | merged["spread_mismatch"]
    ].copy()

    print(
        f"Cross-reference: {total_matching} matching games, "
        f"{len(discrepancies)} discrepancies"
    )
    return discrepancies.reset_index(drop=True)


# ---------------------------------------------------------------------------
# 3. quality_report
# ---------------------------------------------------------------------------

def quality_report(df: pd.DataFrame, label: str) -> str:
    """Generate a text quality report for a dataset.

    Reports:
      - Total games
      - Date range (min → max)
      - Unique teams (sorted)
      - Missing spreads count and percentage
      - Missing totals count and percentage
      - Missing scores count (games where either team score is absent)
      - Games per season breakdown

    Args:
        df:    DataFrame with game records.
        label: Short identifier printed in the report header (e.g. "kaggle").

    Returns:
        The full report as a string (also suitable for printing).
    """
    lines: list[str] = []
    total = len(df)

    lines.append(f"=== Quality Report: {label} ===")
    lines.append(f"Total games : {total}")

    if total == 0:
        lines.append("(no records)")
        return "\n".join(lines)

    # Date range
    dates = pd.to_datetime(df["date"])
    lines.append(f"Date range  : {dates.min().date()} to {dates.max().date()}")

    # Unique teams
    away_col = _away_col(df)
    home_col = _home_col(df)
    teams = sorted(
        set(df[away_col].dropna().unique()) | set(df[home_col].dropna().unique())
    )
    lines.append(f"Unique teams: {len(teams)}")
    lines.append(f"  {', '.join(teams)}")

    # Missing spreads
    if "home_spread" in df.columns:
        missing_spread = int(df["home_spread"].isna().sum())
        pct_spread = missing_spread / total * 100
        lines.append(
            f"Missing spreads : {missing_spread} / {total} ({pct_spread:.1f}%)"
        )
    else:
        lines.append("Missing spreads : column absent")

    # Missing totals
    total_col = _total_col(df)
    if total_col is not None:
        missing_total = int(df[total_col].isna().sum())
        pct_total = missing_total / total * 100
        lines.append(
            f"Missing totals  : {missing_total} / {total} ({pct_total:.1f}%)"
        )
    else:
        lines.append("Missing totals  : column absent")

    # Missing scores (either score missing)
    if "away_score" in df.columns and "home_score" in df.columns:
        missing_scores = int(
            (df["away_score"].isna() | df["home_score"].isna()).sum()
        )
        lines.append(f"Missing scores  : {missing_scores}")
    else:
        lines.append("Missing scores  : column absent")

    # Games per season
    if "season" in df.columns:
        lines.append("Games per season:")
        per_season = (
            df.groupby("season", sort=True)
            .size()
            .reset_index(name="count")
        )
        for _, row in per_season.iterrows():
            lines.append(f"  {row['season']}: {row['count']}")
    else:
        lines.append("Games per season: 'season' column absent")

    return "\n".join(lines)
