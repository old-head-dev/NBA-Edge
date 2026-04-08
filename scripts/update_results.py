#!/usr/bin/env python3
"""
NBA Edge V3 — Nightly Results Logger
Runs via GitHub Actions at 9am ET daily.
Pulls previous day's finalized NBA games from SGO,
detects V3 schedule signals (S2, B2), grades ATS outcomes,
appends to data/results_v3.json.
"""

import os
import json
import time
import requests
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

SGO_KEY = os.environ["SGO_API_KEY"]
BASE    = "https://api.sportsgameodds.com/v2"
HEADERS = {"x-api-key": SGO_KEY}

BDL_KEY     = os.environ["BDL_API_KEY"]
BDL_BASE    = "https://api.balldontlie.io/v1"
BDL_HEADERS = {"Authorization": BDL_KEY}

ET = ZoneInfo("America/New_York")

# ── V3 SIGNAL MODEL ──────────────────────────────────────────────
import math

ARENAS = {
    "ATL":{"lat":33.7573,"lon":-84.3963,"tz_name":"America/New_York"},
    "BOS":{"lat":42.3662,"lon":-71.0621,"tz_name":"America/New_York"},
    "BKN":{"lat":40.6826,"lon":-73.9754,"tz_name":"America/New_York"},
    "CHA":{"lat":35.2251,"lon":-80.8392,"tz_name":"America/New_York"},
    "CHI":{"lat":41.8807,"lon":-87.6742,"tz_name":"America/Chicago"},
    "CLE":{"lat":41.4965,"lon":-81.6882,"tz_name":"America/New_York"},
    "DAL":{"lat":32.7905,"lon":-96.8103,"tz_name":"America/Chicago"},
    "DEN":{"lat":39.7487,"lon":-105.0077,"tz_name":"America/Denver"},
    "DET":{"lat":42.3410,"lon":-83.0552,"tz_name":"America/New_York"},
    "GSW":{"lat":37.7680,"lon":-122.3877,"tz_name":"America/Los_Angeles"},
    "HOU":{"lat":29.7508,"lon":-95.3621,"tz_name":"America/Chicago"},
    "IND":{"lat":39.7640,"lon":-86.1555,"tz_name":"America/New_York"},
    "LAC":{"lat":33.8958,"lon":-118.3386,"tz_name":"America/Los_Angeles"},
    "LAL":{"lat":34.0430,"lon":-118.2673,"tz_name":"America/Los_Angeles"},
    "MEM":{"lat":35.1383,"lon":-90.0505,"tz_name":"America/Chicago"},
    "MIA":{"lat":25.7814,"lon":-80.1870,"tz_name":"America/New_York"},
    "MIL":{"lat":43.0450,"lon":-87.9170,"tz_name":"America/Chicago"},
    "MIN":{"lat":44.9795,"lon":-93.2762,"tz_name":"America/Chicago"},
    "NOP":{"lat":29.9490,"lon":-90.0812,"tz_name":"America/Chicago"},
    "NYK":{"lat":40.7505,"lon":-73.9934,"tz_name":"America/New_York"},
    "OKC":{"lat":35.4634,"lon":-97.5151,"tz_name":"America/Chicago"},
    "ORL":{"lat":28.5392,"lon":-81.3839,"tz_name":"America/New_York"},
    "PHI":{"lat":39.9012,"lon":-75.1720,"tz_name":"America/New_York"},
    "PHX":{"lat":33.4457,"lon":-112.0712,"tz_name":"America/Phoenix"},
    "POR":{"lat":45.5316,"lon":-122.6668,"tz_name":"America/Los_Angeles"},
    "SAC":{"lat":38.5802,"lon":-121.4997,"tz_name":"America/Los_Angeles"},
    "SAS":{"lat":29.4270,"lon":-98.4375,"tz_name":"America/Chicago"},
    "TOR":{"lat":43.6435,"lon":-79.3791,"tz_name":"America/Toronto"},
    "UTA":{"lat":40.7683,"lon":-111.9011,"tz_name":"America/Denver"},
    "WAS":{"lat":38.8981,"lon":-77.0209,"tz_name":"America/New_York"},
}
ALTITUDE_ARENAS = {"DEN", "UTA"}

