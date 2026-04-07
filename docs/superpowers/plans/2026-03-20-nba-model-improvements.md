# NBA Edge Model Improvements — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix critical analysis bug, improve fatigue model accuracy (real tip times, DST), add team-quality filter to eliminate tanking-team noise, and re-validate via backtest.

**Architecture:** Four-phase pipeline improvement. Phase 1 fixes bugs and consolidates duplicate scripts. Phase 2 improves fatigue model inputs (tip times, DST). Phase 3 adds a team-quality post-filter. Phase 4 re-runs backtests to validate. Each phase is independently committable and testable.

**Tech Stack:** Node.js (backtest engine), Python 3 (grading/analysis), BallDontLie API (game data), The Odds API (closing lines)

**Spec:** `docs/superpowers/specs/2026-03-20-nba-model-improvements-design.md`

**Backup:** `v1.0-baseline` tag on commit `09e4e07`. Revert: `git checkout v1.0-baseline`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `nba_backtest.js` | Rewrite | Consolidated backtest engine: CLI args, env var key, real tip times, DST, team quality |
| `nba_backtest_24_25.js` | Delete | Consolidated into `nba_backtest.js` |
| `grade_backtest.py` | Rewrite | Consolidated grader: CLI args, CSV+XLSX input |
| `grade_backtest_24_25.py` | Delete | Consolidated into `grade_backtest.py` |
| `analyze_backtest.py` | Modify | Fix fatigue accessor bug, add team-quality analysis section |
| `.gitignore` | Create | Exclude data files, logs, editor artifacts |
| `requirements.txt` | Create | Python dependencies |
| `package.json` | Create | Node.js project metadata |

---

## Phase 1: Bug Fixes & Code Cleanup

### Task 1: Project Hygiene Files

**Files:**
- Create: `.gitignore`
- Create: `requirements.txt`
- Create: `package.json`

- [ ] **Step 1: Create `.gitignore`**

```gitignore
# Data files
*.xlsx
*.csv
output_log.txt
regression_*

# Editor/IDE
.claude/
.vscode/
node_modules/

# OS
Thumbs.db
Desktop.ini
```

- [ ] **Step 2: Create `requirements.txt`**

```
openpyxl>=3.1.0
requests>=2.31.0
```

- [ ] **Step 3: Create `package.json`**

```json
{
  "name": "nba-edge-model",
  "version": "2.0.0",
  "description": "NBA fatigue-based betting edge model — backtest and analysis tools",
  "scripts": {
    "backtest": "node nba_backtest.js",
    "backtest:24-25": "node nba_backtest.js --start 2024-11-01 --end 2025-04-13",
    "backtest:25-26": "node nba_backtest.js --start 2025-11-01 --end 2026-04-13"
  },
  "engines": {
    "node": ">=18.0.0"
  }
}
```

- [ ] **Step 4: Commit**

```bash
git add .gitignore requirements.txt package.json
git commit -m "Add project hygiene: .gitignore, requirements.txt, package.json"
```

---

### Task 2: Fix Analysis Bug (Column Naming + Accessor)

**Files:**
- Modify: `analyze_backtest.py:43-44` (swap `_get` key order)
- Modify: `nba_backtest_24_25.js:314` (rename CSV headers — this is the canonical version that Task 5 will use as the base)

Note: `nba_backtest.js` is NOT edited here — Task 5 will replace it entirely using `nba_backtest_24_25.js` as the base, inheriting this rename.

- [ ] **Step 1: Fix fatigue accessors in `analyze_backtest.py`**

Change lines 43-44 from:
```python
def away_fat(r):  return float(_get(r, 'away_score', 'away_fatigue') or 0)
def home_fat(r):  return float(_get(r, 'home_score', 'home_fatigue') or 0)
```
To:
```python
def away_fat(r):  return float(_get(r, 'away_fatigue', 'away_score') or 0)
def home_fat(r):  return float(_get(r, 'home_fatigue', 'home_score') or 0)
```

- [ ] **Step 2: Rename CSV headers in `nba_backtest_24_25.js`**

