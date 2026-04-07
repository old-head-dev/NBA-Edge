"""
test_arenas.py — Unit tests for backtest/v3/arenas.py

Run from the backtest/ directory:
    python -m pytest v3/tests/test_arenas.py -v
"""

import math
import pytest

from v3.arenas import (
    ARENAS,
    ALTITUDE_ARENAS,
    haversine_miles,
    normalize_team,
    get_tz_offset,
    travel_distance,
)


# ---------------------------------------------------------------------------
# haversine_miles
# ---------------------------------------------------------------------------

class TestHaversineMiles:
    def test_bos_lal_approx_2611_miles(self):
        """Boston to LA Lakers arena should be ~2611 miles."""
        bos = ARENAS["BOS"]
        lal = ARENAS["LAL"]
        dist = haversine_miles(bos["lat"], bos["lon"], lal["lat"], lal["lon"])
        assert abs(dist - 2611) < 25, f"Expected ~2611mi, got {dist:.1f}mi"

    def test_same_point_is_zero(self):
        """Distance from a point to itself must be exactly 0."""
        dist = haversine_miles(40.7505, -73.9934, 40.7505, -73.9934)
        assert dist == 0.0

    def test_lal_lac_under_15_miles(self):
        """LA Lakers and LA Clippers share the same arena building — should be < 15mi."""
        lal = ARENAS["LAL"]
        lac = ARENAS["LAC"]
        dist = haversine_miles(lal["lat"], lal["lon"], lac["lat"], lac["lon"])
        assert dist < 15, f"LAL-LAC distance should be < 15mi, got {dist:.2f}mi"


# ---------------------------------------------------------------------------
# ARENAS completeness
# ---------------------------------------------------------------------------

class TestArenasCompleteness:
    EXPECTED_TEAMS = {
        "ATL", "BOS", "BKN", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", "GSW",
        "HOU", "IND", "LAC", "LAL", "MEM", "MIA", "MIL", "MIN", "NOP", "NYK",
        "OKC", "ORL", "PHI", "PHX", "POR", "SAC", "SAS", "TOR", "UTA", "WAS",
    }

    def test_all_30_teams_present(self):
        assert set(ARENAS.keys()) == self.EXPECTED_TEAMS

    def test_each_entry_has_lat_lon_tz(self):
        for team, data in ARENAS.items():
            assert "lat" in data, f"{team} missing lat"
            assert "lon" in data, f"{team} missing lon"
            assert "tz" in data, f"{team} missing tz"

    def test_altitude_arenas_subset_of_arenas(self):
        assert ALTITUDE_ARENAS.issubset(set(ARENAS.keys()))

    def test_altitude_arenas_contains_den_uta(self):
        assert "DEN" in ALTITUDE_ARENAS
        assert "UTA" in ALTITUDE_ARENAS


# ---------------------------------------------------------------------------
# normalize_team
# ---------------------------------------------------------------------------

class TestNormalizeTeam:
    def test_modern_abbreviations_pass_through(self):
        for team in ("BOS", "LAL", "GSW", "NYK", "SAS"):
            assert normalize_team(team) == team

    def test_historical_njn_maps_to_bkn(self):
        assert normalize_team("NJN") == "BKN"

    def test_historical_sea_maps_to_okc(self):
        assert normalize_team("SEA") == "OKC"

    def test_historical_noh_maps_to_nop(self):
        assert normalize_team("NOH") == "NOP"

    def test_historical_chh_maps_to_cha(self):
        assert normalize_team("CHH") == "CHA"

    def test_historical_van_maps_to_mem(self):
        assert normalize_team("VAN") == "MEM"

    def test_case_insensitive_lowercase(self):
        assert normalize_team("bos") == "BOS"
        assert normalize_team("lal") == "LAL"

    def test_case_insensitive_mixed(self):
        assert normalize_team("Njn") == "BKN"
        assert normalize_team("sea") == "OKC"

    def test_unknown_team_raises_key_error(self):
        with pytest.raises(KeyError):
            normalize_team("XYZ")


# ---------------------------------------------------------------------------
# get_tz_offset
# ---------------------------------------------------------------------------

class TestGetTzOffset:
    def test_bos_is_minus_5(self):
        assert get_tz_offset("BOS") == -5

    def test_lal_is_minus_8(self):
        assert get_tz_offset("LAL") == -8

    def test_den_is_minus_7(self):
        assert get_tz_offset("DEN") == -7

    def test_chi_is_minus_6(self):
        assert get_tz_offset("CHI") == -6

    def test_historical_alias_resolves(self):
        # NJN → BKN, which is tz=-5
        assert get_tz_offset("NJN") == -5


# ---------------------------------------------------------------------------
# travel_distance
# ---------------------------------------------------------------------------

class TestTravelDistance:
    def test_bos_cle_approx_554_miles(self):
        """Boston to Cleveland should be ~554 miles."""
        dist = travel_distance("BOS", "CLE")
        assert abs(dist - 554) < 20, f"Expected ~554mi, got {dist:.1f}mi"

    def test_same_team_is_zero(self):
        assert travel_distance("LAL", "LAL") == 0.0

    def test_symmetry(self):
        """travel_distance(A, B) == travel_distance(B, A)"""
        d_ab = travel_distance("MIA", "BOS")
        d_ba = travel_distance("BOS", "MIA")
        assert math.isclose(d_ab, d_ba, rel_tol=1e-9)

    def test_historical_alias_works(self):
        """travel_distance should accept historical abbreviations."""
        # NJN → BKN; should match BKN-BOS distance
        dist_alias = travel_distance("NJN", "BOS")
        dist_modern = travel_distance("BKN", "BOS")
        assert math.isclose(dist_alias, dist_modern, rel_tol=1e-9)
