#!/usr/bin/env python3
"""Deep cross-season analysis of NBA Edge Model backtest results."""

import csv

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
def under_val(r): return g(r,'under_result').upper()
def wpct(r):
    v = g(r,'edge_team_wpct')
    return float(v) if v else None
def total(r):
    v = g(r,'close_total')
    return float(v) if v else None
def a_scen(r): return g(r,'away_scenario')
def h_det(r): return g(r,'home_detail')
def a_sleep(r):
    v = g(r,'away_sleep','away_est_sleep')
    return float(v) if v else None
def h_sleep(r):
    v = g(r,'home_sleep','home_est_sleep')
    return float(v) if v else None

def wl(games, field='edge_ats'):
    w = sum(1 for x in games if x.get(field,'').upper() == 'WIN')
    l = sum(1 for x in games if x.get(field,'').upper() == 'LOSS')
    return w, l

def roi(w, l):
    if w+l == 0: return 0
    profit = w * (100.0/110.0) - l * 1.0
    return round(profit / (w+l) * 100, 1)

def fmt(w, l):
    n = w+l
    pct = round(w/n*100.0, 1) if n else 0
    r = roi(w, l)
    flag = '' if n >= 30 else '  *n=%d' % n
    return '%dW %dL  %.1f%%  ROI:%+.1f%%  (n=%d)%s' % (w, l, pct, r, n, flag)

def h_scen(r):
    d = h_det(r)
    if 'BTB home' in d and 'flew' in d: return 'C'
    if 'home-home' in d.lower(): return 'HH'
    return 'other'

# =====================================================================
print('='*70)
print('  6. BOTH-TIRED UNDER DEEP DIVE (COMBINED)')
print('='*70)

both = [r for r in all_games if under_val(r) in ('WIN','LOSS')]
w,l = wl(both, 'under_result')
print('\n  Baseline: %s' % fmt(w,l))

print('\n  By combined fatigue:')
for t in [10, 12, 14, 16]:
    g2 = [r for r in both if fat_a(r) + fat_h(r) >= t]
    if g2:
        w,l = wl(g2, 'under_result')
        print('    Combined >= %d: %s' % (t, fmt(w,l)))

print('\n  By closing total:')
for lo, hi, label in [(200,220,'< 220'), (220,228,'220-228'), (228,234,'228-234'), (234,250,'234+')]:
    g2 = [r for r in both if total(r) is not None and lo <= total(r) < hi]
    if g2:
        w,l = wl(g2, 'under_result')
        print('    Total %s: %s' % (label, fmt(w,l)))

print('\n  By scenario combo:')
combos = {}
for r in both:
    k = (a_scen(r), h_scen(r))
    if k not in combos: combos[k] = []
    combos[k].append(r)
for k in sorted(combos, key=lambda x: -len(combos[x])):
    g2 = combos[k]
    w,l = wl(g2, 'under_result')
    print('    Away=%s / Home=%s: %s' % (k[0], k[1], fmt(w,l)))

print('\n  By season:')
for season, data in [('24-25', s1), ('25-26', s2)]:
    bt = [r for r in data if under_val(r) in ('WIN','LOSS')]
    w,l = wl(bt, 'under_result')
    print('    %s: %s' % (season, fmt(w,l)))

# =====================================================================
print()
print('='*70)
print('  7. HOME EDGE FLIP INVESTIGATION')
print('='*70)

for season, data in [('24-25', s1), ('25-26', s2)]:
    he = [r for r in data if 'HOME' in edge(r) and ats(r) in ('WIN','LOSS') and spread(r) is not None]
    print('\n  --- %s --- (flipped = bet away in HOME EDGE games)' % season)
    for lo, hi, label in [(-99,-7,'Big fav -7+'), (-6.5,-3,'Mid fav -3 to -6.5'), (-2.5,0.5,'Small fav/pick'), (1,99,'Home is dog')]:
        g2 = [r for r in he if lo <= spread(r) <= hi]
        if g2:
            wf = sum(1 for r in g2 if ats(r) == 'LOSS')
            lf = sum(1 for r in g2 if ats(r) == 'WIN')
            print('    %s: %s' % (label, fmt(wf, lf)))

# =====================================================================
print()
print('='*70)
print('  8. CROSS-SEASON CONSISTENCY (>52.4%% = profitable at -110)')
print('='*70)

rules = [
    ('AWAY EDGE overall', lambda r: 'AWAY' in edge(r) and ats(r) in ('WIN','LOSS'), 'edge_ats'),
    ('AWAY EDGE + home fav', lambda r: 'AWAY' in edge(r) and ats(r) in ('WIN','LOSS') and spread(r) is not None and spread(r) < 0, 'edge_ats'),
    ('AWAY EDGE + home fav + delta>=4', lambda r: 'AWAY' in edge(r) and ats(r) in ('WIN','LOSS') and spread(r) is not None and spread(r) < 0 and delta(r) >= 4, 'edge_ats'),
    ('AWAY EDGE + home fav + delta>=5', lambda r: 'AWAY' in edge(r) and ats(r) in ('WIN','LOSS') and spread(r) is not None and spread(r) < 0 and delta(r) >= 5, 'edge_ats'),
    ('AWAY EDGE + fav -1 to -9.5', lambda r: 'AWAY' in edge(r) and ats(r) in ('WIN','LOSS') and spread(r) is not None and -9.5 <= spread(r) <= -1, 'edge_ats'),
    ('Both-tired UNDER', lambda r: under_val(r) in ('WIN','LOSS'), 'under_result'),
    ('Under + Away=A', lambda r: under_val(r) in ('WIN','LOSS') and a_scen(r) == 'A', 'under_result'),
]

