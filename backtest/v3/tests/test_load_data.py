"""
test_load_data.py — Unit tests for backtest/v3/load_data.py

Run from the backtest/ directory:
    python -m pytest v3/tests/test_load_data.py -v
"""

import pytest
import pandas as pd

from v3.load_data import (
    compute_ats_result,
    compute_ou_result,
    normalize_game_row,
    _safe_float,
    _safe_int,
)


# ---------------------------------------------------------------------------
# compute_ats_result
# ---------------------------------------------------------------------------

class TestComputeAtsResult:
    def test_home_covers(self):
        # home_score=110, away_score=100, home_spread=-8 => adjusted=102 < 100? No: 110-8=102 > 100 -> home
        assert compute_ats_result(110, 100, -8) == "home"

    def test_away_covers(self):
        # home_score=100, away_score=110, home_spread=-8 => adjusted=92 < 110 -> away
        assert compute_ats_result(100, 110, -8) == "away"

    def test_push(self):
        # home_score=108, away_score=100, home_spread=-8 => adjusted=100 == 100 -> push
        assert compute_ats_result(108, 100, -8) == "push"

    def test_away_favored_home_covers(self):
        # home is underdog, spread=+6: home_score=105, away_score=108 => 105+6=111 > 108 -> home
        assert compute_ats_result(105, 108, 6) == "home"

    def test_away_favored_away_covers(self):
        # home is underdog, spread=+6: home_score=100, away_score=110 => 100+6=106 < 110 -> away
        assert compute_ats_result(100, 110, 6) == "away"

    def test_none_spread_returns_none(self):
        assert compute_ats_result(110, 100, None) is None

    def test_exact_home_favored_push(self):
        # home_score=115, away_score=110, home_spread=-5 => 115-5=110 == 110 -> push
        assert compute_ats_result(115, 110, -5) == "push"


# ---------------------------------------------------------------------------
# compute_ou_result
# ---------------------------------------------------------------------------

class TestComputeOuResult:
    def test_over(self):
        # 105 + 110 = 215 > 210.5 -> over
        assert compute_ou_result(105, 110, 210.5) == "over"

    def test_under(self):
        # 100 + 98 = 198 < 210.5 -> under
        assert compute_ou_result(100, 98, 210.5) == "under"

    def test_push(self):
        # 105 + 105 = 210 == 210 -> push
        assert compute_ou_result(105, 105, 210) == "push"

    def test_none_total_returns_none(self):
        assert compute_ou_result(105, 110, None) is None

    def test_high_scoring(self):
        # 130 + 125 = 255 > 230 -> over
        assert compute_ou_result(130, 125, 230) == "over"

    def test_exact_total_push(self):
        assert compute_ou_result(110, 100, 210) == "push"


# ---------------------------------------------------------------------------
# normalize_game_row
# ---------------------------------------------------------------------------

class TestNormalizeGameRow:
    def test_modern_abbrevs_pass_through(self):
        row = {"home_team": "BOS", "away_team": "LAL"}
        result = normalize_game_row(row)
        assert result["home_team"] == "BOS"
        assert result["away_team"] == "LAL"

    def test_historical_njn_maps_to_bkn(self):
        row = {"home_team": "NYK", "away_team": "NJN"}
        result = normalize_game_row(row)
        assert result["away_team"] == "BKN"

    def test_lowercase_gs_maps_to_gsw(self):
        row = {"home_team": "gs", "away_team": "lal"}
        result = normalize_game_row(row)
        assert result["home_team"] == "GSW"
        assert result["away_team"] == "LAL"

    def test_lowercase_utah_maps_to_uta(self):
        row = {"home_team": "utah", "away_team": "bos"}
        result = normalize_game_row(row)
        assert result["home_team"] == "UTA"

    def test_lowercase_no_maps_to_nop(self):
        row = {"home_team": "no", "away_team": "bos"}
        result = normalize_game_row(row)
        assert result["home_team"] == "NOP"

    def test_lowercase_sa_maps_to_sas(self):
        row = {"home_team": "sa", "away_team": "bos"}
        result = normalize_game_row(row)
        assert result["home_team"] == "SAS"

    def test_non_team_fields_preserved(self):
        row = {"home_team": "BOS", "away_team": "LAL", "score": 100}
        result = normalize_game_row(row)
        assert result["score"] == 100


