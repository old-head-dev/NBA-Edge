#!/usr/bin/env python3
"""
NBA Edge Backtest Grader
- Scores:        BallDontLie API  (env: BDL_API_KEY)
- Closing lines: The Odds API     (env: ODDS_API_KEY)

Usage:
    python grade_backtest.py --input NBA_Backtest_24_25.xlsx --output graded_backtest_24_25.csv
    python grade_backtest.py --input NBA_Backtest_24_25.csv --output graded_output.csv
"""

import os, csv, time, requests, openpyxl, argparse
from datetime import datetime, timezone, timedelta
from collections import defaultdict

# ── CONFIG ────────────────────────────────────────────────────────
BDL_KEY  = os.environ.get("BDL_API_KEY", "")
ODDS_KEY = os.environ.get("ODDS_API_KEY", "")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

BDL_BASE  = "https://api.balldontlie.io/v1"
ODDS_BASE = "https://api.the-odds-api.com/v4"
SPORT     = "basketball_nba"

# ── ARG PARSING ───────────────────────────────────────────────────
def parse_args():
    p = argparse.ArgumentParser(description="NBA Edge Backtest Grader")
    p.add_argument("--input", required=True, help="Input file (.xlsx or .csv)")
    p.add_argument("--output", required=True, help="Output CSV file path")
    return p.parse_args()

TEAM_NAMES = {
    "ATL":"Atlanta Hawks",        "BOS":"Boston Celtics",
    "BKN":"Brooklyn Nets",        "CHA":"Charlotte Hornets",
    "CHI":"Chicago Bulls",        "CLE":"Cleveland Cavaliers",
    "DAL":"Dallas Mavericks",     "DEN":"Denver Nuggets",
    "DET":"Detroit Pistons",      "GSW":"Golden State Warriors",
    "HOU":"Houston Rockets",      "IND":"Indiana Pacers",
    "LAC":"Los Angeles Clippers",          "LAL":"Los Angeles Lakers",
    "MEM":"Memphis Grizzlies",    "MIA":"Miami Heat",
    "MIL":"Milwaukee Bucks",      "MIN":"Minnesota Timberwolves",
    "NOP":"New Orleans Pelicans", "NYK":"New York Knicks",
    "OKC":"Oklahoma City Thunder","ORL":"Orlando Magic",
    "PHI":"Philadelphia 76ers",   "PHX":"Phoenix Suns",
    "POR":"Portland Trail Blazers","SAC":"Sacramento Kings",
    "SAS":"San Antonio Spurs",    "TOR":"Toronto Raptors",
    "UTA":"Utah Jazz",            "WAS":"Washington Wizards",
}

# ── LOAD XLSX ─────────────────────────────────────────────────────
def load_games_xlsx(path):
    wb = openpyxl.load_workbook(path)
    ws = wb.active
    games = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row[0]:
            continue
        date_val = row[0]
        if isinstance(date_val, datetime):
            game_date = date_val.date()
        else:
            game_date = datetime.strptime(str(date_val)[:10], "%Y-%m-%d").date()

        away_fat = float(row[4]) if row[4] is not None else 0.0
        home_fat = float(row[5]) if row[5] is not None else 0.0

        games.append({
            "date":          game_date,
            "matchup":       row[1] or "",
            "away":          row[2] or "",
            "home":          row[3] or "",
            "away_fatigue":  away_fat,
            "home_fatigue":  home_fat,
            "max_fatigue":   float(row[6]) if row[6] is not None else 0.0,
            "flagged_team":  row[7] or "",
            "edge_side":     row[8] or "",
            "away_scenario": row[9] or "",
            "home_scenario": row[10] or "",
            "away_days_rest":row[11] if row[11] is not None else "",
            "home_days_rest":row[12] if row[12] is not None else "",
            "away_sleep":    row[13] if row[13] is not None else "",
            "home_sleep":    row[14] if row[14] is not None else "",
            "away_detail":   row[15] or "",
            "home_detail":   row[16] or "",
            "both_tired":    away_fat >= 5.0 and home_fat >= 5.0,
        })
    return games