for label, filt, field in rules:
    for season, data in [('24-25', s1), ('25-26', s2), ('COMBINED', all_games)]:
        g2 = [r for r in data if filt(r)]
        if g2:
            w,l = wl(g2, field)
            pct = round(w/(w+l)*100.0,1) if (w+l) else 0
            status = 'PROFIT' if pct > 52.4 else 'LOSS'
            tag = ' <<<' if season == 'COMBINED' else ''
            print('  %s (%s): %dW %dL %.1f%% [%s]%s' % (label, season, w, l, pct, status, tag))
    print()

# =====================================================================
print('='*70)
print('  9. BEST COMPOSITE RULES')
print('='*70)

combos = [
    ('SIGNAL A: AWAY EDGE + fav + delta>=4',
     lambda r: 'AWAY' in edge(r) and ats(r) in ('WIN','LOSS') and spread(r) is not None and spread(r) < 0 and delta(r) >= 4, 'edge_ats'),
    ('SIGNAL A + exclude big fav (-10+)',
     lambda r: 'AWAY' in edge(r) and ats(r) in ('WIN','LOSS') and spread(r) is not None and -9.5 <= spread(r) < 0 and delta(r) >= 4, 'edge_ats'),
    ('SIGNAL A + exclude big fav + wpct>=.400',
     lambda r: 'AWAY' in edge(r) and ats(r) in ('WIN','LOSS') and spread(r) is not None and -9.5 <= spread(r) < 0 and delta(r) >= 4 and wpct(r) is not None and wpct(r) >= .400, 'edge_ats'),
    ('SIGNAL A + fav -1 to -9.5 + delta>=5',
     lambda r: 'AWAY' in edge(r) and ats(r) in ('WIN','LOSS') and spread(r) is not None and -9.5 <= spread(r) <= -1 and delta(r) >= 5, 'edge_ats'),
    ('UNDER: baseline both-tired',
     lambda r: under_val(r) in ('WIN','LOSS'), 'under_result'),
    ('UNDER: Away=A + Home=HH',
     lambda r: under_val(r) in ('WIN','LOSS') and a_scen(r) == 'A' and h_scen(r) == 'HH', 'under_result'),
    ('UNDER: Away=A + total < 234',
     lambda r: under_val(r) in ('WIN','LOSS') and a_scen(r) == 'A' and total(r) is not None and total(r) < 234, 'under_result'),
    ('UNDER: delta >= 4',
     lambda r: under_val(r) in ('WIN','LOSS') and delta(r) >= 4, 'under_result'),
    ('UNDER: Away=A + delta >= 2',
     lambda r: under_val(r) in ('WIN','LOSS') and a_scen(r) == 'A' and delta(r) >= 2, 'under_result'),
]

for label, filt, field in combos:
    print()
    for season, data in [('24-25', s1), ('25-26', s2), ('COMBINED', all_games)]:
        g2 = [r for r in data if filt(r)]
        if g2:
            w,l = wl(g2, field)
            pct = round(w/(w+l)*100.0,1) if (w+l) else 0
            r = roi(w,l)
            tag = ' <<<' if season == 'COMBINED' else ''
            n = w+l
            print('  %s (%s): %dW %dL %.1f%% ROI:%+.1f%% (n=%d)%s' % (label, season, w, l, pct, r, n, tag))

# =====================================================================
print()
print('='*70)
print('  10. FINAL SIGNAL CARD')
print('='*70)

print("""
  SPREAD SIGNAL: Bet AWAY when...
    - Edge side = AWAY EDGE (home team is fatigued)
    - Home team is favored (spread < 0)
    - Fatigue delta >= 4
    - Exclude home favorites of -10 or more
    - (Optional) Edge team win%% >= .400 for extra filtering
""")

# Calculate final signal
for label, filt, field in [
    ('SPREAD SIGNAL (no wpct filter)',
     lambda r: 'AWAY' in edge(r) and ats(r) in ('WIN','LOSS') and spread(r) is not None and -9.5 <= spread(r) < 0 and delta(r) >= 4, 'edge_ats'),
    ('SPREAD SIGNAL (with wpct >= .400)',
     lambda r: 'AWAY' in edge(r) and ats(r) in ('WIN','LOSS') and spread(r) is not None and -9.5 <= spread(r) < 0 and delta(r) >= 4 and (wpct(r) is None or wpct(r) >= .400), 'edge_ats'),
]:
    print('  %s:' % label)
    for season, data in [('24-25', s1), ('25-26', s2), ('COMBINED', all_games)]:
        g2 = [r for r in data if filt(r)]
        if g2:
            w,l = wl(g2, field)
            pct = round(w/(w+l)*100.0,1) if (w+l) else 0
            r = roi(w,l)
            tag = ' <<<' if season == 'COMBINED' else ''
            print('    %s: %dW %dL %.1f%% ROI:%+.1f%% (n=%d)%s' % (season, w, l, pct, r, w+l, tag))
    print()

print("""
  UNDER SIGNAL: Bet UNDER when...
    - Both teams fatigued (both >= 5.0)
    - Away team scenario = A (road-to-road BTB)
    - Closing total < 234
""")

filt = lambda r: under_val(r) in ('WIN','LOSS') and a_scen(r) == 'A' and total(r) is not None and total(r) < 234
print('  UNDER SIGNAL:')
for season, data in [('24-25', s1), ('25-26', s2), ('COMBINED', all_games)]:
    g2 = [r for r in data if filt(r)]
    if g2:
        w,l = wl(g2, 'under_result')
        pct = round(w/(w+l)*100.0,1) if (w+l) else 0
        r = roi(w,l)
        tag = ' <<<' if season == 'COMBINED' else ''
        print('    %s: %dW %dL %.1f%% ROI:%+.1f%% (n=%d)%s' % (season, w, l, pct, r, w+l, tag))