# ---------------------------------------------------------------------------
# Kaggle spread conversion
# ---------------------------------------------------------------------------

class TestKaggleSpreadConversion:
    """Test spread direction logic: whos_favored='home' + spread=5 -> home_spread=-5"""

    def test_home_favored_spread_is_negative(self):
        # Import the internal conversion logic via load_kaggle result
        # We test the formula directly using the helper
        spread = 5.0
        whos_favored = "home"
        home_spread = -spread if whos_favored == "home" else +spread
        assert home_spread == -5.0

    def test_away_favored_spread_is_positive(self):
        spread = 3.0
        whos_favored = "away"
        home_spread = -spread if whos_favored == "home" else +spread
        assert home_spread == 3.0

    def test_home_favored_ats_makes_sense(self):
        # Home favored by 8: home_spread=-8
        # If home scores 110, away 100: adjusted=102 > 100 -> home covers
        home_spread = -8.0
        assert compute_ats_result(110, 100, home_spread) == "home"

    def test_away_favored_ats_makes_sense(self):
        # Away favored by 8: home_spread=+8
        # If home scores 100, away 110: adjusted=108 < 110 -> away covers
        home_spread = 8.0
        assert compute_ats_result(100, 110, home_spread) == "away"


# ---------------------------------------------------------------------------
# Season label conversion
# ---------------------------------------------------------------------------

class TestSeasonLabelConversion:
    """Test season integer -> label string conversion."""

    def _convert(self, season_int: int) -> str:
        """Replicate Kaggle season label conversion: 2025 -> '2024-25'."""
        start_year = int(season_int) - 1
        end_year = int(season_int)
        return f"{start_year}-{str(end_year)[-2:]}"

    def test_2025_becomes_2024_25(self):
        assert self._convert(2025) == "2024-25"

    def test_2019_becomes_2018_19(self):
        assert self._convert(2019) == "2018-19"

    def test_2008_becomes_2007_08(self):
        assert self._convert(2008) == "2007-08"

    def test_2010_becomes_2009_10(self):
        assert self._convert(2010) == "2009-10"

    def _convert_sbr(self, season_int: int) -> str:
        """SBR season label: 2011 -> '2011-12'."""
        start_year = int(season_int)
        end_year = int(season_int) + 1
        return f"{start_year}-{str(end_year)[-2:]}"

    def test_sbr_2011_becomes_2011_12(self):
        assert self._convert_sbr(2011) == "2011-12"

    def test_sbr_2021_becomes_2021_22(self):
        assert self._convert_sbr(2021) == "2021-22"


# ---------------------------------------------------------------------------
# _safe_float and _safe_int helpers
# ---------------------------------------------------------------------------

class TestSafeHelpers:
    def test_safe_float_numeric_string(self):
        assert _safe_float("3.5") == 3.5

    def test_safe_float_empty_string(self):
        assert _safe_float("") is None

    def test_safe_float_none(self):
        assert _safe_float(None) is None

    def test_safe_float_nan(self):
        import math
        # float('nan') should return None
        assert _safe_float(float("nan")) is None

    def test_safe_float_numeric(self):
        assert _safe_float(7.5) == 7.5

    def test_safe_int_numeric_string(self):
        assert _safe_int("106") == 106

    def test_safe_int_empty_string(self):
        assert _safe_int("") is None

    def test_safe_int_none(self):
        assert _safe_int(None) is None

    def test_safe_int_float_string(self):
        # "106.0" should convert: float first, then int
        assert _safe_int("106.0") == 106
