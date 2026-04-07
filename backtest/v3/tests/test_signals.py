"""
test_signals.py — Unit tests for backtest/v3/signals.py and backtest/v3/analyze.py

Run from the backtest/ directory:
    python -m pytest v3/tests/test_signals.py -v
"""

from __future__ import annotations

import math
import pytest
import pandas as pd
import numpy as np

from v3.signals import wilson_ci, compute_split, SIGNAL_CONDITIONS
from v3.analyze import assign_season


# ---------------------------------------------------------------------------
# wilson_ci
# ---------------------------------------------------------------------------

class TestWilsonCI:
    def test_basic_60_of_100(self):
        """60/100 should give a CI around 0.60, straddling it."""
        lo, hi = wilson_ci(60, 100)
        assert lo < 0.60 < hi
        assert 0.0 <= lo <= hi <= 1.0

    def test_zero_total_returns_zero_zero(self):
        """Zero total → (0.0, 0.0)."""
        lo, hi = wilson_ci(0, 0)
        assert lo == 0.0
        assert hi == 0.0

    def test_perfect_10_of_10(self):
        """10/10 wins → CI should have upper bound = 1.0."""
        lo, hi = wilson_ci(10, 10)
        assert hi == 1.0
        assert lo > 0.0  # not 0 even for perfect record with Wilson

    def test_ci_width_shrinks_with_larger_sample(self):
        """Larger sample → narrower CI at same win rate."""
        lo_small, hi_small = wilson_ci(60, 100)
        lo_large, hi_large = wilson_ci(600, 1000)
        width_small = hi_small - lo_small
        width_large = hi_large - lo_large
        assert width_large < width_small

    def test_values_within_unit_interval(self):
        """All CI values must be between 0 and 1."""
        for wins, total in [(0, 10), (5, 10), (10, 10), (1, 1), (100, 200)]:
            lo, hi = wilson_ci(wins, total)
            assert 0.0 <= lo <= hi <= 1.0, f"Failed for {wins}/{total}: ({lo}, {hi})"

    def test_known_approximate_bounds_60_of_100(self):
        """At 60/100 with z=1.96, Wilson CI should be roughly [0.50, 0.70]."""
        lo, hi = wilson_ci(60, 100)
        assert lo > 0.48
        assert hi < 0.72


# ---------------------------------------------------------------------------
# compute_split
# ---------------------------------------------------------------------------

class TestComputeSplit:
    def test_basic_mix_ats(self):
        """Basic mix of home/away/push."""
        results = ["home", "home", "away", "push", "home", None]
        split = compute_split(results)
        # home=3, away=1, pushes=1, None=1 → total=4 (excludes push and None)
        assert split["home_wins"] == 3
        assert split["away_wins"] == 1
        assert split["pushes"] == 1
        assert split["total"] == 4
        assert math.isclose(split["home_pct"], 75.0)
        assert math.isclose(split["away_pct"], 25.0)

    def test_basic_mix_ou(self):
        """Over/under results work correctly."""
        results = ["over", "over", "under", "push"]
        split = compute_split(results)
        assert split["home_wins"] == 2   # over counts as home_wins
        assert split["away_wins"] == 1   # under counts as away_wins
        assert split["pushes"] == 1
        assert split["total"] == 3

    def test_all_none_returns_zeros(self):
        """All None → total=0, CI=(0.0,0.0)."""
        split = compute_split([None, None, None])
        assert split["total"] == 0
        assert split["home_wins"] == 0
        assert split["away_wins"] == 0
        assert split["home_ci"] == (0.0, 0.0)
        assert split["away_ci"] == (0.0, 0.0)

    def test_all_pushes(self):
        """All pushes → total=0, CI=(0.0,0.0)."""
        split = compute_split(["push", "push", "push"])
        assert split["total"] == 0
        assert split["pushes"] == 3
        assert split["home_ci"] == (0.0, 0.0)

    def test_empty_list(self):
        """Empty list → all zeros."""
        split = compute_split([])
        assert split["total"] == 0
        assert split["home_wins"] == 0

    def test_wilson_ci_present(self):
        """compute_split includes Wilson CI tuples."""
        results = ["home"] * 6 + ["away"] * 4
        split = compute_split(results)
        assert "home_ci" in split
        assert "away_ci" in split
        lo, hi = split["home_ci"]
        assert isinstance(lo, float)
        assert isinstance(hi, float)

    def test_percentages_sum_to_100_when_no_push_no_none(self):
        """With no pushes or None, home_pct + away_pct = 100."""
        results = ["home", "home", "away", "home"]
        split = compute_split(results)
        assert math.isclose(split["home_pct"] + split["away_pct"], 100.0)

    def test_pushes_excluded_from_total(self):
        """Pushes don't count in total or win percentages."""
        results_with_push = ["home", "away", "push"]
        results_no_push = ["home", "away"]
        s1 = compute_split(results_with_push)
        s2 = compute_split(results_no_push)
        assert s1["total"] == s2["total"] == 2
        assert math.isclose(s1["home_pct"], s2["home_pct"])


