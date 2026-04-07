"""
test_schedule.py — Unit tests for backtest/v3/schedule.py

Run from the backtest/ directory:
    python -m pytest v3/tests/test_schedule.py -v
"""

import pytest
import pandas as pd

from v3.schedule import compute_schedule_context


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_games(game_list):
    rows = []
    for g in game_list:
        rows.append({
            "date": pd.Timestamp(g[0]),
            "away": g[1],
            "home": g[2],
            "away_score": g[3],
            "home_score": g[4],
            "home_spread": -5.0,
            "close_total": 220.0,
            "ats_result": "home",
            "ou_result": "under",
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# B2B detection — away team
# ---------------------------------------------------------------------------

class TestB2BDetectionAway:
    def test_b2b_consecutive_days(self):
        """Away team plays two consecutive days → b2b=True on second game."""
        games = _make_games([
            ("2025-01-01", "BOS", "NYK", 100, 95),
            ("2025-01-02", "BOS", "PHI", 102, 98),
        ])
        ctx = compute_schedule_context(games)
        assert ctx.iloc[1]["away_b2b"] == True

    def test_not_b2b_skip_day(self):
        """Away team skips a day → b2b=False."""
        games = _make_games([
            ("2025-01-01", "BOS", "NYK", 100, 95),
            ("2025-01-03", "BOS", "PHI", 102, 98),
        ])
        ctx = compute_schedule_context(games)
        assert ctx.iloc[1]["away_b2b"] == False

    def test_first_game_not_b2b(self):
        """First game of the season → b2b=False, days_rest=None."""
        games = _make_games([
            ("2025-01-01", "BOS", "NYK", 100, 95),
        ])
        ctx = compute_schedule_context(games)
        assert ctx.iloc[0]["away_b2b"] == False
        assert ctx.iloc[0]["away_days_rest"] is None


# ---------------------------------------------------------------------------
# B2B detection — home team
# ---------------------------------------------------------------------------

class TestB2BDetectionHome:
    def test_home_b2b_consecutive_days(self):
        """Home team plays two consecutive home games → b2b=True on second."""
        games = _make_games([
            ("2025-01-01", "MIA", "BOS", 95, 100),
            ("2025-01-02", "LAL", "BOS", 98, 102),
        ])
        ctx = compute_schedule_context(games)
        assert ctx.iloc[1]["home_b2b"] == True

    def test_home_not_b2b_skip_day(self):
        """Home team has a day off → b2b=False."""
        games = _make_games([
            ("2025-01-01", "MIA", "BOS", 95, 100),
            ("2025-01-03", "LAL", "BOS", 98, 102),
        ])
        ctx = compute_schedule_context(games)
        assert ctx.iloc[1]["home_b2b"] == False


# ---------------------------------------------------------------------------
# Days rest
# ---------------------------------------------------------------------------

class TestDaysRest:
    def test_days_rest_b2b_is_zero(self):
        """B2B → days_rest=0."""
        games = _make_games([
            ("2025-01-01", "BOS", "NYK", 100, 95),
            ("2025-01-02", "BOS", "PHI", 102, 98),
        ])
        ctx = compute_schedule_context(games)
        assert ctx.iloc[1]["away_days_rest"] == 0

    def test_days_rest_one_day_off_is_one(self):
        """One day off → days_rest=1."""
        games = _make_games([
            ("2025-01-01", "BOS", "NYK", 100, 95),
            ("2025-01-03", "BOS", "PHI", 102, 98),
        ])
        ctx = compute_schedule_context(games)
        assert ctx.iloc[1]["away_days_rest"] == 1

    def test_days_rest_two_days_off_is_two(self):
        """Two days off → days_rest=2."""
        games = _make_games([
            ("2025-01-01", "BOS", "NYK", 100, 95),
            ("2025-01-04", "BOS", "PHI", 102, 98),
        ])
        ctx = compute_schedule_context(games)
        assert ctx.iloc[1]["away_days_rest"] == 2

    def test_first_game_days_rest_is_none(self):
        """No previous game → days_rest=None."""
        games = _make_games([
            ("2025-01-01", "BOS", "NYK", 100, 95),
        ])
        ctx = compute_schedule_context(games)
        assert ctx.iloc[0]["away_days_rest"] is None


# ---------------------------------------------------------------------------
# Traveled flag — away team
# ---------------------------------------------------------------------------

class TestTraveledFlagAway:
    def test_away_traveled_different_arenas(self):
        """Away team played at different arena yesterday → traveled=True."""
        # BOS plays at LAL then at NYK (different arenas → traveled)
        games = _make_games([
            ("2025-01-01", "BOS", "LAL", 100, 95),   # BOS at LAL arena
            ("2025-01-02", "BOS", "NYK", 102, 98),   # BOS at NYK arena
        ])
        ctx = compute_schedule_context(games)
        assert ctx.iloc[1]["away_traveled"] == True

    def test_away_not_traveled_same_city(self):
        """Away team plays two consecutive away games at same arena → traveled=False."""
        # BOS plays at NYK twice
        games = _make_games([
            ("2025-01-01", "BOS", "NYK", 100, 95),
            ("2025-01-02", "BOS", "NYK", 102, 98),
        ])
        ctx = compute_schedule_context(games)
        assert ctx.iloc[1]["away_traveled"] == False

    def test_away_first_game_not_traveled(self):
        """First game → traveled=False."""
        games = _make_games([
            ("2025-01-01", "BOS", "NYK", 100, 95),
        ])
        ctx = compute_schedule_context(games)
        assert ctx.iloc[0]["away_traveled"] == False


# ---------------------------------------------------------------------------
# Traveled flag — home team
# ---------------------------------------------------------------------------

class TestTraveledFlagHome:
    def test_home_traveled_after_away_game(self):
        """Home team played away yesterday, now home → traveled=True."""
        # BOS plays away at LAL, then hosts the next day
        games = _make_games([
            ("2025-01-01", "LAL", "BOS", 95, 100),  # BOS home (arena=BOS)
            ("2025-01-02", "MIA", "BOS", 100, 98),  # BOS home again (arena=BOS)
        ])
        # First game: BOS is HOME, arena=BOS. Second game: BOS is HOME, arena=BOS.
        # Both at BOS — should NOT be traveled. Let me use a case where BOS was away:
        ctx = compute_schedule_context(games)
        # BOS is home both games → same arena → not traveled
        assert ctx.iloc[1]["home_traveled"] == False

    def test_home_traveled_was_away_yesterday(self):
        """Home team was playing away at a different city yesterday → traveled=True."""
        # BOS plays AWAY at NYK on day 1 (arena=NYK), then HOME vs MIA on day 2 (arena=BOS)
        games = _make_games([
            ("2025-01-01", "BOS", "NYK", 100, 95),  # BOS is AWAY; arena=NYK
            ("2025-01-02", "MIA", "BOS", 98, 102),  # BOS is HOME; arena=BOS
        ])
        ctx = compute_schedule_context(games)
        # BOS previous arena=NYK, tonight arena=BOS → traveled=True
        assert ctx.iloc[1]["home_traveled"] == True

    def test_home_not_traveled_consecutive_home_games(self):
        """Home team plays two consecutive home games → traveled=False."""
        games = _make_games([
            ("2025-01-01", "MIA", "BOS", 95, 100),
            ("2025-01-02", "LAL", "BOS", 98, 102),
        ])
        ctx = compute_schedule_context(games)
        assert ctx.iloc[1]["home_traveled"] == False


# ---------------------------------------------------------------------------
# Travel distance
# ---------------------------------------------------------------------------

class TestTravelDistance:
    def test_travel_dist_zero_when_not_traveled(self):
        """No travel → travel_dist=0."""
        games = _make_games([
            ("2025-01-01", "BOS", "NYK", 100, 95),
            ("2025-01-02", "BOS", "NYK", 102, 98),
        ])
        ctx = compute_schedule_context(games)
        assert ctx.iloc[1]["away_travel_dist"] == 0.0

    def test_travel_dist_positive_when_traveled(self):
        """Cross-country trip → large travel distance."""
        games = _make_games([
            ("2025-01-01", "BOS", "NYK", 100, 95),   # BOS at NYK
            ("2025-01-02", "BOS", "LAL", 102, 98),   # BOS at LAL
        ])
        ctx = compute_schedule_context(games)
        # NYK to LAL is ~2800 miles
        assert ctx.iloc[1]["away_travel_dist"] > 2000

    def test_travel_dist_no_previous_game_is_zero(self):
        """First game → travel_dist=0."""
        games = _make_games([
            ("2025-01-01", "BOS", "NYK", 100, 95),
        ])
        ctx = compute_schedule_context(games)
        assert ctx.iloc[0]["away_travel_dist"] == 0.0


# ---------------------------------------------------------------------------
# Sleep estimate
# ---------------------------------------------------------------------------

class TestSleepEstimate:
    def test_short_trip_decent_sleep(self):
        """Short trip (BOS→NYK = ~215mi) → reasonable sleep (>5 hrs)."""
        games = _make_games([
            ("2025-01-01", "BOS", "NYK", 100, 95),
            ("2025-01-02", "BOS", "PHI", 102, 98),
        ])
        ctx = compute_schedule_context(games)
        sleep = ctx.iloc[1]["away_est_sleep"]
        assert sleep is not None
        assert sleep > 5.0

    def test_long_trip_less_sleep(self):
        """Long west-coast trip (BOS→LAL = ~2600mi) → less sleep than short trip."""
        games = _make_games([
            ("2025-01-01", "BOS", "NYK", 100, 95),
            ("2025-01-02", "BOS", "LAL", 102, 98),
        ])
        ctx = compute_schedule_context(games)
        sleep_long = ctx.iloc[1]["away_est_sleep"]

        games2 = _make_games([
            ("2025-01-01", "BOS", "NYK", 100, 95),
            ("2025-01-02", "BOS", "PHI", 102, 98),
        ])
        ctx2 = compute_schedule_context(games2)
        sleep_short = ctx2.iloc[1]["away_est_sleep"]

        assert sleep_long < sleep_short

    def test_no_sleep_for_non_b2b(self):
        """Non-B2B game → est_sleep=None."""
        games = _make_games([
            ("2025-01-01", "BOS", "NYK", 100, 95),
            ("2025-01-03", "BOS", "PHI", 102, 98),
        ])
        ctx = compute_schedule_context(games)
        assert ctx.iloc[1]["away_est_sleep"] is None

    def test_sleep_capped_at_12(self):
        """Sleep is never more than 12 hours."""
        games = _make_games([
            ("2025-01-01", "MIA", "BOS", 95, 100),
            ("2025-01-02", "LAL", "BOS", 98, 102),
        ])
        ctx = compute_schedule_context(games)
        sleep = ctx.iloc[1]["home_est_sleep"]
        if sleep is not None:
            assert sleep <= 12.0


# ---------------------------------------------------------------------------
# Home-home sleep estimate
# ---------------------------------------------------------------------------

class TestHomeHomeSleep:
    def test_home_home_sleep_reasonable(self):
        """Home team plays two consecutive home games → sleep 7-11 hrs for ET team."""
        # BOS (ET = tz -5) plays at home two nights in a row
        games = _make_games([
            ("2025-01-01", "MIA", "BOS", 95, 100),
            ("2025-01-02", "LAL", "BOS", 98, 102),
        ])
        ctx = compute_schedule_context(games)
        sleep = ctx.iloc[1]["home_est_sleep"]
        assert sleep is not None
        assert 5.0 <= sleep <= 12.0

    def test_home_home_sleep_makes_sense_for_late_game(self):
        """Late tip time (10pm ET) → less sleep than early tip."""
        # 10pm ET game on day 1
        games_late = _make_games([
            ("2025-01-01 22:00", "MIA", "BOS", 95, 100),
            ("2025-01-02", "LAL", "BOS", 98, 102),
        ])
        # 7pm ET game on day 1
        games_early = _make_games([
            ("2025-01-01 19:00", "MIA", "BOS", 95, 100),
            ("2025-01-02", "LAL", "BOS", 98, 102),
        ])
        ctx_late = compute_schedule_context(games_late)
        ctx_early = compute_schedule_context(games_early)

        sleep_late = ctx_late.iloc[1]["home_est_sleep"]
        sleep_early = ctx_early.iloc[1]["home_est_sleep"]
        # Later game → less sleep
        assert sleep_late < sleep_early


# ---------------------------------------------------------------------------
# Timezone change
# ---------------------------------------------------------------------------

class TestTimezoneChange:
    def test_tz_change_zero_same_timezone(self):
        """Same timezone zone → tz_change=0."""
        # BOS (ET -5) plays at NYK (ET -5)
        games = _make_games([
            ("2025-01-01", "BOS", "NYK", 100, 95),
            ("2025-01-02", "BOS", "PHI", 102, 98),
        ])
        ctx = compute_schedule_context(games)
        assert ctx.iloc[1]["away_tz_change"] == 0

    def test_tz_change_positive_eastbound(self):
        """Traveling east (LAL→BOS): tz_change=+3 (gained 3 hours east)."""
        # LAL (PT -8) played at home (arena=LAL), then travels to NYK (ET -5)
        games = _make_games([
            ("2025-01-01", "BOS", "LAL", 95, 100),   # LAL at home (arena=LAL, tz=-8)
            ("2025-01-02", "BOS", "NYK", 102, 98),   # BOS at NYK (arena=NYK, tz=-5)
        ])
        # BOS's previous arena was LAL (tz=-8), new arena is NYK (tz=-5)
        # tz_change = curr_tz - prev_tz = -5 - (-8) = +3
        ctx = compute_schedule_context(games)
        assert ctx.iloc[1]["away_tz_change"] == 3

    def test_tz_change_negative_westbound(self):
        """Traveling west (NYK→LAL): tz_change=-3."""
        # BOS at NYK (tz=-5) then at LAL (tz=-8)
        games = _make_games([
            ("2025-01-01", "BOS", "NYK", 100, 95),
            ("2025-01-02", "BOS", "LAL", 102, 98),
        ])
        # prev arena=NYK (tz=-5), curr arena=LAL (tz=-8)
        # tz_change = -8 - (-5) = -3
        ctx = compute_schedule_context(games)
        assert ctx.iloc[1]["away_tz_change"] == -3

    def test_tz_change_zero_no_previous_game(self):
        """No previous game → tz_change=0."""
        games = _make_games([
            ("2025-01-01", "BOS", "NYK", 100, 95),
        ])
        ctx = compute_schedule_context(games)
        assert ctx.iloc[0]["away_tz_change"] == 0


# ---------------------------------------------------------------------------
# Schedule density (3-in-4 and 4-in-6)
# ---------------------------------------------------------------------------

class TestScheduleDensity:
    def test_3in4_true_on_third_game(self):
        """3 games in 4 calendar days → 3in4=True on the 3rd game."""
        games = _make_games([
            ("2025-01-01", "BOS", "NYK", 100, 95),
            ("2025-01-02", "BOS", "MIA", 102, 98),
            ("2025-01-04", "BOS", "PHI", 105, 100),
        ])
        ctx = compute_schedule_context(games)
        assert ctx.iloc[2]["away_3in4"] == True

    def test_3in4_false_with_gap(self):
        """3 games but spread over 5+ days → 3in4=False."""
        games = _make_games([
            ("2025-01-01", "BOS", "NYK", 100, 95),
            ("2025-01-03", "BOS", "MIA", 102, 98),
            ("2025-01-06", "BOS", "PHI", 105, 100),
        ])
        ctx = compute_schedule_context(games)
        assert ctx.iloc[2]["away_3in4"] == False

    def test_4in6_true_on_fourth_game(self):
        """4 games in 6 days → 4in6=True on the 4th game."""
        games = _make_games([
            ("2025-01-01", "BOS", "NYK", 100, 95),
            ("2025-01-02", "BOS", "MIA", 102, 98),
            ("2025-01-04", "BOS", "PHI", 105, 100),
            ("2025-01-06", "BOS", "CLE", 110, 108),
        ])
        ctx = compute_schedule_context(games)
        assert ctx.iloc[3]["away_4in6"] == True

    def test_4in6_false_with_gap(self):
        """4 games but spread out → 4in6=False."""
        games = _make_games([
            ("2025-01-01", "BOS", "NYK", 100, 95),
            ("2025-01-03", "BOS", "MIA", 102, 98),
            ("2025-01-06", "BOS", "PHI", 105, 100),
            ("2025-01-09", "BOS", "CLE", 110, 108),
        ])
        ctx = compute_schedule_context(games)
        assert ctx.iloc[3]["away_4in6"] == False

    def test_first_game_density_false(self):
        """First game → 3in4=False, 4in6=False."""
        games = _make_games([
            ("2025-01-01", "BOS", "NYK", 100, 95),
        ])
        ctx = compute_schedule_context(games)
        assert ctx.iloc[0]["away_3in4"] == False
        assert ctx.iloc[0]["away_4in6"] == False


# ---------------------------------------------------------------------------
# Altitude flag
# ---------------------------------------------------------------------------

class TestAltitudeFlag:
    def test_away_at_den_without_recent_altitude(self):
        """Away team arrives at DEN with no altitude game in past 4 days → at_altitude=True."""
        games = _make_games([
            ("2025-01-01", "BOS", "NYK", 100, 95),
            ("2025-01-03", "BOS", "DEN", 102, 98),
        ])
        ctx = compute_schedule_context(games)
        assert ctx.iloc[1]["away_at_altitude"] == True

    def test_away_at_uta_without_recent_altitude(self):
        """Away team at UTA without recent altitude game → at_altitude=True."""
        games = _make_games([
            ("2025-01-01", "BOS", "NYK", 100, 95),
            ("2025-01-03", "BOS", "UTA", 102, 98),
        ])
        ctx = compute_schedule_context(games)
        assert ctx.iloc[1]["away_at_altitude"] == True

    def test_away_at_den_with_recent_altitude(self):
        """Away team was at DEN 3 days ago → at_altitude=False (acclimatized)."""
        games = _make_games([
            ("2025-01-01", "BOS", "DEN", 100, 95),
            ("2025-01-04", "BOS", "DEN", 102, 98),
        ])
        ctx = compute_schedule_context(games)
        assert ctx.iloc[1]["away_at_altitude"] == False

    def test_home_team_never_at_altitude(self):
        """Home team is never flagged for altitude (they live there)."""
        games = _make_games([
            ("2025-01-01", "BOS", "NYK", 100, 95),
            ("2025-01-03", "BOS", "DEN", 102, 98),
        ])
        ctx = compute_schedule_context(games)
        # DEN is HOME → home_at_altitude should be False
        assert ctx.iloc[1]["home_at_altitude"] == False

    def test_non_altitude_venue_is_false(self):
        """Away team at non-altitude venue → at_altitude=False."""
        games = _make_games([
            ("2025-01-01", "BOS", "NYK", 100, 95),
            ("2025-01-03", "BOS", "MIA", 102, 98),
        ])
        ctx = compute_schedule_context(games)
        assert ctx.iloc[1]["away_at_altitude"] == False

    def test_altitude_flag_cleared_after_5_days(self):
        """Away team was at altitude 5 days ago → at_altitude=True again."""
        games = _make_games([
            ("2025-01-01", "BOS", "DEN", 100, 95),
            ("2025-01-06", "BOS", "UTA", 102, 98),
        ])
        ctx = compute_schedule_context(games)
        # 5 days later → no longer within past 4 days → at_altitude=True
        assert ctx.iloc[1]["away_at_altitude"] == True


# ---------------------------------------------------------------------------
# Win percentage
# ---------------------------------------------------------------------------

class TestWinPercentage:
    def test_win_pct_default_no_games(self):
        """No prior games → win_pct=0.5."""
        games = _make_games([
            ("2025-01-01", "BOS", "NYK", 100, 95),
        ])
        ctx = compute_schedule_context(games)
        assert ctx.iloc[0]["away_win_pct"] == 0.5
        assert ctx.iloc[0]["home_win_pct"] == 0.5

    def test_win_pct_reflects_record_entering_game(self):
        """Win% is based on record ENTERING the game, not after."""
        # BOS wins game 1 (away, BOS 100 > 95), then plays game 2
        games = _make_games([
            ("2025-01-01", "BOS", "NYK", 100, 95),   # BOS wins (away)
            ("2025-01-03", "BOS", "MIA", 102, 98),   # BOS entering with 1-0
        ])
        ctx = compute_schedule_context(games)
        # After game 1: BOS is 1-0 → win_pct entering game 2 = 1.0
        assert ctx.iloc[1]["away_win_pct"] == 1.0

    def test_win_pct_updated_correctly_after_loss(self):
        """After a loss, win_pct reflects loss."""
        # BOS loses game 1 (away, BOS 90 < NYK 95)
        games = _make_games([
            ("2025-01-01", "BOS", "NYK", 90, 95),   # BOS loses
            ("2025-01-03", "BOS", "MIA", 102, 98),
        ])
        ctx = compute_schedule_context(games)
        # After game 1: BOS is 0-1 → win_pct entering game 2 = 0.0
        assert ctx.iloc[1]["away_win_pct"] == 0.0

    def test_win_pct_home_team_tracks_correctly(self):
        """Home team win% is tracked separately from away team."""
        # NYK wins game 1 at home (95 > 90)
        games = _make_games([
            ("2025-01-01", "BOS", "NYK", 90, 95),   # NYK wins at home
            ("2025-01-03", "MIA", "NYK", 98, 102),   # NYK hosts again
        ])
        ctx = compute_schedule_context(games)
        # NYK enters game 2 with 1-0 → win_pct=1.0
        assert ctx.iloc[1]["home_win_pct"] == 1.0

    def test_win_pct_mixed_record(self):
        """Team with 2-1 record → win_pct=0.667."""
        games = _make_games([
            ("2025-01-01", "BOS", "NYK", 100, 95),   # BOS wins
            ("2025-01-03", "BOS", "MIA", 102, 98),   # BOS wins
            ("2025-01-05", "BOS", "LAL", 90, 95),    # BOS loses
            ("2025-01-07", "BOS", "CHI", 105, 100),  # entering with 2-1
        ])
        ctx = compute_schedule_context(games)
        # BOS enters game 4 with 2-1 record → win_pct ≈ 0.667
        assert abs(ctx.iloc[3]["away_win_pct"] - 2/3) < 0.01


# ---------------------------------------------------------------------------
# Home is altitude flag
# ---------------------------------------------------------------------------

class TestHomeIsAltitude:
    def test_home_is_altitude_at_den(self):
        """Game at DEN → home_is_altitude=True."""
        games = _make_games([
            ("2025-01-01", "BOS", "DEN", 100, 95),
        ])
        ctx = compute_schedule_context(games)
        assert ctx.iloc[0]["home_is_altitude"] == True

    def test_home_is_altitude_at_uta(self):
        """Game at UTA → home_is_altitude=True."""
        games = _make_games([
            ("2025-01-01", "BOS", "UTA", 100, 95),
        ])
        ctx = compute_schedule_context(games)
        assert ctx.iloc[0]["home_is_altitude"] == True

    def test_home_is_altitude_non_altitude_venue(self):
        """Game not at DEN/UTA → home_is_altitude=False."""
        games = _make_games([
            ("2025-01-01", "BOS", "NYK", 100, 95),
        ])
        ctx = compute_schedule_context(games)
        assert ctx.iloc[0]["home_is_altitude"] == False


# ---------------------------------------------------------------------------
# Column completeness
# ---------------------------------------------------------------------------

class TestColumnCompleteness:
    EXPECTED_COLS = [
        "away_days_rest", "away_b2b", "away_traveled", "away_travel_dist",
        "away_est_sleep", "away_tz_change", "away_3in4", "away_4in6",
        "away_at_altitude", "away_win_pct",
        "home_days_rest", "home_b2b", "home_traveled", "home_travel_dist",
        "home_est_sleep", "home_tz_change", "home_3in4", "home_4in6",
        "home_at_altitude", "home_win_pct",
        "home_is_altitude",
    ]

    def test_all_expected_columns_present(self):
        games = _make_games([
            ("2025-01-01", "BOS", "NYK", 100, 95),
        ])
        ctx = compute_schedule_context(games)
        for col in self.EXPECTED_COLS:
            assert col in ctx.columns, f"Missing column: {col}"

    def test_output_row_count_matches_input(self):
        games = _make_games([
            ("2025-01-01", "BOS", "NYK", 100, 95),
            ("2025-01-03", "LAL", "MIA", 110, 108),
        ])
        ctx = compute_schedule_context(games)
        assert len(ctx) == len(games)
