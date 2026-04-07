"""
arenas.py — NBA arena coordinates, timezone offsets, and travel utilities.

Pure Python, no external dependencies.
Used by the schedule context engine to compute travel distances and tz changes.
"""

import math

# All 30 NBA arenas: lat/lon in decimal degrees, tz = UTC offset (standard time)
ARENAS: dict[str, dict] = {
    "ATL": {"lat": 33.7573, "lon": -84.3963, "tz": -5},
    "BOS": {"lat": 42.3662, "lon": -71.0621, "tz": -5},
    "BKN": {"lat": 40.6826, "lon": -73.9754, "tz": -5},
    "CHA": {"lat": 35.2251, "lon": -80.8392, "tz": -5},
    "CHI": {"lat": 41.8807, "lon": -87.6742, "tz": -6},
    "CLE": {"lat": 41.4965, "lon": -81.6882, "tz": -5},
    "DAL": {"lat": 32.7905, "lon": -96.8103, "tz": -6},
    "DEN": {"lat": 39.7487, "lon": -105.0077, "tz": -7},
    "DET": {"lat": 42.3410, "lon": -83.0552, "tz": -5},
    "GSW": {"lat": 37.7680, "lon": -122.3877, "tz": -8},
    "HOU": {"lat": 29.7508, "lon": -95.3621, "tz": -6},
    "IND": {"lat": 39.7640, "lon": -86.1555, "tz": -5},
    "LAC": {"lat": 33.8958, "lon": -118.3386, "tz": -8},
    "LAL": {"lat": 34.0430, "lon": -118.2673, "tz": -8},
    "MEM": {"lat": 35.1383, "lon": -90.0505, "tz": -6},
    "MIA": {"lat": 25.7814, "lon": -80.1870, "tz": -5},
    "MIL": {"lat": 43.0450, "lon": -87.9170, "tz": -6},
    "MIN": {"lat": 44.9795, "lon": -93.2762, "tz": -6},
    "NOP": {"lat": 29.9490, "lon": -90.0812, "tz": -6},
    "NYK": {"lat": 40.7505, "lon": -73.9934, "tz": -5},
    "OKC": {"lat": 35.4634, "lon": -97.5151, "tz": -6},
    "ORL": {"lat": 28.5392, "lon": -81.3839, "tz": -5},
    "PHI": {"lat": 39.9012, "lon": -75.1720, "tz": -5},
    "PHX": {"lat": 33.4457, "lon": -112.0712, "tz": -7},
    "POR": {"lat": 45.5316, "lon": -122.6668, "tz": -8},
    "SAC": {"lat": 38.5802, "lon": -121.4997, "tz": -8},
    "SAS": {"lat": 29.4270, "lon": -98.4375, "tz": -6},
    "TOR": {"lat": 43.6435, "lon": -79.3791, "tz": -5},
    "UTA": {"lat": 40.7683, "lon": -111.9011, "tz": -7},
    "WAS": {"lat": 38.8981, "lon": -77.0209, "tz": -5},
}

# Teams playing at high altitude (>4000 ft)
ALTITUDE_ARENAS: set[str] = {"DEN", "UTA"}

# Historical abbreviation → modern 3-letter code
_TEAM_ALIASES: dict[str, str] = {
    "NJN": "BKN",
    "SEA": "OKC",
    "NOH": "NOP",
    "NOK": "NOP",
    "CHH": "CHA",
    "CHO": "CHA",
    "CHP": "CHA",
    "VAN": "MEM",
    "GOS": "GSW",
    "PHO": "PHX",
    "SA":  "SAS",
    "NY":  "NYK",
    "NO":  "NOP",
    "GS":  "GSW",
    "WSH": "WAS",
    "BRK": "BKN",
    "UTH": "UTA",
}


def normalize_team(abbr: str) -> str:
    """Return the canonical modern 3-letter team code for any abbreviation.

    Uppercases input, resolves historical aliases, then returns the modern code.
    Raises KeyError if the result is not a known arena.
    """
    upper = abbr.upper().strip()
    modern = _TEAM_ALIASES.get(upper, upper)
    if modern not in ARENAS:
        raise KeyError(f"Unknown team abbreviation: {abbr!r} (resolved to {modern!r})")
    return modern


def get_tz_offset(team: str) -> int:
    """Return the UTC offset (integer hours) for a team's arena."""
    return ARENAS[normalize_team(team)]["tz"]


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute the great-circle distance in miles between two lat/lon points.

    Uses the Haversine formula with Earth radius R = 3959 miles.
    """
    R = 3959.0  # Earth radius in miles
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return R * c


def travel_distance(from_team: str, to_team: str) -> float:
    """Return the great-circle distance in miles between two teams' arenas."""
    src = ARENAS[normalize_team(from_team)]
    dst = ARENAS[normalize_team(to_team)]
    return haversine_miles(src["lat"], src["lon"], dst["lat"], dst["lon"])