# ---------------------------------------------------------------------------
# Helper: make a minimal pandas Series with schedule context columns
# ---------------------------------------------------------------------------

def _make_row(**kwargs) -> pd.Series:
    """Build a game row with all required schedule context columns, overridable via kwargs."""
    defaults = {
        # B2B flags
        "home_b2b": False,
        "away_b2b": False,
        # Traveled flags
        "home_traveled": False,
        "away_traveled": False,
        # Travel distances
        "home_travel_dist": 0.0,
        "away_travel_dist": 0.0,
        # Schedule density
        "home_3in4": False,
        "home_4in6": False,
        "away_3in4": False,
        "away_4in6": False,
        # Altitude
        "away_at_altitude": False,
        "home_at_altitude": False,
        "home_is_altitude": False,
        # Win pct
        "home_win_pct": 0.5,
        "away_win_pct": 0.5,
    }
    defaults.update(kwargs)
    return pd.Series(defaults)


# ---------------------------------------------------------------------------
# SIGNAL_CONDITIONS: check all 12 signals are defined
# ---------------------------------------------------------------------------

class TestSignalConditionsDefined:
    def test_all_12_signals_defined(self):
        """All 12 signal IDs must be present in SIGNAL_CONDITIONS."""
        expected_ids = {"S1", "S2", "S3", "S4", "S5", "S6", "B1", "B2", "D1", "D2", "A1", "C1"}
        assert set(SIGNAL_CONDITIONS.keys()) == expected_ids

    def test_each_signal_has_name_and_filter(self):
        """Each entry must have 'name' (str) and 'filter' (callable)."""
        for sig_id, sig in SIGNAL_CONDITIONS.items():
            assert "name" in sig, f"{sig_id} missing 'name'"
            assert "filter" in sig, f"{sig_id} missing 'filter'"
            assert isinstance(sig["name"], str), f"{sig_id} name must be str"
            assert callable(sig["filter"]), f"{sig_id} filter must be callable"

    def test_signal_names_are_non_empty(self):
        """Names must be non-empty strings."""
        for sig_id, sig in SIGNAL_CONDITIONS.items():
            assert len(sig["name"]) > 0, f"{sig_id} has empty name"


# ---------------------------------------------------------------------------
# S1: Home on B2B, away NOT on B2B
# ---------------------------------------------------------------------------

class TestSignalS1:
    def _f(self, **kwargs):
        return SIGNAL_CONDITIONS["S1"]["filter"](_make_row(**kwargs))

    def test_true_when_home_b2b_away_not(self):
        assert self._f(home_b2b=True, away_b2b=False) is True

    def test_false_when_both_b2b(self):
        assert self._f(home_b2b=True, away_b2b=True) is False

    def test_false_when_neither_b2b(self):
        assert self._f(home_b2b=False, away_b2b=False) is False

    def test_false_when_only_away_b2b(self):
        assert self._f(home_b2b=False, away_b2b=True) is False

    def test_works_with_numpy_bool(self):
        """Filter must handle numpy.bool_ values, not just Python bool."""
        row = _make_row(home_b2b=np.bool_(True), away_b2b=np.bool_(False))
        assert SIGNAL_CONDITIONS["S1"]["filter"](row) is True


# ---------------------------------------------------------------------------
# S2: Home on B2B + traveled, away NOT on B2B
# ---------------------------------------------------------------------------

class TestSignalS2:
    def _f(self, **kwargs):
        return SIGNAL_CONDITIONS["S2"]["filter"](_make_row(**kwargs))

    def test_true_when_home_b2b_traveled_away_not(self):
        assert self._f(home_b2b=True, home_traveled=True, away_b2b=False) is True

    def test_false_when_home_b2b_not_traveled(self):
        assert self._f(home_b2b=True, home_traveled=False, away_b2b=False) is False

    def test_false_when_away_also_b2b(self):
        assert self._f(home_b2b=True, home_traveled=True, away_b2b=True) is False


# ---------------------------------------------------------------------------
# S3: Home on B2B + long travel (>=1000mi), away NOT on B2B
# ---------------------------------------------------------------------------

