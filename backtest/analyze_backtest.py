#!/usr/bin/env python3
"""
NBA Edge Model — Backtest Analysis Script
Runs full ATS and Under analysis against any graded backtest CSV.

Usage:
    python analyze_backtest.py graded_backtest_24_25.csv
    python analyze_backtest.py NBA_Backtest_graded.csv

Output: printed report + analysis_results.txt
"""

import csv, sys, statistics
from collections import defaultdict

# ── LOAD ──────────────────────────────────────────────────────────
def load(path):
    rows = []
    with open(path, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            rows.append({k.lower().strip().replace(' ', '_'): v for k, v in row.items()})
    print(f"Loaded {len(rows)} rows from {path}\n")
    return rows

# ── HELPERS ───────────────────────────────────────────────────────
def wl(games, field='edge_ats'):
    w = sum(1 for g in games if g[field].upper() == 'WIN')
    l = sum(1 for g in games if g[field].upper() == 'LOSS')
    p = sum(1 for g in games if g[field].upper() == 'PUSH')
    pct = round(w / (w + l) * 100, 1) if (w + l) else 0
    return w, l, p, pct, len(games)

def fmt(w, l, p, pct, n, min_n=30):
    flag = "" if n >= min_n else f"  * PRELIMINARY n={n}"
    return f"{w}W {l}L {p}P  {pct}%  (n={n}){flag}"

# Fatigue accessors — works regardless of column name casing
def _get(row, *keys):
    for k in keys:
        if k in row: return row[k]
    return ""

def away_fat(r):  return float(_get(r, 'away_fatigue', 'away_score') or 0)
def home_fat(r):  return float(_get(r, 'home_fatigue', 'home_score') or 0)
def edge_side(r): return _get(r, 'edge_side').upper()
def away_scen(r): return _get(r, 'away_scenario')
def home_scen(r): return _get(r, 'home_scenario')
def away_det(r):  return _get(r, 'away_detail')
def home_det(r):  return _get(r, 'home_detail')
def spread(r):
    v = _get(r, 'home_spread')
    return float(v) if v not in ('', None) else None
def ats_val(r):   return _get(r, 'edge_ats')
def under_val(r): return _get(r, 'under_result')
def close_tot(r):
    v = _get(r, 'close_total')
    return float(v) if v not in ('', None) else None

def edge_wpct(r):
    v = _get(r, 'edge_team_wpct')
    return float(v) if v not in ('', None, 'None') else None

def fat_delta(r): return abs(away_fat(r) - home_fat(r))

def fatigued_score(r):
    return away_fat(r) if 'HOME' in edge_side(r) else home_fat(r)

def fresh_score(r):
    return home_fat(r) if 'HOME' in edge_side(r) else away_fat(r)

def fatigued_scen(r):
    return away_scen(r) if 'HOME' in edge_side(r) else home_scen_from_detail(r)

def home_scen_from_detail(r):
    d = home_det(r)
    if 'BTB home' in d and 'flew' in d: return 'C'
    if 'home-home' in d.lower(): return 'home-home'
    if 'home\u2192away' in d or 'home->away' in d: return 'B'
    return 'other'

def btb_scen_from_detail(detail):
    if 'BTB road' in detail: return 'A'
    if 'home\u2192away' in detail or 'BTB home\u2192away' in detail: return 'B'
    if 'BTB home' in detail and 'flew' in detail: return 'C'
    if 'home-home' in detail.lower(): return 'home-home'
    if 'BTB' in detail: return 'BTB-other'
    return 'non-BTB'

# ── REPORT BUILDER ────────────────────────────────────────────────
lines_out = []

def section(title):
    s = f"\n{'='*65}\n  {title}\n{'='*65}"
    print(s); lines_out.append(s)

def sub(title):
    s = f"\n--- {title} ---"
    print(s); lines_out.append(s)

def row(label, record):
    s = f"  {label:<50s} {record}"
    print(s); lines_out.append(s)

def blank():
    print(""); lines_out.append("")

# ── ATS ANALYSIS ─────────────────────────────────────────────────
def analyze_ats(rows):
    edge = [r for r in rows if ats_val(r).upper() in ('WIN','LOSS','PUSH')]
    if not edge:
        print("No Edge ATS games found — check column names in CSV.")
        return

    home_edge = [r for r in edge if 'HOME' in edge_side(r)]
    away_edge = [r for r in edge if 'AWAY' in edge_side(r)]

    section("EDGE ATS ANALYSIS")

    sub("OVERALL")
    row("Overall", fmt(*wl(edge, 'edge_ats')))
    row("HOME EDGE (bet home as flagged)", fmt(*wl(home_edge, 'edge_ats')))
    row("AWAY EDGE (bet away as flagged)", fmt(*wl(away_edge, 'edge_ats')))

    # HOME EDGE flipped
    sub("HOME EDGE — FLIPPED (bet the away/road team)")
    w_f = sum(1 for r in home_edge if ats_val(r).upper() == 'LOSS')
    l_f = sum(1 for r in home_edge if ats_val(r).upper() == 'WIN')
    p_f = sum(1 for r in home_edge if ats_val(r).upper() == 'PUSH')
    pct_f = round(w_f/(w_f+l_f)*100,1) if (w_f+l_f) else 0
    row("Bet AWAY in HOME EDGE games", fmt(w_f, l_f, p_f, pct_f, len(home_edge)))
    for t in [2, 4, 5, 6, 7, 8]:
        g = [r for r in home_edge if fat_delta(r) >= t]
        if g:
            wf = sum(1 for r in g if ats_val(r).upper() == 'LOSS')
            lf = sum(1 for r in g if ats_val(r).upper() == 'WIN')
            pf = sum(1 for r in g if ats_val(r).upper() == 'PUSH')
            pctf = round(wf/(wf+lf)*100,1) if (wf+lf) else 0
            row(f"  Bet AWAY + delta >= {t}", fmt(wf, lf, pf, pctf, len(g)))

    sub("HOME EDGE FLIPPED — by spread bucket")
    buckets = [
        ('Home -7 or more',     lambda x: x <= -7),
        ('Home -3 to -6.5',     lambda x: -6.5 <= x <= -3),
        ('Home -2.5 to -0.5',   lambda x: -2.5 <= x <= -0.5),
        ('Pick / Dog (+0 to +6)',lambda x: x >= 0),
    ]
    for label, fn in buckets:
        g = [r for r in home_edge if spread(r) is not None and fn(spread(r))]
        if g:
            wf = sum(1 for r in g if ats_val(r).upper() == 'LOSS')
            lf = sum(1 for r in g if ats_val(r).upper() == 'WIN')
            pf = sum(1 for r in g if ats_val(r).upper() == 'PUSH')
            pctf = round(wf/(wf+lf)*100,1) if (wf+lf) else 0
            row(f"  Bet AWAY + {label}", fmt(wf, lf, pf, pctf, len(g)))

    sub("AWAY EDGE — by delta threshold")
    for t in [2, 3, 4, 5, 6, 7, 8]:
        g = [r for r in away_edge if fat_delta(r) >= t]
        if g:
            row(f"  Delta >= {t}", fmt(*wl(g,'edge_ats')))

    sub("AWAY EDGE — home team spread")
    g = [r for r in away_edge if spread(r) is not None and spread(r) < 0]
    if g: row("  Home is FAVORITE", fmt(*wl(g,'edge_ats')))
    g = [r for r in away_edge if spread(r) is not None and spread(r) > 0]
    if g: row("  Home is UNDERDOG", fmt(*wl(g,'edge_ats')))

    sub("AWAY EDGE — home favorite + delta threshold (KEY RULE)")
    for t in [3, 4, 5, 6, 7]:
        g = [r for r in away_edge if spread(r) is not None and spread(r) < 0 and fat_delta(r) >= t]
        if g:
            row(f"  Home fav + delta >= {t}", fmt(*wl(g,'edge_ats')))

    sub("AWAY EDGE — by fatigued home scenario")
    scens = defaultdict(list)
    for r in away_edge:
        scens[home_scen_from_detail(r)].append(r)
    for s, g in sorted(scens.items()):
        row(f"  Home scenario={s}", fmt(*wl(g,'edge_ats')))

    sub("AWAY EDGE — Scenario C home + delta thresholds")
    c_games = [r for r in away_edge if home_scen_from_detail(r) == 'C']
    for t in [2, 3, 4, 5]:
        g = [r for r in c_games if fat_delta(r) >= t]
        if g: row(f"  ScenC + delta >= {t}", fmt(*wl(g,'edge_ats')))

    sub("HOME EDGE — by away BTB scenario (from detail)")
    he_scens = defaultdict(list)
    for r in home_edge:
        he_scens[btb_scen_from_detail(away_det(r))].append(r)
    for s, g in sorted(he_scens.items()):
        row(f"  Away scenario={s}", fmt(*wl(g,'edge_ats')))

    sub("EDGE ATS — by month")
    months = defaultdict(list)
    for r in edge:
        months[_get(r,'date')[:7]].append(r)
    for m in sorted(months):
        g = months[m]
        he = [r for r in g if 'HOME' in edge_side(r)]
        ae = [r for r in g if 'AWAY' in edge_side(r)]
        wt,lt,pt,pctt,nt = wl(g)
        whe,lhe,_,phe,nhe = wl(he) if he else (0,0,0,0,0)
        wae,lae,_,pae,nae = wl(ae) if ae else (0,0,0,0,0)
        s = f"  {m}: {wt}W {lt}L {pctt}%  (n={nt}) | HOME_EDGE:{whe}W{lhe}L {phe}% (n={nhe}) | AWAY_EDGE:{wae}W{lae}L {pae}% (n={nae})"
        print(s); lines_out.append(s)

# ── UNDER ANALYSIS ────────────────────────────────────────────────
def analyze_under(rows):
    both = [r for r in rows if under_val(r).upper() in ('WIN','LOSS','PUSH')]
    if not both:
        print("No both-tired under games found.")
        return

    section("UNDER EDGE ANALYSIS (Both Tired >= 5)")

    sub("BASELINE")
    row("Overall both-tired under", fmt(*wl(both, 'under_result')))

    sub("BY MAX FATIGUE SCORE")
    for t in [5, 6, 7, 8, 9]:
        g = [r for r in both if max(away_fat(r), home_fat(r)) >= t]
        if g: row(f"  Max score >= {t}", fmt(*wl(g,'under_result')))

    sub("BY COMBINED FATIGUE SCORE")
    for t in [10, 11, 12, 13, 14, 15]:
        g = [r for r in both if away_fat(r) + home_fat(r) >= t]
        if g: row(f"  Combined >= {t}", fmt(*wl(g,'under_result')))

    sub("BY FATIGUE DELTA BETWEEN TEAMS")
    for t in [0, 1, 2, 3, 4]:
        g = [r for r in both if fat_delta(r) <= t]
        if g: row(f"  Delta <= {t} (evenly tired)", fmt(*wl(g,'under_result')))
    blank()
    for t in [2, 3, 4, 5]:
        g = [r for r in both if fat_delta(r) >= t]
        if g: row(f"  Delta >= {t} (one much worse)", fmt(*wl(g,'under_result')))

    sub("BY AWAY TEAM SCENARIO")
    scens = defaultdict(list)
    for r in both:
        scens[away_scen(r)].append(r)
    for s, g in sorted(scens.items()):
        row(f"  Away={s}", fmt(*wl(g,'under_result')))

    sub("BY HOME TEAM SCENARIO (from detail)")
    hscens = defaultdict(list)
    for r in both:
        hscens[home_scen_from_detail(r)].append(r)
    for s, g in sorted(hscens.items()):
        row(f"  Home={s}", fmt(*wl(g,'under_result')))

    sub("SCENARIO COMBOS (Away + Home)")
    combos = defaultdict(list)
    for r in both:
        k = f"Away={away_scen(r)} / Home={home_scen_from_detail(r)}"
        combos[k].append(r)
    for k, g in sorted(combos.items(), key=lambda x: -len(x[1])):
        row(f"  {k}", fmt(*wl(g,'under_result')))

    sub("KEY RULE: Away=A + Home=home-home + thresholds")
    base = [r for r in both if away_scen(r) == 'A' and home_scen_from_detail(r) == 'home-home']
    if base:
        row("  Baseline", fmt(*wl(base,'under_result')))
        for t in [2, 3, 4]:
            g = [r for r in base if fat_delta(r) >= t]
            if g: row(f"  + delta >= {t}", fmt(*wl(g,'under_result')))

    sub("Away=A (all home scenarios)")
    a_all = [r for r in both if away_scen(r) == 'A']
    if a_all: row("  Away=A all", fmt(*wl(a_all,'under_result')))

    sub("CLOSING TOTAL BUCKETS")
    tbuckets = [
        ('Total <= 220',      lambda x: x <= 220),
        ('Total 220.5-227',   lambda x: 220.5 <= x <= 227),
        ('Total 227.5-234',   lambda x: 227.5 <= x <= 234),
        ('Total 234.5+',      lambda x: x >= 234.5),
    ]
    for label, fn in tbuckets:
        g = [r for r in both if close_tot(r) is not None and fn(close_tot(r))]
        if g: row(f"  {label}", fmt(*wl(g,'under_result')))

    sub("Away=A + CLOSING TOTAL BUCKETS")
    for label, fn in tbuckets:
        g = [r for r in both if away_scen(r) == 'A' and close_tot(r) is not None and fn(close_tot(r))]
        if g: row(f"  Away=A + {label}", fmt(*wl(g,'under_result')))

    sub("BY MONTH")
    months = defaultdict(list)
    for r in both:
        months[_get(r,'date')[:7]].append(r)
    for m in sorted(months):
        g = months[m]
        tots = [close_tot(r) for r in g if close_tot(r)]
        avg_t = round(sum(tots)/len(tots),1) if tots else 0
        w,l,p,pct,n = wl(g,'under_result')
        s = f"  {m}: {w}W {l}L {p}P  {pct}%  (n={n})  avg_total={avg_t}"
        print(s); lines_out.append(s)

    sub("SLEEP ESTIMATES: WINS vs LOSSES")
    def sleep_avg(games, result, side):
        cap = side.capitalize(); key = f'{side}_sleep' if games and f'{side}_sleep' in games[0] else f'{cap.lower()} est sleep'
        vals = [float(r[key]) for r in games if under_val(r).upper() == result.upper() and r.get(key,'') not in ('','None','null')]
        if vals:
            return round(statistics.mean(vals), 1), len(vals)
        return None, 0
    for result in ['WIN','LOSS']:
        for side in ['away','home']:
            avg, n = sleep_avg(both, result, side)
            if avg is not None:
                row(f"  {result} {side} est sleep avg", f"{avg} hrs (n={n})")

# ── TEAM QUALITY ANALYSIS ─────────────────────────────────────────
def analyze_quality(rows):
    edge = [r for r in rows if ats_val(r).upper() in ('WIN','LOSS','PUSH')]
    has_wpct = [r for r in edge if edge_wpct(r) is not None]
    if not has_wpct:
        print("\nNo edge_team_wpct data found — skipping quality analysis.")
        return

    section("TEAM QUALITY FILTER")

    sub("EDGE TEAM WIN% THRESHOLDS")
    for t in [.300, .350, .400, .450]:
        g = [r for r in has_wpct if edge_wpct(r) >= t]
        if g: row(f"  Edge team wpct >= {t:.3f}", fmt(*wl(g, 'edge_ats')))

    sub("AWAY EDGE + HOME FAVORITE + QUALITY FILTER")
    away_fav = [r for r in has_wpct if 'AWAY' in edge_side(r) and spread(r) is not None and spread(r) < 0]
    for t in [.300, .350, .400, .450]:
        g = [r for r in away_fav if edge_wpct(r) >= t]
        if g: row(f"  Away edge + home fav + wpct >= {t:.3f}", fmt(*wl(g, 'edge_ats')))

    sub("EXCLUDED GAMES (below quality threshold)")
    for t in [.300, .350]:
        g = [r for r in has_wpct if edge_wpct(r) < t]
        if g: row(f"  Edge team wpct < {t:.3f} (would exclude)", fmt(*wl(g, 'edge_ats')))

# ── SUMMARY TABLE ─────────────────────────────────────────────────
def print_summary(rows):
    edge = [r for r in rows if ats_val(r).upper() in ('WIN','LOSS','PUSH')]
    both = [r for r in rows if under_val(r).upper() in ('WIN','LOSS','PUSH')]
    home_edge = [r for r in edge if 'HOME' in edge_side(r)]
    away_edge = [r for r in edge if 'AWAY' in edge_side(r)]

    section("SUMMARY — TOP RULES")

    if edge:
        # Flipped HOME EDGE
        wf = sum(1 for r in home_edge if ats_val(r).upper() == 'LOSS')
        lf = sum(1 for r in home_edge if ats_val(r).upper() == 'WIN')
        pctf = round(wf/(wf+lf)*100,1) if (wf+lf) else 0
        row("Bet AWAY in HOME EDGE games (flipped)", fmt(wf,lf,0,pctf,len(home_edge)))

        g = [r for r in home_edge if fat_delta(r) >= 5]
        if g:
            wf2 = sum(1 for r in g if ats_val(r).upper() == 'LOSS')
            lf2 = sum(1 for r in g if ats_val(r).upper() == 'WIN')
            pctf2 = round(wf2/(wf2+lf2)*100,1) if (wf2+lf2) else 0
            row("  + delta >= 5", fmt(wf2,lf2,0,pctf2,len(g)))

        g = [r for r in away_edge if spread(r) is not None and spread(r) < 0 and fat_delta(r) >= 5]
        if g: row("AWAY EDGE + home fav + delta >= 5", fmt(*wl(g,'edge_ats')))

        g = [r for r in away_edge if home_scen_from_detail(r) == 'C' and fat_delta(r) >= 4]
        if g: row("AWAY EDGE + ScenC home + delta >= 4", fmt(*wl(g,'edge_ats')))

    if both:
        row("Both-tired UNDER baseline", fmt(*wl(both,'under_result')))
        base = [r for r in both if away_scen(r) == 'A' and home_scen_from_detail(r) == 'home-home']
        if base: row("Under: Away=A + Home=home-home", fmt(*wl(base,'under_result')))
        g = [r for r in both if fat_delta(r) >= 4]
        if g: row("Under: delta >= 4", fmt(*wl(g,'under_result')))
        bad = [r for r in both if close_tot(r) is not None and 220.5 <= close_tot(r) <= 227]
        if bad: row("Under: AVOID — total 220.5-227", fmt(*wl(bad,'under_result')))

    blank()
    print("  * = preliminary sample (n < 30)")
    lines_out.append("  * = preliminary sample (n < 30)")

# ── MAIN ──────────────────────────────────────────────────────────
def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "NBA_Backtest_graded.csv"
    rows = load(path)

    analyze_ats(rows)
    analyze_under(rows)
    analyze_quality(rows)   # NEW
    print_summary(rows)

    out_path = path.replace('.csv', '_analysis.txt')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines_out))
    print(f"\n\nFull report saved to: {out_path}")

if __name__ == "__main__":
    main()