# Map SGO teamID suffixes to our abbreviations
SGO_TEAM_MAP = {
    "ATLANTA_HAWKS_NBA": "ATL", "BOSTON_CELTICS_NBA": "BOS",
    "BROOKLYN_NETS_NBA": "BKN", "CHARLOTTE_HORNETS_NBA": "CHA",
    "CHICAGO_BULLS_NBA": "CHI", "CLEVELAND_CAVALIERS_NBA": "CLE",
    "DALLAS_MAVERICKS_NBA": "DAL", "DENVER_NUGGETS_NBA": "DEN",
    "DETROIT_PISTONS_NBA": "DET", "GOLDEN_STATE_WARRIORS_NBA": "GSW",
    "HOUSTON_ROCKETS_NBA": "HOU", "INDIANA_PACERS_NBA": "IND",
    "LOS_ANGELES_CLIPPERS_NBA": "LAC", "LOS_ANGELES_LAKERS_NBA": "LAL",
    "MEMPHIS_GRIZZLIES_NBA": "MEM", "MIAMI_HEAT_NBA": "MIA",
    "MILWAUKEE_BUCKS_NBA": "MIL", "MINNESOTA_TIMBERWOLVES_NBA": "MIN",
    "NEW_ORLEANS_PELICANS_NBA": "NOP", "NEW_YORK_KNICKS_NBA": "NYK",
    "OKLAHOMA_CITY_THUNDER_NBA": "OKC", "ORLANDO_MAGIC_NBA": "ORL",
    "PHILADELPHIA_76ERS_NBA": "PHI", "PHOENIX_SUNS_NBA": "PHX",
    "PORTLAND_TRAIL_BLAZERS_NBA": "POR", "SACRAMENTO_KINGS_NBA": "SAC",
    "SAN_ANTONIO_SPURS_NBA": "SAS", "TORONTO_RAPTORS_NBA": "TOR",
    "UTAH_JAZZ_NBA": "UTA", "WASHINGTON_WIZARDS_NBA": "WAS",
}

def haversine(lat1, lon1, lat2, lon2):
    R = 3959
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return round(R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a)))

def get_dist(a, b):
    if a == b: return 0
    if set([a,b]) == {"LAL","LAC"}: return 12
    if set([a,b]) == {"NYK","BKN"}: return 8
    if a not in ARENAS or b not in ARENAS: return 0
    return haversine(ARENAS[a]["lat"], ARENAS[a]["lon"], ARENAS[b]["lat"], ARENAS[b]["lon"])

def get_schedule_context(team, game_date, game_arena, team_history):
    """Simple schedule context -- just B2B and travel detection.

    game_arena: the HOME team abbreviation (game is always at home arena).
    Must match backtest/v3/schedule.py definition: traveled = prev_arena != arena_tonight.
    """
    games = team_history.get(team, [])
    if not games:
        return {"is_b2b": False, "traveled": False, "travel_dist": 0, "prev_arena": None}

    # Find most recent game before game_date
    # team_history entries have "et_date" (datetime.date) and "home_abbr" keys
    played = [g for g in games if g["et_date"] < game_date]
    if not played:
        return {"is_b2b": False, "traveled": False, "travel_dist": 0, "prev_arena": None}

    last = played[-1]  # already sorted ascending by date
    days_since = (game_date - last["et_date"]).days
    is_b2b = (days_since == 1)  # played exactly yesterday

    # "traveled" = previous game was at a different arena than TONIGHT's game arena
    prev_arena = last["home_abbr"]  # game is always at home team's arena
    traveled = (prev_arena != game_arena)

    travel_dist = 0
    if traveled and prev_arena in ARENAS and game_arena in ARENAS:
        travel_dist = haversine(
            ARENAS[prev_arena]["lat"], ARENAS[prev_arena]["lon"],
            ARENAS[game_arena]["lat"], ARENAS[game_arena]["lon"]
        )

    return {
        "is_b2b": is_b2b,
        "traveled": traveled,
        "travel_dist": round(travel_dist),
        "prev_arena": prev_arena,
    }