class TestSignalS3:
    def _f(self, **kwargs):
        return SIGNAL_CONDITIONS["S3"]["filter"](_make_row(**kwargs))

    def test_true_long_travel(self):
        assert self._f(home_b2b=True, home_traveled=True, home_travel_dist=1200.0, away_b2b=False) is True

    def test_false_short_travel(self):
        assert self._f(home_b2b=True, home_traveled=True, home_travel_dist=500.0, away_b2b=False) is False

    def test_false_exactly_999_miles(self):
        assert self._f(home_b2b=True, home_traveled=True, home_travel_dist=999.0, away_b2b=False) is False

    def test_true_exactly_1000_miles(self):
        assert self._f(home_b2b=True, home_traveled=True, home_travel_dist=1000.0, away_b2b=False) is True


# ---------------------------------------------------------------------------
# S4: Away on B2B, home NOT on B2B
# ---------------------------------------------------------------------------

class TestSignalS4:
    def _f(self, **kwargs):
        return SIGNAL_CONDITIONS["S4"]["filter"](_make_row(**kwargs))

    def test_true_when_away_b2b_home_not(self):
        assert self._f(away_b2b=True, home_b2b=False) is True

    def test_false_when_both_b2b(self):
        assert self._f(away_b2b=True, home_b2b=True) is False

    def test_false_when_neither_b2b(self):
        assert self._f(away_b2b=False, home_b2b=False) is False


# ---------------------------------------------------------------------------
# S5: Away on B2B + traveled, home NOT on B2B
# ---------------------------------------------------------------------------

class TestSignalS5:
    def _f(self, **kwargs):
        return SIGNAL_CONDITIONS["S5"]["filter"](_make_row(**kwargs))

    def test_true_when_away_b2b_traveled_home_not(self):
        assert self._f(away_b2b=True, away_traveled=True, home_b2b=False) is True

    def test_false_when_away_b2b_not_traveled(self):
        assert self._f(away_b2b=True, away_traveled=False, home_b2b=False) is False

    def test_false_when_home_also_b2b(self):
        assert self._f(away_b2b=True, away_traveled=True, home_b2b=True) is False


# ---------------------------------------------------------------------------
# S6: Away on B2B + long travel (>=1000mi), home NOT on B2B
# ---------------------------------------------------------------------------

class TestSignalS6:
    def _f(self, **kwargs):
        return SIGNAL_CONDITIONS["S6"]["filter"](_make_row(**kwargs))

    def test_true_long_travel(self):
        assert self._f(away_b2b=True, away_traveled=True, away_travel_dist=1500.0, home_b2b=False) is True

    def test_false_short_travel(self):
        assert self._f(away_b2b=True, away_traveled=True, away_travel_dist=800.0, home_b2b=False) is False

    def test_false_exactly_999_miles(self):
        assert self._f(away_b2b=True, away_traveled=True, away_travel_dist=999.0, home_b2b=False) is False

    def test_true_exactly_1000_miles(self):
        assert self._f(away_b2b=True, away_traveled=True, away_travel_dist=1000.0, home_b2b=False) is True


# ---------------------------------------------------------------------------
# B1: Both B2B, only road traveled (home home-home B2B)
# ---------------------------------------------------------------------------

class TestSignalB1:
    def _f(self, **kwargs):
        return SIGNAL_CONDITIONS["B1"]["filter"](_make_row(**kwargs))

    def test_true_when_both_b2b_home_not_traveled(self):
        assert self._f(away_b2b=True, home_b2b=True, home_traveled=False) is True

    def test_false_when_home_also_traveled(self):
        assert self._f(away_b2b=True, home_b2b=True, home_traveled=True) is False

    def test_false_when_only_away_b2b(self):
        assert self._f(away_b2b=True, home_b2b=False, home_traveled=False) is False

    def test_false_when_only_home_b2b(self):
        assert self._f(away_b2b=False, home_b2b=True, home_traveled=False) is False


# ---------------------------------------------------------------------------
# B2: Both B2B, both traveled
# ---------------------------------------------------------------------------

class TestSignalB2:
    def _f(self, **kwargs):
        return SIGNAL_CONDITIONS["B2"]["filter"](_make_row(**kwargs))

    def test_true_when_both_b2b_home_traveled(self):
        assert self._f(away_b2b=True, home_b2b=True, home_traveled=True) is True

    def test_false_when_home_not_traveled(self):
        assert self._f(away_b2b=True, home_b2b=True, home_traveled=False) is False

    def test_false_when_only_away_b2b(self):
        assert self._f(away_b2b=True, home_b2b=False, home_traveled=True) is False


# ---------------------------------------------------------------------------
# D1: Home on 3-in-4 or 4-in-6
# ---------------------------------------------------------------------------