Change line 314 from:
```javascript
const header = ['Date','Matchup','Away','Home','Away Score','Home Score','Max Score','Flagged Team','Edge Side','Away Scenario','Home Scenario','Away Days Rest','Home Days Rest','Away Est Sleep','Home Est Sleep','Away Detail','Home Detail','Covers URL'];
```
To:
```javascript
const header = ['Date','Matchup','Away','Home','Away Fatigue','Home Fatigue','Max Fatigue','Flagged Team','Edge Side','Away Scenario','Home Scenario','Away Days Rest','Home Days Rest','Away Est Sleep','Home Est Sleep','Away Detail','Home Detail','Covers URL'];
```

- [ ] **Step 3: Verify fix by running analysis on existing graded CSV**

Run: `python analyze_backtest.py graded_backtest_24_25.csv`

Expected: The "BY MAX FATIGUE SCORE" section should now show **different** counts for thresholds >= 5 through >= 9 (previously all showed identical 33W 17L because game scores always exceed 9). If max_score >= 8 or >= 9 shows fewer games than >= 5, the fix is working.

- [ ] **Step 4: Commit**

```bash
git add analyze_backtest.py nba_backtest_24_25.js
git commit -m "Fix critical analysis bug: fatigue accessors were using game scores instead of fatigue scores"
```

---

### Task 3: Generate Regression Baseline

Before consolidating scripts, capture current output for comparison.

**Files:**
- None modified (read-only verification step)

- [ ] **Step 1: Save first 20 rows of existing backtest output as reference**

```bash
head -21 NBA_Backtest_24_25.csv > regression_reference.csv
```

This captures expected fatigue score values for the first 20 games. After consolidation, we'll compare fatigue values (columns 5-6) from the new output against this reference. Note: headers will differ (renamed from "Away Score" to "Away Fatigue" in Task 2) — compare values only.

---

### Task 4: Consolidate Backtest Scripts

**Files:**
- Rewrite: `nba_backtest.js` (merge both versions, add CLI args)
- Delete: `nba_backtest_24_25.js`

- [ ] **Step 1: Add CLI argument parsing to `nba_backtest.js`**

Replace the hardcoded season constants (lines 11-14 of the 24-25 version) with:

```javascript
// ── CLI ARGS ──────────────────────────────────────────────────
function parseArgs() {
  const args = process.argv.slice(2);
  const opts = { start: '2025-11-01', end: '2026-04-13' };  // current season defaults
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--start' && args[i+1]) opts.start = args[++i];
    if (args[i] === '--end' && args[i+1]) opts.end = args[++i];
  }
  return opts;
}

const { start: SEASON_START, end: SEASON_END } = parseArgs();
const FLAG_THRESHOLD = 5;
```

- [ ] **Step 2: Use `nba_backtest_24_25.js` as the base (it has env var key, better error handling)**

Copy all logic from `nba_backtest_24_25.js` into `nba_backtest.js`, replacing the old content entirely. Then apply the CLI args change from Step 1 and the header rename from Task 2.

- [ ] **Step 3: Verify consolidated script produces matching output**

```powershell
$env:BDL_API_KEY="your_key"
node nba_backtest.js --start 2024-11-01 --end 2024-11-07 > regression_test.csv 2>nul
```

Compare fatigue values (columns 5-6) against `regression_reference.csv`. Headers will differ (renamed to "Away Fatigue" etc.) — compare data values only:

```bash
tail -n+2 regression_reference.csv | cut -d, -f5,6 | head -5 > ref_vals.txt
tail -n+2 regression_test.csv | cut -d, -f5,6 | head -5 > test_vals.txt
diff ref_vals.txt test_vals.txt
```

Expected: No differences in fatigue score values. Clean up temp files after.

- [ ] **Step 4: Delete `nba_backtest_24_25.js`**

```bash
git rm nba_backtest_24_25.js
```

- [ ] **Step 5: Commit**

```bash
git add nba_backtest.js
git commit -m "Consolidate backtest scripts into single parameterized nba_backtest.js"
```

---

### Task 5: Consolidate Grading Scripts

**Files:**
- Rewrite: `grade_backtest.py` (merge both, add CLI args, CSV support)
- Delete: `grade_backtest_24_25.py`

- [ ] **Step 1: Add CLI argument parsing and CSV input support**

Replace the hardcoded paths (lines 23-25 of `grade_backtest_24_25.py`) with:

