"""
schedule.py — NBA schedule context engine.

Replaces V2's arbitrary fatigue scoring with simple binary flags and
continuous variables derived from actual schedule data.

Run from the backtest/ directory:
    python -m pytest v3/tests/test_schedule.py -v
"""

from __future__ import annotations

import math
from typing import Optional

import pandas as pd

from v3.arenas import ARENAS, ALTITUDE_ARENAS, haversine_miles

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_TIP_HOUR_ET: float = 19.5  # 7:30pm ET when tip time unavailable


# ---------------------------------------------------------------------------
# Private helper functions
# ---------------------------------------------------------------------------

def _get_tip_hour_et(row) -> float:
    """Extract tip time in ET hours from a game row.

    If the date has hour > 0 (timestamp includes time), use it directly as ET
    hours. Otherwise return DEFAULT_TIP_HOUR_ET.
    """
    ts = row["date"]
    if hasattr(ts, "hour") and ts.hour > 0:
        return float(ts.hour) + float(ts.minute) / 60.0
    return DEFAULT_TIP_HOUR_ET


def _estimate_sleep(
    prev_arena: str,
    curr_arena: str,
    prev_tip_et: float,
) -> Optional[float]:
    """Estimate sleep hours for a traveling B2B team.

    Formula:
    - Game ends       = prev_tip_et + 2.5 hrs
    - Post-game dep.  = game_end + 2.5 hrs  = prev_tip_et + 5.0
    - Flight time     = haversine_miles(prev, curr) / 500 mph
    - Hotel arrival   = departure_et + flight_hrs + 0.75 (tarmac → hotel)
    - Wake-up         = 10am LOCAL at game venue, converted to ET:
                        wakeup_et = 10.0 - (curr_tz - (-5)) + 24.0
    - Sleep           = max(0, wakeup_et - hotel_arrival_et), capped at 12 hrs

    Returns hours rounded to 1 decimal, or None if prev_arena == curr_arena.
    """
    if prev_arena not in ARENAS or curr_arena not in ARENAS:
        return None

    prev = ARENAS[prev_arena]
    curr = ARENAS[curr_arena]

    # Flight distance and time
    dist_miles = haversine_miles(prev["lat"], prev["lon"], curr["lat"], curr["lon"])
    flight_hrs = dist_miles / 500.0

    # Departure and hotel arrival (all in ET)
    departure_et = prev_tip_et + 5.0
    hotel_arrival_et = departure_et + flight_hrs + 0.75

    # Wake-up at 10am LOCAL converted to ET
    curr_tz = curr["tz"]  # e.g. -8 for PT, -5 for ET
    wakeup_et = 10.0 - (curr_tz - (-5)) + 24.0

    sleep_hrs = max(0.0, wakeup_et - hotel_arrival_et)
    sleep_hrs = min(sleep_hrs, 12.0)
    return round(sleep_hrs, 1)


def _estimate_sleep_home_home(prev_tip_et: float, home_team: str) -> float:
    """Estimate sleep for a home team playing B2B at their own arena.

    Formula:
    - Bed time  = prev_tip_et + 5.0
    - Wake-up   = 10am LOCAL at home arena, converted to ET:
                  wakeup_et = 10.0 - (home_tz - (-5)) + 24.0
    - Sleep     = max(0, wakeup_et - bed_time), capped at 12 hrs
    """
    home_tz = ARENAS[home_team]["tz"]
    bed_time_et = prev_tip_et + 5.0
    wakeup_et = 10.0 - (home_tz - (-5)) + 24.0

    sleep_hrs = max(0.0, wakeup_et - bed_time_et)
    sleep_hrs = min(sleep_hrs, 12.0)
    return round(sleep_hrs, 1)


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------