class TestSignalD1:
    def _f(self, **kwargs):
        return SIGNAL_CONDITIONS["D1"]["filter"](_make_row(**kwargs))

    def test_true_when_home_3in4(self):
        assert self._f(home_3in4=True, home_4in6=False) is True

    def test_true_when_home_4in6(self):
        assert self._f(home_3in4=False, home_4in6=True) is True

    def test_true_when_both(self):
        assert self._f(home_3in4=True, home_4in6=True) is True

    def test_false_when_neither(self):
        assert self._f(home_3in4=False, home_4in6=False) is False


# ---------------------------------------------------------------------------
# D2: Away on 3-in-4 or 4-in-6
# ---------------------------------------------------------------------------

class TestSignalD2:
    def _f(self, **kwargs):
        return SIGNAL_CONDITIONS["D2"]["filter"](_make_row(**kwargs))

    def test_true_when_away_3in4(self):
        assert self._f(away_3in4=True, away_4in6=False) is True

    def test_true_when_away_4in6(self):
        assert self._f(away_3in4=False, away_4in6=True) is True

    def test_false_when_neither(self):
        assert self._f(away_3in4=False, away_4in6=False) is False


# ---------------------------------------------------------------------------
# A1: Visitor at DEN/UTA on B2B with travel
# ---------------------------------------------------------------------------

class TestSignalA1:
    def _f(self, **kwargs):
        return SIGNAL_CONDITIONS["A1"]["filter"](_make_row(**kwargs))

    def test_true_when_away_b2b_traveled_at_altitude(self):
        assert self._f(away_b2b=True, away_traveled=True, away_at_altitude=True) is True

    def test_false_when_not_at_altitude(self):
        assert self._f(away_b2b=True, away_traveled=True, away_at_altitude=False) is False

    def test_false_when_not_b2b(self):
        assert self._f(away_b2b=False, away_traveled=True, away_at_altitude=True) is False

    def test_false_when_not_traveled(self):
        assert self._f(away_b2b=True, away_traveled=False, away_at_altitude=True) is False


# ---------------------------------------------------------------------------
# C1: Neither team on B2B (control)
# ---------------------------------------------------------------------------

class TestSignalC1:
    def _f(self, **kwargs):
        return SIGNAL_CONDITIONS["C1"]["filter"](_make_row(**kwargs))

    def test_true_when_neither_b2b(self):
        assert self._f(away_b2b=False, home_b2b=False) is True

    def test_false_when_away_b2b(self):
        assert self._f(away_b2b=True, home_b2b=False) is False

    def test_false_when_home_b2b(self):
        assert self._f(away_b2b=False, home_b2b=True) is False

    def test_false_when_both_b2b(self):
        assert self._f(away_b2b=True, home_b2b=True) is False

    def test_works_with_numpy_bool(self):
        """numpy.bool_ must be handled correctly."""
        row = _make_row(away_b2b=np.bool_(False), home_b2b=np.bool_(False))
        assert SIGNAL_CONDITIONS["C1"]["filter"](row) is True

        row2 = _make_row(away_b2b=np.bool_(True), home_b2b=np.bool_(False))
        assert SIGNAL_CONDITIONS["C1"]["filter"](row2) is False


# ---------------------------------------------------------------------------
# assign_season
# ---------------------------------------------------------------------------

class TestAssignSeason:
    def test_october_maps_to_current_start_year(self):
        """October 2024 → '2024-25'."""
        assert assign_season("2024-10-15") == "2024-25"

    def test_november_maps_to_current_start_year(self):
        """November 2022 → '2022-23'."""
        assert assign_season("2022-11-01") == "2022-23"

    def test_april_maps_to_prev_start_year(self):
        """April 2025 → '2024-25'."""
        assert assign_season("2025-04-07") == "2024-25"

    def test_january_maps_to_prev_start_year(self):
        """January 2023 → '2022-23'."""
        assert assign_season("2023-01-15") == "2022-23"

    def test_february_maps_to_prev_start_year(self):
        """February 2024 → '2023-24'."""
        assert assign_season("2024-02-18") == "2023-24"

    def test_june_maps_to_prev_start_year(self):
        """June 2024 (playoffs) → '2023-24'."""
        assert assign_season("2024-06-10") == "2023-24"

    def test_two_digit_year_zero_padded(self):
        """Season label second part is zero-padded: '2019-20' not '2019-0'."""
        result = assign_season("2019-11-01")
        assert result == "2019-20"

    def test_century_boundary(self):
        """2099-10 → '2099-00' (modulo wrapping — edge case)."""
        result = assign_season("2099-10-01")
        assert result == "2099-00"