```python
import argparse

def parse_args():
    p = argparse.ArgumentParser(description="NBA Edge Backtest Grader")
    p.add_argument("--input", required=True, help="Input file (.xlsx or .csv)")
    p.add_argument("--output", required=True, help="Output CSV file path")
    return p.parse_args()
```

- [ ] **Step 2: Add CSV loading alongside XLSX**

Add a `load_games_csv()` function that reads CSV input with the same column mapping as XLSX. Detect format by file extension:

```python
def load_games(path):
    if path.endswith('.xlsx'):
        return load_games_xlsx(path)
    elif path.endswith('.csv'):
        return load_games_csv(path)
    else:
        raise ValueError(f"Unsupported file format: {path}")

def load_games_csv(path):
    games = []
    with open(path, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            # Normalize keys: lowercase, strip, underscores
            r = {k.lower().strip().replace(' ', '_'): v for k, v in row.items()}
            away_fat = float(r.get('away_fatigue', 0) or 0)
            home_fat = float(r.get('home_fatigue', 0) or 0)
            games.append({
                "date": datetime.strptime(r['date'][:10], "%Y-%m-%d").date(),
                "matchup": r.get('matchup', ''),
                "away": r.get('away', ''),
                "home": r.get('home', ''),
                "away_fatigue": away_fat,
                "home_fatigue": home_fat,
                "max_fatigue": float(r.get('max_fatigue', 0) or 0),
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
                "both_tired": away_fat >= 5.0 and home_fat >= 5.0,
            })
    return games
```

Rename existing `load_games()` to `load_games_xlsx()`.

- [ ] **Step 3: Update `main()` to use CLI args**

```python
def main():
    args = parse_args()
    # ... rest of main uses args.input and args.output instead of hardcoded paths
```

- [ ] **Step 4: Verify consolidated grader output format**

Compare output column headers against existing graded CSV:

```bash
head -1 graded_backtest_24_25.csv
```

After running the consolidated grader on a test input, verify headers match exactly (29 columns in same order). This catches column mapping regressions.

- [ ] **Step 5: Delete `grade_backtest_24_25.py`**

```bash
git rm grade_backtest_24_25.py
```

- [ ] **Step 6: Commit**

```bash
git add grade_backtest.py
git commit -m "Consolidate grading scripts into single parameterized grade_backtest.py"
```

---

## Phase 2: Fatigue Model Improvements

### Task 6: DST-Aware Timezones, Real Tip Times & Late-Tip Penalty

This task combines DST handling, real tip times, and late-tip penalty activation into a single task because they modify the same function signatures and cannot be independently tested. Changing `estimateBTBSleep`'s parameter list for DST would break callers until tip-time threading is also done.

**Files:**
- Modify: `nba_backtest.js` (ARENAS dictionary, helper functions, `parseTipET`, `estimateBTBSleep`, `calcRest`, `analyzeFatigue`)

- [ ] **Step 1: Replace static `tz` offsets with IANA identifiers in ARENAS**