def detect_v3_signals(home, away, game_date, team_history):
    """Detect V3 signals for a game. Returns list of signal dicts."""
    game_arena = home  # game is always at home team's arena
    home_ctx = get_schedule_context(home, game_date, game_arena, team_history)
    away_ctx = get_schedule_context(away, game_date, game_arena, team_history)

    signals = []

    # S2: Home B2B + traveled, away NOT B2B
    if home_ctx["is_b2b"] and home_ctx["traveled"] and not away_ctx["is_b2b"]:
        signals.append({
            "signal": "S2",
            "bet_direction": "away",
            "detail": f"{home} flew home from {home_ctx['prev_arena']} ({home_ctx['travel_dist']}mi)",
            "home_ctx": home_ctx,
            "away_ctx": away_ctx,
        })

    # B2: Both B2B + home traveled
    if home_ctx["is_b2b"] and home_ctx["traveled"] and away_ctx["is_b2b"]:
        signals.append({
            "signal": "B2",
            "bet_direction": "home",
            "detail": f"Both B2B. {home} traveled {home_ctx['travel_dist']}mi from {home_ctx['prev_arena']}",
            "home_ctx": home_ctx,
            "away_ctx": away_ctx,
        })

    return signals

def grade_signal(signal_type, ats_result):
    """Grade a V3 signal result. Returns None if ats_result is missing."""
    if ats_result is None:
        return None
    if signal_type == "S2":
        # S2 bets AWAY
        if ats_result == "away": return "WIN"
        if ats_result == "home": return "LOSS"
        return "PUSH"
    elif signal_type == "B2":
        # B2 tracks HOME
        if ats_result == "home": return "WIN"
        if ats_result == "away": return "LOSS"
        return "PUSH"
    return None

# ── SGO FETCH HELPERS ─────────────────────────────────────────────

def sgo_get(endpoint, params, retries=4, backoff=15):
    import time
    for attempt in range(retries):
        r = requests.get(f"{BASE}{endpoint}", headers=HEADERS, params=params, timeout=20)
        if r.status_code == 429:
            wait = backoff * (2 ** attempt)
            print(f"  429 rate limit — waiting {wait}s before retry {attempt+1}/{retries}")
            time.sleep(wait)
            continue
        r.raise_for_status()
        return r.json()
    raise Exception(f"SGO API rate limit exceeded after {retries} retries for {endpoint}")

def fetch_all_events(params):
    events = []
    cursor = None
    while True:
        p = {**params, "limit": 50}
        if cursor:
            p["cursor"] = cursor
        data = sgo_get("/events/", p)
        events.extend(data.get("data", []))
        cursor = data.get("nextCursor")
        if not cursor:
            break
    return events

# ── BDL HISTORY FETCH ────────────────────────────────────────────

def fetch_bdl_history(start_date_str, end_date_str):
    """
    Fetch games between two dates from BDL for schedule history.
    V3 only needs ~3 days for B2B detection.
    Batches in chunks of 6 dates per request to stay within param limits.
    """
    from datetime import date as _date
    start = _date.fromisoformat(start_date_str)
    end   = _date.fromisoformat(end_date_str)
    dates = []
    cur = start
    while cur < end:
        dates.append(cur.isoformat())
        cur += timedelta(days=1)

    all_games = []
    for i in range(0, len(dates), 6):
        batch  = dates[i:i+6]
        params = [("dates[]", d) for d in batch] + [("per_page", 100)]
        r = requests.get(f"{BDL_BASE}/games", headers=BDL_HEADERS,
                         params=params, timeout=20)
        r.raise_for_status()
        all_games.extend(r.json().get("data", []))
        if i + 6 < len(dates):
            time.sleep(1)  # stay under BDL rate limit between chunks
    return all_games

# ── TEAM ABBR FROM SGO EVENT ──────────────────────────────────────

def abbr(team_obj):
    tid = team_obj.get("teamID", "")
    if tid in SGO_TEAM_MAP:
        return SGO_TEAM_MAP[tid]
    # fallback: use short name
    return team_obj.get("names", {}).get("short", tid[:3].upper())

# ── OUTCOME COMPUTATION ───────────────────────────────────────────