# ── LOAD CSV ──────────────────────────────────────────────────────
def load_games_csv(path):
    games = []
    with open(path, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            r = {k.lower().strip().replace(' ', '_'): v for k, v in row.items()}
            away_fat = float(r.get('away_fatigue', r.get('away_score', 0)) or 0)
            home_fat = float(r.get('home_fatigue', r.get('home_score', 0)) or 0)
            games.append({
                "date": datetime.strptime(r['date'][:10], "%Y-%m-%d").date(),
                "matchup": r.get('matchup', ''),
                "away": r.get('away', ''),
                "home": r.get('home', ''),
                "away_fatigue": away_fat,
                "home_fatigue": home_fat,
                "max_fatigue": float(r.get('max_fatigue', r.get('max_score', 0)) or 0),
                "flagged_team": r.get('flagged_team', ''),
                "edge_side": r.get('edge_side', ''),
                "away_scenario": r.get('away_scenario', ''),
                "home_scenario": r.get('home_scenario', ''),
                "away_days_rest": r.get('away_days_rest', ''),
                "home_days_rest": r.get('home_days_rest', ''),
                "away_sleep": r.get('away_sleep', r.get('away_est_sleep', '')),
                "home_sleep": r.get('home_sleep', r.get('home_est_sleep', '')),
                "away_detail": r.get('away_detail', ''),
                "home_detail": r.get('home_detail', ''),
                "edge_team_wpct": r.get('edge_team_wpct', ''),
                "both_tired": away_fat >= 5.0 and home_fat >= 5.0,
            })
    return games

def load_games(path):
    if path.endswith('.xlsx'):
        return load_games_xlsx(path)
    elif path.endswith('.csv'):
        return load_games_csv(path)
    else:
        raise ValueError(f"Unsupported file format: {path}")

# ── BDL: FETCH SCORES ─────────────────────────────────────────────
def bdl_fetch_scores(date_str):
    """Fetch final scores for a given ET date from BallDontLie."""
    headers = {"Authorization": BDL_KEY}
    url = f"{BDL_BASE}/games"
    params = {"dates[]": date_str, "per_page": 100}
    try:
        r = requests.get(url, headers=headers, params=params, timeout=20)
        if r.status_code != 200:
            print(f"    BDL error {r.status_code}: {r.text[:150]}")
            return {}
        data = r.json().get("data", [])
    except Exception as e:
        print(f"    BDL exception: {e}")
        return {}

    scores = {}
    for g in data:
        if g.get("status") != "Final":
            continue
        away_abbr = g["visitor_team"]["abbreviation"]
        home_abbr = g["home_team"]["abbreviation"]
        key = (away_abbr, home_abbr)
        scores[key] = {
            "away_score": g.get("visitor_team_score"),
            "home_score": g.get("home_team_score"),
        }
    return scores

# ── ODDS API: FETCH CLOSING LINES ─────────────────────────────────
def odds_fetch_lines(date_str):
    """
    Fetch closing lines from The Odds API historical endpoint.
    Snapshot ~1hr before earliest tip (19:00 UTC = 2pm ET) captures
    pre-game closing lines for all games that day.
    Cost: 30 credits (3 markets x 1 region).
    """
    y, m, d = map(int, date_str.split("-"))
    # 19:00 UTC on game date = ~2pm ET, well before any tip but after line movement
    snapshot = datetime(y, m, d, 19, 0, 0, tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    params = {
        "apiKey":    ODDS_KEY,
        "regions":   "us",
        "markets":   "spreads,totals,h2h",
        "oddsFormat":"american",
        "date":      snapshot,
    }
    try:
        r = requests.get(
            f"{ODDS_BASE}/historical/sports/{SPORT}/odds",
            params=params, timeout=20
        )
        remaining = r.headers.get("x-requests-remaining", "?")
        used      = r.headers.get("x-requests-used", "?")
        print(f"    [quota] used={used}  remaining={remaining}")
        if r.status_code != 200:
            print(f"    Odds API error {r.status_code}: {r.text[:150]}")
            return {}
        events = r.json().get("data", [])
    except Exception as e:
        print(f"    Odds API exception: {e}")
        return {}

    lines = {}
    for ev in events:
        away_full = ev.get("away_team", "")
        home_full = ev.get("home_team", "")
        # Match to our abbreviations
        away_abbr = next((k for k, v in TEAM_NAMES.items() if v == away_full), None)
        home_abbr = next((k for k, v in TEAM_NAMES.items() if v == home_full), None)
        if not away_abbr or not home_abbr:
            continue

        bks = ev.get("bookmakers", [])
        home_spread = _avg_point(bks, "spreads", home_full)
        close_total = _avg_point(bks, "totals",  "Over")
        home_ml     = _avg_price(bks, "h2h",     home_full)
        away_ml     = _avg_price(bks, "h2h",     away_full)

        lines[(away_abbr, home_abbr)] = {
            "home_spread": home_spread,
            "close_total": close_total,
            "home_ml":     home_ml,
            "away_ml":     away_ml,
        }

    return lines

def _avg_point(bookmakers, market_key, outcome_name):
    vals = []
    name_lower = outcome_name.lower()
    for bk in bookmakers:
        for mkt in bk.get("markets", []):
            if mkt["key"] != market_key:
                continue
            for o in mkt.get("outcomes", []):
                if o.get("name", "").lower() == name_lower:
                    v = o.get("point")
                    if v is not None:
                        vals.append(float(v))
    return round(sum(vals) / len(vals), 1) if vals else None

def _avg_price(bookmakers, market_key, outcome_name):
    vals = []
    name_lower = outcome_name.lower()
    for bk in bookmakers:
        for mkt in bk.get("markets", []):
            if mkt["key"] != market_key:
                continue
            for o in mkt.get("outcomes", []):
                if o.get("name", "").lower() == name_lower:
                    v = o.get("price")
                    if v is not None:
                        vals.append(float(v))
    return round(sum(vals) / len(vals), 0) if vals else None

# ── GRADING ───────────────────────────────────────────────────────
def grade_ats(home_score, away_score, home_spread):
    if None in (home_spread, home_score, away_score):
        return None
    net = (home_score - away_score) + home_spread
    if net > 0:  return "home"
    if net < 0:  return "away"
    return "push"

def grade_ou(home_score, away_score, total_line):
    if None in (total_line, home_score, away_score):
        return None
    total = home_score + away_score
    if total > total_line: return "over"
    if total < total_line: return "under"
    return "push"

def grade_ml(home_score, away_score):
    if None in (home_score, away_score):
        return None
    if home_score > away_score: return "home"
    if away_score > home_score: return "away"
    return "push"

def edge_ats_result(ats, edge_side):
    if not ats or not edge_side or edge_side == "EVEN":
        return None
    edge_team = "home" if "HOME" in edge_side else "away"
    if ats == "push":    return "PUSH"
    if ats == edge_team: return "WIN"
    return "LOSS"

def under_result(ou):
    if ou is None:    return None
    if ou == "under": return "WIN"
    if ou == "push":  return "PUSH"
    return "LOSS"

# ── MAIN ──────────────────────────────────────────────────────────
def main():
    args = parse_args()

    if not BDL_KEY:
        print("ERROR: BDL_API_KEY not set.  $env:BDL_API_KEY=\"your_key\"")
        return
    if not ODDS_KEY:
        print("ERROR: ODDS_API_KEY not set.  $env:ODDS_API_KEY=\"your_key\"")
        return

    input_path = os.path.join(SCRIPT_DIR, args.input) if not os.path.isabs(args.input) else args.input
    output_path = os.path.join(SCRIPT_DIR, args.output) if not os.path.isabs(args.output) else args.output

    print(f"Loading: {input_path}\n")
    games = load_games(input_path)
    both_count = sum(1 for g in games if g["both_tired"])
    print(f"Loaded {len(games)} flagged games")
    print(f"  Both tired: {both_count}  |  Directional: {len(games)}\n")

    by_date = defaultdict(list)
    for g in games:
        by_date[g["date"]].append(g)

    results     = []
    missing_scores = 0
    missing_lines  = 0
    total_dates = len(by_date)

    for di, (game_date, day_games) in enumerate(sorted(by_date.items()), 1):
        date_str = game_date.strftime("%Y-%m-%d")
        print(f"[{di}/{total_dates}] {date_str} — {len(day_games)} game(s)")

        # 1. Scores from BDL (free, no credit cost)
        scores = bdl_fetch_scores(date_str)
        print(f"    BDL: {len(scores)} final games found")

        # 2. Closing lines from Odds API (30 credits per date)
        lines = odds_fetch_lines(date_str)
        print(f"    Odds API: {len(lines)} games with lines")

        for g in day_games:
            away, home = g["away"], g["home"]
            key = (away, home)

            # Scores
            sc = scores.get(key, {})
            home_score = sc.get("home_score")
            away_score = sc.get("away_score")
            if home_score is None:
                missing_scores += 1

            # Lines
            ln = lines.get(key, {})
            home_spread = ln.get("home_spread")
            close_total = ln.get("close_total")
            home_ml     = ln.get("home_ml")
            away_ml     = ln.get("away_ml")
            if home_spread is None:
                missing_lines += 1

            # Grade
            ats = grade_ats(home_score, away_score, home_spread)
            ou  = grade_ou(home_score, away_score, close_total)
            ml  = grade_ml(home_score, away_score)
            e_ats   = edge_ats_result(ats, g["edge_side"])
            u_result = under_result(ou) if g["both_tired"] else None

            status = "OK" if (home_score is not None and home_spread is not None) else \
                     "NO_SCORE" if home_score is None else "NO_LINE"
            print(f"    {away} @ {home}: score={away_score}-{home_score}  "
                  f"spread={home_spread}  total={close_total}  "
                  f"edge={e_ats}  under={u_result}  [{status}]")

            results.append({
                **g,
                "date":          date_str,
                "away_score":    int(away_score) if away_score is not None else "",
                "home_score":    int(home_score) if home_score is not None else "",
                "home_spread":   home_spread  if home_spread  is not None else "",
                "close_total":   close_total  if close_total  is not None else "",
                "home_ml":       int(home_ml) if home_ml      is not None else "",
                "away_ml":       int(away_ml) if away_ml      is not None else "",
                "ats_result":    ats          or "",
                "ou_result":     ou           or "",
                "ml_result":     ml           or "",
                "edge_ats":      e_ats        or "",
                "under_result":  u_result     or "",
            })

        time.sleep(12)  # light rate limit buffer

    # ── Write CSV ─────────────────────────────────────────────────
    fields = [
        "date","matchup","away","home",
        "away_fatigue","home_fatigue","max_fatigue","both_tired",
        "edge_side","flagged_team",
        "away_scenario","home_scenario",
        "away_days_rest","home_days_rest",
        "away_sleep","home_sleep",
        "away_detail","home_detail",
        "edge_team_wpct",
        "away_score","home_score",
        "home_spread","close_total","home_ml","away_ml",
        "ats_result","ou_result","ml_result",
        "edge_ats","under_result",
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(results)

    # ── Summary ───────────────────────────────────────────────────
    print(f"\n{'='*55}")
    print(f"Output: {output_path}")
    print(f"Total: {len(results)}  |  Missing scores: {missing_scores}  |  Missing lines: {missing_lines}")

    edge_games  = [r for r in results if r["edge_ats"]]
    under_games = [r for r in results if r["under_result"]]

    if edge_games:
        w2 = sum(1 for r in edge_games if r["edge_ats"] == "WIN")
        l  = sum(1 for r in edge_games if r["edge_ats"] == "LOSS")
        p  = sum(1 for r in edge_games if r["edge_ats"] == "PUSH")
        pct = round(w2/(w2+l)*100, 1) if (w2+l) else 0
        print(f"Edge ATS:  {w2}W {l}L {p}P  ({pct}%)")

    if under_games:
        w2 = sum(1 for r in under_games if r["under_result"] == "WIN")
        l  = sum(1 for r in under_games if r["under_result"] == "LOSS")
        p  = sum(1 for r in under_games if r["under_result"] == "PUSH")
        pct = round(w2/(w2+l)*100, 1) if (w2+l) else 0
        print(f"Under:     {w2}W {l}L {p}P  ({pct}%)")

    print(f"{'='*55}")

if __name__ == "__main__":
    main()