```javascript
const ARENAS = {
  ATL:{lat:33.7573,lon:-84.3963,tz:'America/New_York'},
  BOS:{lat:42.3662,lon:-71.0621,tz:'America/New_York'},
  BKN:{lat:40.6826,lon:-73.9754,tz:'America/New_York'},
  CHA:{lat:35.2251,lon:-80.8392,tz:'America/New_York'},
  CHI:{lat:41.8807,lon:-87.6742,tz:'America/Chicago'},
  CLE:{lat:41.4965,lon:-81.6882,tz:'America/New_York'},
  DAL:{lat:32.7905,lon:-96.8103,tz:'America/Chicago'},
  DEN:{lat:39.7487,lon:-105.0077,tz:'America/Denver'},
  DET:{lat:42.3410,lon:-83.0552,tz:'America/Detroit'},
  GSW:{lat:37.7680,lon:-122.3877,tz:'America/Los_Angeles'},
  HOU:{lat:29.7508,lon:-95.3621,tz:'America/Chicago'},
  IND:{lat:39.7640,lon:-86.1555,tz:'America/Indiana/Indianapolis'},
  LAC:{lat:33.8958,lon:-118.3386,tz:'America/Los_Angeles'},
  LAL:{lat:34.0430,lon:-118.2673,tz:'America/Los_Angeles'},
  MEM:{lat:35.1383,lon:-90.0505,tz:'America/Chicago'},
  MIA:{lat:25.7814,lon:-80.1870,tz:'America/New_York'},
  MIL:{lat:43.0450,lon:-87.9170,tz:'America/Chicago'},
  MIN:{lat:44.9795,lon:-93.2762,tz:'America/Chicago'},
  NOP:{lat:29.9490,lon:-90.0812,tz:'America/Chicago'},
  NYK:{lat:40.7505,lon:-73.9934,tz:'America/New_York'},
  OKC:{lat:35.4634,lon:-97.5151,tz:'America/Chicago'},
  ORL:{lat:28.5392,lon:-81.3839,tz:'America/New_York'},
  PHI:{lat:39.9012,lon:-75.1720,tz:'America/New_York'},
  PHX:{lat:33.4457,lon:-112.0712,tz:'America/Phoenix'},
  POR:{lat:45.5316,lon:-122.6668,tz:'America/Los_Angeles'},
  SAC:{lat:38.5802,lon:-121.4997,tz:'America/Los_Angeles'},
  SAS:{lat:29.4270,lon:-98.4375,tz:'America/Chicago'},
  TOR:{lat:43.6435,lon:-79.3791,tz:'America/Toronto'},
  UTA:{lat:40.7683,lon:-111.9011,tz:'America/Denver'},
  WAS:{lat:38.8981,lon:-77.0209,tz:'America/New_York'},
};
```

- [ ] **Step 2: Add DST-aware UTC offset helper**

```javascript
function getUtcOffset(tzName, date) {
  // Returns UTC offset in hours (e.g., -5 for EST, -4 for EDT)
  const formatter = new Intl.DateTimeFormat('en-US', {
    timeZone: tzName,
    timeZoneName: 'shortOffset',
  });
  const parts = formatter.formatToParts(date);
  const tzPart = parts.find(p => p.type === 'timeZoneName');
  // tzPart.value is like "GMT-5" or "GMT-4"
  const match = tzPart.value.match(/GMT([+-]?\d+)/);
  return match ? parseInt(match[1]) : -5;  // fallback to ET
}
```

- [ ] **Step 3: Update `parseTipET` to be DST-aware**

Replace the hardcoded `-5` with a date-aware calculation:

```javascript
function parseTipET(datetimeStr) {
  if(!datetimeStr) return 19.5;
  const d = new Date(datetimeStr);
  const etOffset = getUtcOffset('America/New_York', d);
  const etHour = (d.getUTCHours() + etOffset + 24) % 24;
  return etHour + d.getUTCMinutes() / 60;
}
```

- [ ] **Step 4: Update all functions that use `ARENAS[x].tz` to call `getUtcOffset`**

In `estimateBTBSleep`, replace:
```javascript
const fromTZ = ARENAS[fromArena]?.tz ?? -6;
const toTZ   = ARENAS[toArena]?.tz   ?? -6;
```
With:
```javascript
const gameDate = new Date(/* pass game date through */);
const fromTZ = getUtcOffset(ARENAS[fromArena]?.tz ?? 'America/Chicago', gameDate);
const toTZ   = getUtcOffset(ARENAS[toArena]?.tz   ?? 'America/Chicago', gameDate);
```

This requires threading the game date into `estimateBTBSleep`. Add `gameDate` as a fourth parameter.

- [ ] **Step 5: Return previous-game datetime from `calcRest`**

In `calcRest`, the `last` variable already contains the previous game object with a `datetime` field. Add it to the return:

```javascript
return {
  daysRest,
  prevLocation: prevArena,
  lastGame: last,
  wasHomeLastGame: wasHome,
  gamesIn4: gamesIn3+1,
  gamesIn6: gamesIn5+1,
  recentAltitudeVisit,
  prevTipDatetime: last.datetime || null,  // NEW
};
```

- [ ] **Step 6: Update `estimateBTBSleep` to use real tip time**

Add `prevTipDatetime` and `gameDate` as parameters. Replace the hardcoded `prevTipLocal = 20.0`:

