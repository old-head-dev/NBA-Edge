#!/usr/bin/env python3
"""Unexplored pattern analysis — looking for what Sonnet missed."""

import csv
from collections import defaultdict

def load(path):
    rows = []
    with open(path, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            r = {k.lower().strip().replace(' ', '_'): v for k, v in row.items()}
            rows.append(r)
    return rows

s1 = load('graded_backtest_24_25_v2.csv')
s2 = load('graded_backtest_25_26_v2.csv')
all_games = s1 + s2

def g(r, *keys):
    for k in keys:
        if k in r and r[k] not in ('', None, 'None'): return r[k]
    return ''

def fat_a(r): return float(g(r,'away_fatigue') or 0)
def fat_h(r): return float(g(r,'home_fatigue') or 0)
def delta(r): return abs(fat_a(r) - fat_h(r))
def edge(r): return g(r,'edge_side').upper()
def spread(r):
    v = g(r,'home_spread')
    return float(v) if v else None
def ats(r): return g(r,'edge_ats').upper()
def ats_raw(r): return g(r,'ats_result').lower()  # home/away/push — who actually covered
def ou_raw(r): return g(r,'ou_result').lower()
def ml_raw(r): return g(r,'ml_result').lower()
def under_val(r): return g(r,'under_result').upper()
def total(r):
    v = g(r,'close_total')
    return float(v) if v else None
def a_scen(r): return g(r,'away_scenario')
def h_scen_raw(r): return g(r,'home_scenario')
def a_det(r): return g(r,'away_detail')
def h_det(r): return g(r,'home_detail')
def a_rest(r):
    v = g(r,'away_days_rest')
    return int(float(v)) if v else None
def h_rest(r):
    v = g(r,'home_days_rest')
    return int(float(v)) if v else None
def a_sleep(r):
    v = g(r,'away_sleep','away_est_sleep')
    return float(v) if v else None
def h_sleep(r):
    v = g(r,'home_sleep','home_est_sleep')
    return float(v) if v else None
def home_pts(r):
    v = g(r,'home_score')
    return int(v) if v else None
def away_pts(r):
    v = g(r,'away_score')
    return int(v) if v else None
def game_total(r):
    h, a = home_pts(r), away_pts(r)
    return h + a if h is not None and a is not None else None
def wpct(r):
    v = g(r,'edge_team_wpct')
    return float(v) if v else None
def date(r): return g(r,'date')
def dow(r):
    from datetime import datetime
    d = date(r)
    if not d: return None
    return datetime.strptime(d[:10], '%Y-%m-%d').strftime('%A')

def wl(games, field='edge_ats'):
    w = sum(1 for x in games if x.get(field,'').upper() == 'WIN')
    l = sum(1 for x in games if x.get(field,'').upper() == 'LOSS')
    return w, l

def roi(w, l):
    if w+l == 0: return 0
    return round((w * (100.0/110.0) - l) / (w+l) * 100, 1)

def fmt(w, l):
    n = w+l
    if n == 0: return 'no games'
    pct = round(w/n*100.0, 1)
    r = roi(w, l)
    flag = '' if n >= 25 else '  *n=%d' % n
    return '%dW %dL  %.1f%%  ROI:%+.1f%%  (n=%d)%s' % (w, l, pct, r, n, flag)

def h_scen(r):
    d = h_det(r)
    if 'BTB home' in d and 'flew' in d: return 'C'
    if 'home-home' in d.lower(): return 'HH'
    return 'other'

edge_games = [r for r in all_games if ats(r) in ('WIN','LOSS')]
away_edge = [r for r in edge_games if 'AWAY' in edge(r)]
home_edge = [r for r in edge_games if 'HOME' in edge(r)]

# =====================================================================
print('='*70)
print('  UNEXPLORED PATTERN ANALYSIS')
print('='*70)

# === A. MONEYLINE INSTEAD OF ATS ===
print('\n' + '='*70)
print('  A. MONEYLINE — IS THE EDGE STRONGER ON ML THAN ATS?')
print('='*70)
# For AWAY EDGE games, does the away team win OUTRIGHT more often?
print('\n  AWAY EDGE games:')
ae_ml = [r for r in away_edge if ml_raw(r) in ('home','away')]
ml_wins = sum(1 for r in ae_ml if ml_raw(r) == 'away')  # away wins outright
ml_losses = sum(1 for r in ae_ml if ml_raw(r) == 'home')
print('    ML (away wins outright): %s' % fmt(ml_wins, ml_losses))
w,l = wl(away_edge)
print('    ATS (away covers): %s' % fmt(w, l))

# ML with home favorite filter
ae_fav_ml = [r for r in ae_ml if spread(r) is not None and spread(r) < 0]
ml_w = sum(1 for r in ae_fav_ml if ml_raw(r) == 'away')
ml_l = sum(1 for r in ae_fav_ml if ml_raw(r) == 'home')
print('    ML + home fav (upset wins): %s' % fmt(ml_w, ml_l))

# === B. OVER SIGNAL — REVERSE OF UNDER? ===
print('\n' + '='*70)
print('  B. IS THERE AN OVER SIGNAL? (one team tired, one rested)')
print('='*70)
# Hypothesis: when only ONE team is tired and the other is rested,
# the game might go OVER (rested team runs up the score)
one_tired = [r for r in edge_games if ou_raw(r) in ('over','under') and
             not (fat_a(r) >= 5.0 and fat_h(r) >= 5.0)]  # NOT both tired
print('\n  One-sided fatigue games (not both-tired):')
overs = sum(1 for r in one_tired if ou_raw(r) == 'over')
unders = sum(1 for r in one_tired if ou_raw(r) == 'under')
print('    Over rate: %s' % fmt(overs, unders))

# By which side is tired
for label, filt in [
    ('Home tired (AWAY EDGE)', lambda r: 'AWAY' in edge(r)),
    ('Away tired (HOME EDGE)', lambda r: 'HOME' in edge(r)),
]:
    g2 = [r for r in one_tired if filt(r)]
    ov = sum(1 for r in g2 if ou_raw(r) == 'over')
    un = sum(1 for r in g2 if ou_raw(r) == 'under')
    print('    %s: Over=%d Under=%d (%.1f%% over)' % (label, ov, un, ov/(ov+un)*100 if (ov+un) else 0))

# === C. DAY OF WEEK ===
print('\n' + '='*70)
print('  C. DAY OF WEEK EFFECTS')
print('='*70)
days = defaultdict(list)
for r in edge_games:
    d = dow(r)
    if d: days[d].append(r)

day_order = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
print('\n  Edge ATS by day of week:')
for d in day_order:
    if d in days:
        w,l = wl(days[d])
        print('    %s: %s' % (d, fmt(w,l)))

# B2B games are typically on the second night, which skews toward certain days
print('\n  B2B second night typically falls on:')
btb_days = defaultdict(int)
for r in edge_games:
    d = dow(r)
    if d: btb_days[d] += 1
for d in day_order:
    if d in btb_days:
        print('    %s: %d games' % (d, btb_days[d]))

# === D. REST ADVANTAGE OF THE EDGE TEAM ===
print('\n' + '='*70)
print('  D. EDGE TEAM REST DAYS — DOES MORE REST = BETTER SIGNAL?')
print('='*70)
print('\n  AWAY EDGE: Away team (edge team) days rest:')
for rest_val in [1, 2, 3]:
    label = '%d day(s) rest' % rest_val
    g2 = [r for r in away_edge if a_rest(r) == rest_val]
    if g2:
        w,l = wl(g2)
        print('    Away %s: %s' % (label, fmt(w,l)))

rest3plus = [r for r in away_edge if a_rest(r) is not None and a_rest(r) >= 3]
if rest3plus:
    w,l = wl(rest3plus)
    print('    Away 3+ days rest: %s' % fmt(w,l))

# === E. ALTITUDE GAMES ===
print('\n' + '='*70)
print('  E. ALTITUDE GAMES (DEN/UTA AS HOME)')
print('='*70)
for team in ['DEN', 'UTA']:
    print('\n  %s as fatigued home (AWAY EDGE):' % team)
    g2 = [r for r in away_edge if g(r,'home') == team]
    if g2:
        w,l = wl(g2)
        print('    ATS: %s' % fmt(w,l))

    # Also check when visiting these teams
    print('  Visiting %s (opponent fatigue + altitude):' % team)
    g2 = [r for r in edge_games if g(r,'home') == team]
    if g2:
        w,l = wl(g2)
        print('    Edge ATS: %s' % fmt(w,l))

# === F. SPECIFIC TEAM PERFORMANCE WHEN FATIGUED ===
print('\n' + '='*70)
print('  F. WHICH TEAMS COVER WORST WHEN FATIGUED? (flagged team)')
print('='*70)
team_perf = defaultdict(lambda: [0, 0])
for r in edge_games:
    ft = g(r,'flagged_team')
    if not ft: continue
    if ats(r) == 'WIN':
        team_perf[ft][0] += 1  # edge team (opponent) won
    elif ats(r) == 'LOSS':
        team_perf[ft][1] += 1  # fatigued team covered

print('\n  Teams that FAIL to cover when fatigued (opponent edge wins):')
sorted_teams = sorted(team_perf.items(), key=lambda x: x[1][0]/(x[1][0]+x[1][1]) if (x[1][0]+x[1][1]) >= 5 else 0, reverse=True)
for team, (w, l) in sorted_teams:
    n = w + l
    if n >= 5:
        pct = round(w/n*100, 1)
        print('    %s fatigued: opponent covers %dW %dL (%.1f%%)  n=%d' % (team, w, l, pct, n))

# === G. NON-BTB FATIGUE (DENSITY ONLY) ===
print('\n' + '='*70)
print('  G. NON-BTB FATIGUE (3-in-4, 4-in-6 density)')
print('='*70)
# Games where the fatigued team is NOT on a B2B
non_btb_away = [r for r in away_edge if a_scen(r) == 'rest' or h_scen_raw(r) not in ('A','B','C','home-home','')]
non_btb_home = [r for r in home_edge if a_scen(r) == 'rest' or h_scen_raw(r) == 'rest']

# Check by home scenario for AWAY EDGE (home is the fatigued team)
print('\n  AWAY EDGE by home team scenario:')
for scen in ['C', 'home-home', 'rest']:
    g2 = [r for r in away_edge if h_scen_raw(r) == scen or h_scen(r) == scen]
    if g2:
        w,l = wl(g2)
        print('    Home scenario=%s: %s' % (scen, fmt(w,l)))

# === H. COMBINED SCORE PATTERNS (BLOWOUTS VS CLOSE GAMES) ===
print('\n' + '='*70)
print('  H. MARGIN OF VICTORY — DO FATIGUED TEAMS GET BLOWN OUT?')
print('='*70)
# For AWAY EDGE games (home is tired), what's the avg margin?
margins = []
for r in away_edge:
    h, a = home_pts(r), away_pts(r)
    if h is not None and a is not None:
        margins.append(a - h)  # positive = away team won

if margins:
    avg_margin = sum(margins) / len(margins)
    wins_outright = sum(1 for m in margins if m > 0)
    print('  AWAY EDGE games (home is tired):')
    print('    Avg margin (away - home): %+.1f pts' % avg_margin)
    print('    Away wins outright: %d/%d (%.1f%%)' % (wins_outright, len(margins), wins_outright/len(margins)*100))

    # Margin vs ATS result
    ats_wins = [r for r in away_edge if ats(r) == 'WIN' and home_pts(r) is not None]
    ats_losses = [r for r in away_edge if ats(r) == 'LOSS' and home_pts(r) is not None]
    if ats_wins:
        avg_w = sum(away_pts(r) - home_pts(r) for r in ats_wins) / len(ats_wins)
        print('    Avg margin when covering ATS: %+.1f' % avg_w)
    if ats_losses:
        avg_l = sum(away_pts(r) - home_pts(r) for r in ats_losses) / len(ats_losses)
        print('    Avg margin when NOT covering: %+.1f' % avg_l)

# === I. THE "REVENGE" ANGLE — SECOND GAME OF SAME MATCHUP ===
print('\n' + '='*70)
print('  I. TRAVEL DISTANCE IN DETAIL (from away_detail)')
print('='*70)
# Parse distance from detail strings
import re
print('\n  AWAY EDGE by travel distance of fatigued home team:')
for label, lo, hi in [('0-200mi (local)', 0, 200), ('200-500mi', 200, 500), ('500-1000mi', 500, 1000), ('1000-2000mi', 1000, 2000), ('2000+mi', 2000, 9999)]:
    g2 = []
    for r in away_edge:
        d = h_det(r)
        m = re.search(r'(\d+)mi', d)
        if m:
            dist = int(m.group(1))
            if lo <= dist < hi:
                g2.append(r)
    if g2:
        w,l = wl(g2)
        print('    %s: %s' % (label, fmt(w,l)))

# === J. HOME EDGE — ANY STABLE SUBSET? ===
print('\n' + '='*70)
print('  J. HOME EDGE — SEARCHING FOR STABLE SUBSETS')
print('='*70)
# HOME EDGE overall is unstable (57% in 24-25, 38% in 25-26)
# But are there specific subsets that work in BOTH seasons?
tests = [
    ('Home fav + delta >= 6', lambda r: spread(r) is not None and spread(r) < 0 and delta(r) >= 6),
    ('Home fav -1 to -6.5', lambda r: spread(r) is not None and -6.5 <= spread(r) <= -1),
    ('Home fav + away=A', lambda r: spread(r) is not None and spread(r) < 0 and a_scen(r) == 'A'),
    ('Home dog (home underdog)', lambda r: spread(r) is not None and spread(r) > 0),
    ('Away=A scenario only', lambda r: a_scen(r) == 'A'),
    ('Away=B scenario only', lambda r: a_scen(r) == 'B'),
]
for label, filt in tests:
    print('\n  %s:' % label)
    for season, data in [('24-25', s1), ('25-26', s2)]:
        g2 = [r for r in data if 'HOME' in edge(r) and ats(r) in ('WIN','LOSS') and filt(r)]
        if g2:
            w,l = wl(g2)
            pct = round(w/(w+l)*100.0,1) if (w+l) else 0
            status = 'PROFIT' if pct > 52.4 else 'LOSS'
            print('    %s: %s [%s]' % (season, fmt(w,l), status))

# === K. GAME TOTAL ACTUAL VS LINE — SYSTEMATIC BIAS? ===
print('\n' + '='*70)
print('  K. ARE TOTALS SYSTEMATICALLY BIASED IN FATIGUE GAMES?')
print('='*70)
diffs = []
for r in edge_games:
    t = total(r)
    gt = game_total(r)
    if t is not None and gt is not None:
        diffs.append(gt - t)

if diffs:
    avg_diff = sum(diffs) / len(diffs)
    under_pct = sum(1 for d in diffs if d < 0) / len(diffs) * 100
    print('  All flagged games:')
    print('    Avg (actual - line): %+.1f pts' % avg_diff)
    print('    Under rate: %.1f%% (%d/%d)' % (under_pct, sum(1 for d in diffs if d < 0), len(diffs)))

    # By edge direction
    for label, filt in [('AWAY EDGE', lambda r: 'AWAY' in edge(r)), ('HOME EDGE', lambda r: 'HOME' in edge(r))]:
        d2 = []
        for r in edge_games:
            if filt(r) and total(r) is not None and game_total(r) is not None:
                d2.append(game_total(r) - total(r))
        if d2:
            avg = sum(d2) / len(d2)
            un = sum(1 for d in d2 if d < 0) / len(d2) * 100
            print('    %s: avg %+.1f pts, %.1f%% under (n=%d)' % (label, avg, un, len(d2)))

    # Both tired
    bt_diffs = []
    for r in all_games:
        if fat_a(r) >= 5 and fat_h(r) >= 5 and total(r) is not None and game_total(r) is not None:
            bt_diffs.append(game_total(r) - total(r))
    if bt_diffs:
        avg = sum(bt_diffs) / len(bt_diffs)
        un = sum(1 for d in bt_diffs if d < 0) / len(bt_diffs) * 100
        print('    Both-tired: avg %+.1f pts, %.1f%% under (n=%d)' % (avg, un, len(bt_diffs)))