def compute_outcomes(event):
    """
    SGO puts closeSpread, closeOverUnder, and score directly on the odd object
    (top level, not nested in byBookmaker). Per the handling-odds guide:
      oddObject.score         = final stat value for that market
      oddObject.closeOverUnder = closing line for OU markets
      oddObject.closeSpread    = closing line for spread markets
    We use the consensus/book values. byBookmaker is NOT needed for grading.
    """
    odds = event.get("odds", {})

    # --- Spread (home perspective) ---
    sp_odd = odds.get("points-home-game-sp-home")
    close_spread = None
    if sp_odd:
        for field in ("closeSpread", "closeBookSpread", "bookSpread"):
            v = sp_odd.get(field)
            if v is not None:
                close_spread = float(v)
                break

    # --- Total: use the over odd; its score = total points scored ---
    ou_odd = odds.get("points-all-game-ou-over")
    close_total = None
    total_scored = None
    if ou_odd:
        for field in ("closeOverUnder", "closeBookOverUnder", "bookOverUnder"):
            v = ou_odd.get(field)
            if v is not None:
                close_total = float(v)
                break
        s = ou_odd.get("score")
        if s is not None:
            total_scored = float(s)

    # --- Spread score: use home spread odd's score (= home_pts - away_pts + spread) ---
    # Actually SGO score on a spread odd = the raw stat (home points for home-sp-home).
    # We need home margin, which we already have from final scores passed in separately.
    # So ATS grading uses close_spread + final scores (computed below in caller).

    # O/U result — if SGO gave us total_scored via score field, use it
    ou_result = None
    if close_total is not None and total_scored is not None:
        if total_scored > close_total:   ou_result = "over"
        elif total_scored < close_total: ou_result = "under"
        else:                            ou_result = "push"

    return {
        "close_spread":  close_spread,
        "close_total":   close_total,
        "total_scored":  total_scored,
        "ou_result":     ou_result,
    }

# ── MAIN ──────────────────────────────────────────────────────────