```javascript
function estimateBTBSleep(fromArena, toArena, tonightTipET, prevTipDatetime, gameDate) {
  const dist = getDist(fromArena, toArena);
  const flightHrs = dist / 500;
  const fromTZ = getUtcOffset(ARENAS[fromArena]?.tz ?? 'America/Chicago', gameDate);
  const toTZ   = getUtcOffset(ARENAS[toArena]?.tz   ?? 'America/Chicago', gameDate);

  // Use actual previous-game tip time if available, otherwise default to 8pm local
  let prevTipLocal = 20.0;
  if (prevTipDatetime) {
    const prevDate = new Date(prevTipDatetime);
    const prevLocalOffset = getUtcOffset(ARENAS[fromArena]?.tz ?? 'America/Chicago', prevDate);
    prevTipLocal = (prevDate.getUTCHours() + prevLocalOffset + 24) % 24 + prevDate.getUTCMinutes() / 60;
  }

  // ... rest of function unchanged, but uses dynamic fromTZ/toTZ instead of hardcoded
```

- [ ] **Step 7: Update `analyzeFatigue` to pass real tip time to `computeFatigueScore`**

The current code passes `prevTipLocalHr: 19.5` hardcoded. Change it to compute from the actual previous-game datetime:

```javascript
// In the BTB branch of analyzeFatigue, where prevArena is known:
let prevTipLocalHr = 19.5;  // default
if (prevTipDatetime) {
  const prevDate = new Date(prevTipDatetime);
  const prevLocalOffset = getUtcOffset(ARENAS[prevArena]?.tz ?? 'America/Chicago', prevDate);
  prevTipLocalHr = (prevDate.getUTCHours() + prevLocalOffset + 24) % 24 + prevDate.getUTCMinutes() / 60;
}
```

Pass `prevTipLocalHr` to `computeFatigueScore` instead of the hardcoded `19.5`. This code must appear in ALL BTB branches of `analyzeFatigue` (Scenarios A, B, C, and home-home).

- [ ] **Step 8: Thread new parameters through call sites in `main()`**

Update the calls in the main game loop (lines 274-278):

```javascript
const awayRest = calcRest(history, game.visitor_team.id, date);
const homeRest = calcRest(history, game.home_team.id, date);
const gameDate = new Date(game.datetime || date + 'T19:00:00Z');

const awayF = analyzeFatigue(away, false, awayRest.daysRest, awayRest.prevLocation, home, tipET, awayRest.wasHomeLastGame, awayRest.gamesIn4, awayRest.gamesIn6, awayRest.recentAltitudeVisit, awayRest.prevTipDatetime, gameDate);
const homeF = analyzeFatigue(home, true, homeRest.daysRest, homeRest.prevLocation, home, tipET, homeRest.wasHomeLastGame, homeRest.gamesIn4, homeRest.gamesIn6, homeRest.recentAltitudeVisit, homeRest.prevTipDatetime, gameDate);
```

- [ ] **Step 9: Verify late-tip penalty now fires**

Look for games with previous tips after 9:30pm local in the output. The `Away Detail` / `Home Detail` columns should reflect the late-tip penalty in their score breakdown for BTB games following late tips.

- [ ] **Step 10: Commit**

```bash
git add nba_backtest.js
git commit -m "Add DST-aware timezones, real tip times, and activate late-tip penalty"
```

---

## Phase 3: Team Quality Filter

### Task 7: Add Team Win-Percentage Lookup

**Files:**
- Modify: `nba_backtest.js` (add `getTeamRecord`, new output column)

- [ ] **Step 1: Add running W-L accumulator**

Since the backtest processes dates chronologically, we maintain a running record that gets updated after each date. This uses zero additional API calls — it piggybacks on the games already fetched for each date.

```javascript
// In main(), before the date loop:
const teamRecords = {};  // { teamId: { wins, losses } }

// Inside the date loop, after processing each date's games:
for (const game of games) {
  if (game.status !== 'Final') continue;
  const homeId = game.home_team.id;
  const awayId = game.visitor_team.id;
  if (!teamRecords[homeId]) teamRecords[homeId] = { wins: 0, losses: 0 };
  if (!teamRecords[awayId]) teamRecords[awayId] = { wins: 0, losses: 0 };
  if (game.home_team_score > game.visitor_team_score) {
    teamRecords[homeId].wins++;
    teamRecords[awayId].losses++;
  } else {
    teamRecords[awayId].wins++;
    teamRecords[homeId].losses++;
  }
}

function getWpct(teamId) {
  const r = teamRecords[teamId];
  if (!r) return null;
  const gp = r.wins + r.losses;
  return gp >= 15 ? r.wins / gp : null;  // null if < 15 games (min threshold)
}
```