def compute_schedule_context(games_df: pd.DataFrame) -> pd.DataFrame:
    """Compute per-game schedule context for both teams.

    Takes a season DataFrame sorted by date with columns:
        date, away, home, away_score, home_score,
        home_spread, close_total, ats_result, ou_result

    Returns the same DataFrame augmented with schedule context columns for
    both the away and home team (prefixed away_ / home_), plus home_is_altitude.

    Column descriptions:
        {prefix}_days_rest    int|None   Calendar days since last game minus 1
        {prefix}_b2b          bool       True if days_rest == 0
        {prefix}_traveled     bool       Previous game was at a different arena
        {prefix}_travel_dist  float      Haversine miles from previous arena (0 if none)
        {prefix}_est_sleep    float|None Sleep hours (B2B only)
        {prefix}_tz_change    int        Timezone delta from previous arena (+ = east)
        {prefix}_3in4         bool       3rd+ game in 4 calendar days
        {prefix}_4in6         bool       4th+ game in 6 calendar days
        {prefix}_at_altitude  bool       Away team at DEN/UTA without recent altitude
        {prefix}_win_pct      float      Cumulative season win% entering this game
        home_is_altitude      bool       Game venue is DEN or UTA
    """
    # Work on a copy; we'll collect output rows and join at the end
    df = games_df.reset_index(drop=True)

    # Per-team state: list of {date, arena, tip_et, is_home}
    team_history: dict[str, list[dict]] = {}
    # Per-team win/loss record: {team: [wins, total]}
    team_record: dict[str, list[int]] = {}

    output_rows = []

    for idx, row in df.iterrows():
        away = row["away"]
        home = row["home"]
        game_date = row["date"]
        tip_et = _get_tip_hour_et(row)

        # Home team arena for this game
        # The game is ALWAYS played at the home team's arena
        arena_tonight = home

        ctx = {}

        for team, prefix, is_home in [(away, "away", False), (home, "home", True)]:
            history = team_history.get(team, [])

            # ---- days_rest ----
            # Use date-only subtraction to ignore intra-day time components
            game_date_only = game_date.normalize()
            if not history:
                days_rest = None
            else:
                last_date_only = history[-1]["date"].normalize()
                delta = (game_date_only - last_date_only).days
                days_rest = delta - 1  # 0 = B2B

            ctx[f"{prefix}_days_rest"] = days_rest

            # ---- b2b ----
            b2b = bool(days_rest == 0)
            ctx[f"{prefix}_b2b"] = b2b

            # ---- traveled ----
            if not history:
                traveled = False
                prev_arena = None
            else:
                prev_arena = history[-1]["arena"]
                traveled = bool(prev_arena != arena_tonight)
            ctx[f"{prefix}_traveled"] = traveled

            # ---- travel_dist ----
            if not history or not traveled:
                travel_dist = 0.0
            else:
                p = ARENAS[prev_arena]
                c = ARENAS[arena_tonight]
                travel_dist = haversine_miles(p["lat"], p["lon"], c["lat"], c["lon"])
            ctx[f"{prefix}_travel_dist"] = travel_dist

            # ---- est_sleep ----
            if not b2b:
                est_sleep = None
            elif not history:
                est_sleep = None
            elif not traveled:
                # Home-home B2B: stayed at same arena
                prev_tip_et = history[-1]["tip_et"]
                est_sleep = _estimate_sleep_home_home(prev_tip_et, arena_tonight)
            else:
                # Traveling B2B
                prev_tip_et = history[-1]["tip_et"]
                est_sleep = _estimate_sleep(prev_arena, arena_tonight, prev_tip_et)
            ctx[f"{prefix}_est_sleep"] = est_sleep

            # ---- tz_change ----
            if not history or not traveled:
                tz_change = 0
            else:
                prev_tz = ARENAS[prev_arena]["tz"]
                curr_tz = ARENAS[arena_tonight]["tz"]
                tz_change = curr_tz - prev_tz  # + = moved east, - = moved west
            ctx[f"{prefix}_tz_change"] = tz_change

            # ---- schedule density (3in4, 4in6) ----
            # Count games in the window INCLUDING the current game.
            # "3 games in 4 calendar days" means current + 2 previous within 3-day lookback.
            # Window: >= (today - 3) means today, today-1, today-2, today-3 = 4 days inclusive.
            window_3in4 = game_date_only - pd.Timedelta(days=3)
            window_4in6 = game_date_only - pd.Timedelta(days=5)

            # Count prior games within window (current game is always included → +1)
            count_3 = sum(
                1 for h in history if h["date"].normalize() >= window_3in4
            ) + 1
            count_4 = sum(
                1 for h in history if h["date"].normalize() >= window_4in6
            ) + 1

            ctx[f"{prefix}_3in4"] = bool(count_3 >= 3)
            ctx[f"{prefix}_4in6"] = bool(count_4 >= 4)

            # ---- at_altitude ----
            # Only for away team, only at DEN/UTA, only if no altitude game in past 4 days
            if is_home:
                ctx[f"{prefix}_at_altitude"] = False
            elif arena_tonight not in ALTITUDE_ARENAS:
                ctx[f"{prefix}_at_altitude"] = False
            else:
                # Check if any of team's recent games (past 4 calendar days) were at altitude
                cutoff = game_date_only - pd.Timedelta(days=4)
                recent_altitude = any(
                    h["arena"] in ALTITUDE_ARENAS and h["date"].normalize() > cutoff
                    for h in history
                )
                ctx[f"{prefix}_at_altitude"] = bool(not recent_altitude)

            # ---- win_pct ----
            record = team_record.get(team, [0, 0])
            wins, total = record
            if total == 0:
                win_pct = 0.5
            else:
                win_pct = wins / total
            ctx[f"{prefix}_win_pct"] = win_pct

        # ---- home_is_altitude ----
        ctx["home_is_altitude"] = bool(arena_tonight in ALTITUDE_ARENAS)

        output_rows.append(ctx)

        # ---- Update team histories AFTER computing ----
        away_score = row.get("away_score", None)
        home_score = row.get("home_score", None)

        for team, is_home in [(away, False), (home, True)]:
            if team not in team_history:
                team_history[team] = []
            if team not in team_record:
                team_record[team] = [0, 0]

            team_history[team].append({
                "date": game_date,
                "arena": arena_tonight,
                "tip_et": tip_et,
                "is_home": is_home,
            })

            # Update win/loss record
            if away_score is not None and home_score is not None:
                try:
                    a = float(away_score)
                    h = float(home_score)
                    if not (math.isnan(a) or math.isnan(h)):
                        won = (a > h and not is_home) or (h > a and is_home)
                        team_record[team][1] += 1  # total
                        if won:
                            team_record[team][0] += 1  # wins
                except (TypeError, ValueError):
                    pass

    # Build output DataFrame
    ctx_df = pd.DataFrame(output_rows, index=df.index)

    # Merge context columns into original df
    result = pd.concat([df, ctx_df], axis=1)
    return result