def main():
    # Yesterday in ET
    now_et    = datetime.now(ET)
    yesterday = (now_et - timedelta(days=1)).strftime("%Y-%m-%d")
    print(f"Processing games for {yesterday}")

    # Fetch finalized NBA events from yesterday.
    # Use explicit UTC datetime strings so West Coast games
    # (which tip ~10:30pm ET = 3:30am UTC next day) are never missed.
    yesterday_start_utc = (
        datetime(*map(int, yesterday.split("-")), 5, 0, 0, tzinfo=timezone.utc)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    today_end_utc = (
        datetime(*map(int, yesterday.split("-")), 5, 0, 0, tzinfo=timezone.utc)
        + timedelta(days=1)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    events = fetch_all_events({
        "leagueID":      "NBA",
        "finalized":     "true",
        "startsAfter":   yesterday_start_utc,
        "startsBefore":  today_end_utc,
        "oddID":         "points-home-game-sp-home,points-all-game-ou-over",
        "expandResults": "true",
    })

    if not events:
        print(f"No finalized NBA games found for {yesterday}")
        return

    print(f"Found {len(events)} finalized games")

    # Fetch last 3 days of games from BDL for B2B detection.
    # V3 only needs 1 prior day for B2B, but fetch 3 for safety buffer.
    y, m, d  = map(int, yesterday.split("-"))
    hist_end   = yesterday  # exclusive: stop before yesterday's games
    hist_start = (datetime(y, m, d) - timedelta(days=3)).strftime("%Y-%m-%d")
    history_games = fetch_bdl_history(hist_start, hist_end)
    print(f"Fetched {len(history_games)} history games (BDL, last 3 days) for B2B detection")

    # Build team history keyed by abbreviation.
    # BDL provides a "datetime" UTC ISO string for actual tip time.
    # V3 needs et_date (datetime.date) and home_abbr for schedule context.
    team_history = {}
    for g in history_games:
        home_abbr_h = g["home_team"]["abbreviation"]
        away_abbr_h = g["visitor_team"]["abbreviation"]
        starts_at = g.get("datetime") or (g["date"][:10] + "T00:30:00Z")
        et_dt = datetime.fromisoformat(starts_at.replace("Z", "+00:00")).astimezone(ET).date()
        rec = {
            "starts_at": starts_at,
            "home_abbr": home_abbr_h,
            "away_abbr": away_abbr_h,
            "et_date": et_dt,
        }
        team_history.setdefault(home_abbr_h, []).append(rec)
        team_history.setdefault(away_abbr_h, []).append(rec)

    for abbr_key in team_history:
        team_history[abbr_key].sort(key=lambda x: x["starts_at"])

    # Parse yesterday as a date object for V3 signal detection
    game_date = datetime.strptime(yesterday, "%Y-%m-%d").date()

    # Load existing V3 results
    results_path = os.path.join(os.path.dirname(__file__), "..", "data", "results_v3.json")
    results_path = os.path.normpath(results_path)
    try:
        with open(results_path) as f:
            existing = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        existing = {
            "version": "3.0",
            "games": [],
            "meta": {
                "last_updated": None,
                "model_version": "V3-S2",
                "historical_rate": "56.8% away ATS [50.8-62.6%] (5 seasons, N=270)",
            },
        }

    existing_ids = {g["event_id"] for g in existing["games"]}
    new_games = []

    for event in events:
        eid = event["eventID"]
        if eid in existing_ids:
            print(f"  Skip {eid} (already logged)")
            continue

        home_obj = event["teams"]["home"]
        away_obj = event["teams"]["away"]
        home     = abbr(home_obj)
        away     = abbr(away_obj)

        # Final scores: SGO puts score on the odd object itself (per handling-odds guide).
        # points-all-game-ou-over.score = total points scored (both teams combined).
        # points-home-game-sp-home.score = home team points.
        # Derive away score = total - home.
        odds_raw = event.get("odds", {})
        ou_odd   = odds_raw.get("points-all-game-ou-over", {})
        sp_odd   = odds_raw.get("points-home-game-sp-home", {})

        total_pts = ou_odd.get("score")
        home_pts  = sp_odd.get("score")

        # Fallback: try event.results if odd scores aren't populated
        if total_pts is None or home_pts is None:
            results_raw = event.get("results", {})
            if home_pts is None:
                home_pts = (results_raw.get("home", {}) or {}).get("score")
            if total_pts is None:
                away_pts_r = (results_raw.get("away", {}) or {}).get("score")
                if home_pts is not None and away_pts_r is not None:
                    total_pts = float(home_pts) + float(away_pts_r)

        if total_pts is None or home_pts is None:
            print(f"  Skip {away} @ {home}: no final score in odds or results")
            continue

        home_score = float(home_pts)
        away_score = float(total_pts) - home_score

        # V3 signal detection — simple B2B + travel
        signals = detect_v3_signals(home, away, game_date, team_history)
        if not signals:
            print(f"  Skip {away} @ {home}: no V3 signals")
            continue

        # Get closing lines and outcomes
        outcomes = compute_outcomes(event)
        close_spread = outcomes["close_spread"]
        close_total  = outcomes["close_total"]

        # ATS grading
        ats_result = None
        if close_spread is not None:
            margin = home_score - away_score
            net = margin + close_spread
            ats_result = "push" if net == 0 else ("home" if net > 0 else "away")

        # O/U grading
        ou_result = outcomes["ou_result"]
        if ou_result is None and close_total is not None:
            total_final = home_score + away_score
            if total_final > close_total:   ou_result = "over"
            elif total_final < close_total: ou_result = "under"
            else:                           ou_result = "push"

        # Log one record per signal (S2 and B2 are mutually exclusive:
        # S2 requires away NOT B2B, B2 requires away B2B)
        for sig in signals:
            signal_result = grade_signal(sig["signal"], ats_result)
            home_ctx = sig["home_ctx"]
            away_ctx = sig["away_ctx"]

            rec = {
                "date":            yesterday,
                "event_id":        eid,
                "matchup":         f"{away} @ {home}",
                "away":            away,
                "home":            home,
                "away_score":      int(away_score),
                "home_score":      int(home_score),
                "signal":          sig["signal"],
                "signal_detail":   sig["detail"],
                "home_b2b":        home_ctx["is_b2b"],
                "home_traveled":   home_ctx["traveled"],
                "home_travel_dist": home_ctx["travel_dist"],
                "away_b2b":        away_ctx["is_b2b"],
                "close_spread":    close_spread,
                "close_total":     close_total,
                "ats_result":      ats_result,
                "ou_result":       ou_result,
                "signal_result":   signal_result,
            }

            new_games.append(rec)
            print(f"  LOGGED: {away} @ {home} | {sig['signal']} | {sig['detail']} | result={signal_result}")

    if new_games:
        existing["games"].extend(new_games)
        existing["games"].sort(key=lambda x: x["date"])
        existing["meta"]["last_updated"] = now_et.strftime("%Y-%m-%d %H:%M ET")

        os.makedirs(os.path.dirname(results_path), exist_ok=True)
        with open(results_path, "w") as f:
            json.dump(existing, f, indent=2)
        print(f"\nWrote {len(new_games)} new V3 signals to results_v3.json ({len(existing['games'])} total)")
    else:
        print("\nNo new V3 signals to log today")

if __name__ == "__main__":
    main()