This uses zero additional API calls — it piggybacks on the games already fetched for each date.

- [ ] **Step 2: Add `edge_team_wpct` to flagged game output**

In the section where `flagged.push({...})` is called, compute the edge team's win percentage:

```javascript
const edgeTeamId = edgeSide === 'HOME EDGE'
  ? game.home_team.id    // home team benefits from the edge
  : edgeSide === 'AWAY EDGE'
    ? game.visitor_team.id
    : null;
const edgeTeamWpct = edgeTeamId ? getWpct(edgeTeamId) : null;

flagged.push({
  // ... existing fields ...
  edgeTeamWpct: edgeTeamWpct !== null ? edgeTeamWpct.toFixed(3) : '',
});
```

Wait — important clarification: the "edge side" means which side has the edge (the rested team), NOT which team is fatigued. So:
- `HOME EDGE` = away team is fatigued, home team has the edge → bet home → edge team is home
- `AWAY EDGE` = home team is fatigued, away team has the edge → bet away → edge team is away

The edge team (the one you'd bet on) is the one we need the win% for.

- [ ] **Step 3: Add header and row for new column**

Add `'Edge Team Wpct'` to the CSV header array and `f.edgeTeamWpct` to the row output.

- [ ] **Step 4: Update running records AFTER processing flagged games for each date**

Important: update `teamRecords` AFTER checking flagged games for the current date (so the record reflects games before today, not including today):

```javascript
// Process flagged games for date (uses teamRecords as of yesterday)
for (const game of games) { ... check flagged ... }

// THEN update records with today's results
for (const game of games) {
  if (game.status !== 'Final') continue;
  // ... update teamRecords ...
}
```

- [ ] **Step 5: Commit**

```bash
git add nba_backtest.js
git commit -m "Add team win-percentage lookup and edge_team_wpct output column"
```

---

### Task 8: Add Team Quality Analysis Section

**Files:**
- Modify: `analyze_backtest.py` (add `analyze_quality` function)

- [ ] **Step 1: Add `edge_team_wpct` accessor**

```python
def edge_wpct(r):
    v = _get(r, 'edge_team_wpct')
    return float(v) if v not in ('', None, 'None') else None
```

- [ ] **Step 2: Add `analyze_quality` function**

```python
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
```

- [ ] **Step 3: Call `analyze_quality` from `main()`**

Add after `analyze_under(rows)`:

```python
analyze_quality(rows)
```

- [ ] **Step 4: Commit**

```bash
git add analyze_backtest.py
git commit -m "Add team quality analysis section to analyze_backtest.py"
```

---

## Phase 4: Re-run Backtests & Validate

### Task 9: Re-run 24-25 Backtest

**Files:**
- Creates: new CSV output (not tracked in git)

- [ ] **Step 1: Run improved backtest on 2024-25 season**

```powershell
$env:BDL_API_KEY="your_key"
node nba_backtest.js --start 2024-11-01 --end 2025-04-13 > NBA_Backtest_24_25_v2.csv
```

Expected runtime: ~2-3 hours due to API rate limiting.

- [ ] **Step 2: Compare new flagged game count against original**

Original had 283 edge games. The new model (with DST, real tip times, team quality) may flag more or fewer. Diff the game sets:

```bash
cut -d, -f1,3,4 NBA_Backtest_24_25.csv | sort > old_games.txt
cut -d, -f1,3,4 NBA_Backtest_24_25_v2.csv | sort > new_games.txt
diff old_games.txt new_games.txt
```

Document how many games were added, dropped, or retained.

- [ ] **Step 3: Smart re-grade — identify new games needing lines**

```bash
comm -13 old_games.txt new_games.txt > new_only_games.txt
wc -l new_only_games.txt
```

This shows how many newly-flagged games need Odds API credits for grading.

---

### Task 10: Grade and Analyze Re-run Results

**Files:**
- Creates: new graded CSV and analysis output (not tracked in git)

- [ ] **Step 1: Grade using consolidated grader**

For games in both old and new sets, we can merge existing graded data. For new games only, run the grader:

```powershell
$env:BDL_API_KEY="your_key"
$env:ODDS_API_KEY="your_key"
python grade_backtest.py --input NBA_Backtest_24_25_v2.csv --output graded_backtest_24_25_v2.csv
```

Note: The smart re-grading optimization (reusing existing lines) requires adding merge logic to `grade_backtest.py`. If the incremental cost is low enough (<500 credits), it may be simpler to just re-grade everything.

- [ ] **Step 2: Run analysis**

```bash
python analyze_backtest.py graded_backtest_24_25_v2.csv
```

- [ ] **Step 3: Compare key metrics against original**

| Metric | Original | V2 Re-run |
|--------|----------|-----------|
| Overall edge ATS | 161W 122L 56.9% | ? |
| Away edge + home fav | 40W 26L 60.6% | ? |
| Both-tired under | 33W 17L 66.0% | ? |
| Delta >= 3 (corrected) | corrupted | ? |
| Edge wpct >= .350 | n/a | ? |

Document results and decide on rule changes.

---

### Task 11: Re-run 25-26 Backtest (Same Process)

- [ ] **Step 1: Run backtest on 2025-26 season**

```powershell
node nba_backtest.js --start 2025-11-01 --end 2026-03-20 > NBA_Backtest_25_26_v2.csv
```

- [ ] **Step 2: Grade and analyze**

```powershell
python grade_backtest.py --input NBA_Backtest_25_26_v2.csv --output graded_backtest_25_26_v2.csv
python analyze_backtest.py graded_backtest_25_26_v2.csv
```

- [ ] **Step 3: Compare against original 25-26 results (82W 105L, 43.9%)**

Critical question: does the team-quality filter improve the 25-26 win rate? If excluding tanking teams (UTA, WAS, etc.) brings the rate above 50%, the filter is validated.

---

### Task 12: Decision Gate & Deploy

- [ ] **Step 1: Review re-run results and decide on rule changes**

Based on the comparison tables from Tasks 12-13, decide:
- Does the primary signal (away edge + home favorite) still hold?
- What team-quality threshold to use (.300, .350, .400)?
- Do fatigue-delta thresholds now sharpen the signal?
- Should the both-tired under signal be kept, modified, or dropped?

- [ ] **Step 2: Tag GitHub repo before deployment**

```bash
cd /path/to/NBA-Edge
git tag v1.0-pre-improvement -m "Pre-improvement baseline for live tool"
```

- [ ] **Step 3: Reconcile sleep formula between local and live**

The spec (section 2.3) identifies three sleep formula divergences. Before updating the live tool, document which formula is canonical:

| Aspect | Local (canonical) | Live (`update_results.py`) | Action |
|--------|------------------|---------------------------|--------|
| Wake-up time | `tipLocal - 3.0` | Fixed 10am | Update live to match local |
| Plane sleep | `min(flight*0.6, midnightDelta)` | `max(0, landing - max(departure, 24.0))` | Update live to match local |
| Scenario C adj | `+1.5` hours | None | Update live to match local |

- [ ] **Step 4: Update live tool files**

Apply validated changes to:
- `nba_edge_v2.html` — fatigue model (DST, real tips, reconciled sleep formula), signal rules, team-quality filter
- `update_results.py` — nightly grader (translated for SGO API, reconciled sleep formula)

Note: The live tool uses SportsGameOdds API, not BallDontLie. Model logic changes must be translated to work with SGO's data structure.

- [ ] **Step 5: Manually verify one day's games**

Run the updated nightly script manually on yesterday's games. Compare output against the old script's output for the same day. Verify scores, fatigue values, and signal determinations match expectations.

- [ ] **Step 6: Commit and push to GitHub**

```bash
git add nba_edge_v2.html update_results.py
git commit -m "Deploy improved fatigue model with team-quality filter"
git push origin main
```

- [ ] **Step 7: Monitor nightly action for 3 days**

Check https://old-head-dev.github.io/NBA-Edge/results.html each morning to verify the nightly action ran successfully and results are being logged correctly.
