# NBA Edge Model — Improvement Plan (Approach B)

**Date:** 2026-03-20
**Status:** Approved — pending implementation
**Backup:** `v1.0-baseline` tag on commit `09e4e07`

## Context

The NBA Edge model is a fatigue-based sports betting tool that scores team tiredness on a 0-10 scale and identifies games where one team has a significant fatigue disadvantage. It runs live at https://old-head-dev.github.io/NBA-Edge/ with a nightly GitHub Action grading results.

### Current Performance

- **2024-25 backtest (283 games):** 56.9% overall edge ATS; 60.6% on the primary signal (away edge + home favorite, n=66)
- **2025-26 live (7 games):** 3W 3L spreads, 0W 1L under. Two of three spread losses involved Utah (tanking team).
- **Both-tired under (24-25):** 66.0% (n=50) — promising but small sample

### Problems Identified

1. **Critical bug** in `analyze_backtest.py` — fatigue accessors return game scores instead of fatigue scores, corrupting all delta-threshold analysis
2. **Hardcoded tip time** (8pm) instead of actual game times — understates fatigue for late-night games
3. **No DST handling** — timezone offsets wrong by 1 hour during daylight saving months
4. **Dead code** — late-tip penalty exists but never fires (hardcoded input of 19.5 vs threshold of 21.5)
5. **No team-quality filter** — tanking teams generate false signals
6. **Duplicate scripts** — two nearly identical copies of backtest and grading scripts
7. **Hardcoded API key** in `nba_backtest.js`

## Phase 0: Backup (Complete)

Git tag `v1.0-baseline` created on current commit. Revert with `git checkout v1.0-baseline` at any time. The live GitHub Pages tool is a separate repository and will not be modified until Phase 4.

## Phase 1: Bug Fixes & Code Cleanup

No model changes. Fix what's broken and clean up the codebase.

### 1.1 Fix analysis bug and column naming

**File:** `analyze_backtest.py`, lines 43-44

**Current (broken):**
```python
def away_fat(r):  return float(_get(r, 'away_score', 'away_fatigue') or 0)
def home_fat(r):  return float(_get(r, 'home_score', 'home_fatigue') or 0)
```

**Fixed:**
```python
def away_fat(r):  return float(_get(r, 'away_fatigue', 'away_score') or 0)
def home_fat(r):  return float(_get(r, 'home_fatigue', 'home_score') or 0)
```

The `_get()` helper returns the first matching key. Swapping the order ensures `away_fatigue` (the model's score, e.g. 10.0) is found before `away_score` (the game's points, e.g. 128).

**Root cause fix:** The backtest CSV output headers use `Away Score` / `Home Score` for fatigue scores (which get lowercased to `away_score` / `home_score` by the analysis loader), colliding with the grading script's actual game-score columns of the same name. Rename the backtest output headers to `Away Fatigue` / `Home Fatigue` to eliminate the ambiguity at the source. This makes the `_get` fix above a belt-and-suspenders safety measure rather than the sole defense.

### 1.2 Remove hardcoded API key

**File:** `nba_backtest.js`, line 4

Replace the hardcoded BallDontLie API key with `process.env.BDL_API_KEY` and add the same validation/exit check that `nba_backtest_24_25.js` already has.

### 1.3 Consolidate duplicate scripts

**Pre-consolidation regression check:** Before merging, run both existing scripts on a small date range (one week), save the output, and use it as a regression test after the merge. This costs 5 minutes and catches silent breakage.

**Backtest:** Merge `nba_backtest.js` and `nba_backtest_24_25.js` into a single `nba_backtest.js` that accepts season start/end dates as CLI arguments.

Usage: `node nba_backtest.js --start 2024-11-01 --end 2025-04-13`

Defaults: current season dates (2025-11-01 to 2026-04-13).

Behavioral differences between the two scripts (canonical choice in **bold**):

| Aspect | `nba_backtest.js` | `nba_backtest_24_25.js` | Canonical |
|--------|-------------------|------------------------|-----------|
| API key | Hardcoded string | **`process.env.BDL_API_KEY`** | env var |
| Season dates | 2025-11-01 to 2026-03-03 | 2024-11-01 to 2025-04-13 | **CLI args** |
| FLAG_THRESHOLD | 5 | 5 | **5 (same)** |
| Key validation | None | **Exit with error if missing** | validate |
| All other logic | Identical | Identical | — |

**Grading:** Merge `grade_backtest.py` and `grade_backtest_24_25.py` into a single `grade_backtest.py` that accepts input/output file paths as CLI arguments. The consolidated grader should accept **CSV input directly** (not just XLSX), eliminating the manual XLSX import step. XLSX support is retained as a fallback for existing data files.

Usage: `python grade_backtest.py --input graded_backtest_24_25.csv --output graded_backtest_24_25_regraded.csv`

Old files are preserved via the `v1.0-baseline` tag.

### 1.5 Project hygiene

- `.gitignore`: exclude `.xlsx`, `output_log.txt`, `.claude/`, `node_modules/`
- `requirements.txt`: `openpyxl`, `requests`
- `package.json`: basic manifest with project metadata, no external dependencies

## Phase 2: Fatigue Model Improvements

Better inputs into the existing model structure. No new signals or scoring changes.

### 2.1 Use actual previous-game tip times & activate late-tip penalty

**Current:** `estimateBTBSleep` hardcodes `prevTipLocal = 20.0` (8pm local). Additionally, `computeFatigueScore` has a late-tip penalty (`prevTipLocalHr >= 21.5 → +0.5`) that never fires because `analyzeFatigue` always passes `19.5`.

**Change:** In `calcRest`, extract the `datetime` field from the last game in history and return it alongside the existing rest data.

Modified `calcRest` return shape:
```javascript
// Current:  { daysRest, prevArena, wasHomeLastGame, gamesIn4, gamesIn6, recentAltitudeVisit }
// New:      { daysRest, prevArena, wasHomeLastGame, gamesIn4, gamesIn6, recentAltitudeVisit, prevTipDatetime }
```

Thread `prevTipDatetime` through to:
1. `estimateBTBSleep` — replaces hardcoded `prevTipLocal = 20.0` with actual local tip time
2. `analyzeFatigue` → `computeFatigueScore` — passes real `prevTipLocalHr` instead of `19.5`, activating the late-tip penalty for games that actually tipped after 9:30pm local

The BallDontLie API already returns `datetime` for each game. The backtest already fetches game history via `calcRest`. The data is there — it just needs to be threaded through.

**Impact:** A team that played a 10:30pm ET tip in Portland and flies to Boston for a 7pm tip the next night currently gets the same sleep estimate as one that played a 7pm tip in DC. After this fix, the Portland game correctly shows ~2-3 fewer hours of sleep, potentially crossing the `< 4h = +4 points` threshold. The late-tip penalty also starts firing for games with 9:30pm+ local tips.

### 2.2 DST-aware timezone handling

**Current:** All timezone offsets are hardcoded to standard time in the ARENAS dictionary (ET=-5, CT=-6, MT=-7, PT=-8).

**Change:** Replace static `tz` offsets with IANA timezone identifiers:
```javascript
ATL: { lat: 33.7573, lon: -84.3963, tz: 'America/New_York' }
DEN: { lat: 39.7487, lon: -105.0077, tz: 'America/Denver' }
PHX: { lat: 33.4457, lon: -112.0712, tz: 'America/Phoenix' }  // no DST
```

Use `Intl.DateTimeFormat` (built into Node.js, no external dependencies) to compute the correct UTC offset for a given game date.

**Also fix `parseTipET`** (line 51 of `nba_backtest_24_25.js`): This function hardcodes `UTC-5` for Eastern Time conversion (`d.getUTCHours() - 5`). During EDT months it should use `UTC-4`. Apply the same IANA-based DST-aware conversion here — this function feeds the entire sleep estimation pipeline.

**Special case:** Phoenix (PHX) does not observe DST. The current hardcoded MT=-7 is actually correct year-round for Phoenix. The new implementation must handle this — `America/Phoenix` does this correctly.

**Impact:** During DST months (most of Nov, all of Mar-Apr), eastbound travel penalties and sleep estimates are off by 1 hour. For a BTB with a 3-timezone eastbound flight, that's the difference between 5 hours estimated sleep and 4.

### 2.3 Reconcile sleep formula with live tool

**Important discovery:** The live `update_results.py` already uses IANA timezones and a `get_utc_offset()` function for DST-aware handling. However, its sleep formula diverges from the local backtest in material ways:

| Aspect | Local backtest | Live `update_results.py` |
|--------|---------------|--------------------------|
| Wake-up time | `tipLocal - 3.0` (3h before tip) | Fixed at 10am (`34.0`) |
| Plane sleep | `midnightDelta > 0 ? min(flight*0.6, delta) : 0` | `max(0, landing - max(departure, 24.0)) * 0.5` |
| Scenario C sleep adj | `+1.5` hours added | No adjustment |

**Action:** Choose a single canonical sleep formula, document it, and ensure both local and live implementations match after deployment. The local backtest formula is more nuanced (tip-relative wake-up, scenario adjustments) — recommend adopting it as canonical and updating the live tool to match.

## Phase 3: Team Quality Filter

A new post-filter on the model's output. Does not change the fatigue scoring algorithm.

### 3.1 Add team win-percentage lookup

Add a `getTeamRecord(teamId, beforeDate)` function to the backtest script that computes a team's W-L record from season start through the day before the game (full season-to-date). The BallDontLie API already provides the data needed — the game history fetched for fatigue calculation includes wins and losses.

**Minimum games threshold:** Do not apply the quality filter until a team has played at least 15 games. Early-season records (first 2-3 weeks) are too noisy to distinguish tanking from slow starts. Games before the threshold is met are passed through without filtering.

### 3.2 Add quality column to output

New column `edge_team_wpct` in the backtest CSV output — the win percentage of the team the model suggests betting on (the edge-side team).

### 3.3 Analysis threshold testing

The analysis script gains a new filter section: "edge team win% >= X" tested at .300, .350, .400, .450. This identifies the threshold where tanking teams drop out without eliminating real signals.

### 3.4 Integration into signal rules

Once the threshold is validated via backtest, the live tool gains the same filter. Games where the edge-side team is below the quality threshold are either:
- Suppressed entirely (no signal shown), or
- Shown with a warning label ("low-quality team — proceed with caution")

User decides which approach based on backtest results.

### Why win percentage and not net rating

- Available directly from existing API calls (no new data source)
- Simplest possible quality signal
- Sufficient to identify tanking teams (.250 or worse)
- Net rating can be explored in a future version if needed

## Phase 4: Re-run Backtests & Validate

### 4.1 Re-run improved backtest

Run the consolidated, improved backtest on:
- **2024-25 season** (2024-11-01 to 2025-04-13) — the season with the existing 56.9% baseline
- **2025-26 season** (2025-11-01 to 2026-03-20) — the current season

This produces new CSVs with corrected fatigue scores and the `edge_team_wpct` column.

**API cost:** BallDontLie only (free, rate-limited at ~5 req/min). Expect ~2-3 hours of runtime per season due to rate limiting.

### 4.2 Smart re-grading

Compare new flagged games against existing graded CSVs by matching on `(date, away, home)`:
- **Games in both old and new sets:** Reuse existing scores and closing lines from the graded CSV (0 Odds API credits). The fatigue scores will differ but actual game scores and lines are historical facts.
- **Newly flagged games** (in new set but not old): Fetch scores from BallDontLie (free) and closing lines from The Odds API (30 credits per new date).
- **Dropped games** (in old set but not new): Simply excluded from the new analysis. No action needed.

Estimated incremental cost: The improved model will shift which games cross the flag threshold, but the bulk of high-fatigue games (BTB road trips, etc.) will remain flagged. Expect ~10-30 new dates needing lines = 300-900 credits. Worst case (completely different game set): ~160 dates × 30 = 4,800 credits. Either way, well within the 10,690 remaining.

### 4.3 Re-run analysis

Run the fixed `analyze_backtest.py` on both seasons' graded data. For the first time, fatigue-delta thresholds will operate on actual fatigue scores.

### 4.4 Key comparisons

| Metric | Original (24-25) | Re-run (24-25) | Re-run (25-26) |
|--------|-----------------|----------------|----------------|
| Overall edge ATS | 161W 122L 56.9% | ? | ? |
| Away edge + home fav | 40W 26L 60.6% | ? | ? |
| Both-tired under | 33W 17L 66.0% | ? | ? |
| Delta >= 3 (ATS) | corrupted | first valid run | first valid run |
| Edge team wpct >= .350 | n/a | new filter | new filter |

### 4.5 Decision gate

Based on re-run results:
- Confirm or update the primary signal rules
- Set the team-quality threshold
- Determine if delta thresholds sharpen the signal (now that the bug is fixed)
- Decide which changes to deploy to the live tool

### 4.6 Deploy to live tool

**Important note:** The live `update_results.py` uses the SportsGameOdds (SGO) API, not BallDontLie. Any fatigue model changes must be translated to work with SGO's data structure — this is not a copy-paste from the local backtest. The live tool also already has some Phase 2 features (IANA timezones via `get_utc_offset()`), so deployment is partly bringing the local model up to parity and partly adding genuinely new features (team quality, real tip times, reconciled sleep formula).

1. Tag the GitHub repo's current state before changes
2. Update `nba_edge_v2.html` — fatigue model, signal rules, team-quality filter
3. Update `update_results.py` — nightly grader with the same improvements (translated for SGO API)
4. Manually verify one day's games before re-enabling the nightly action

## API Credit Budget

| Action | API | Estimated Cost |
|--------|-----|---------------|
| Re-run backtest (both seasons) | BallDontLie | Free (rate-limited) |
| Re-grade new flagged games | The Odds API | ~100-500 credits |
| **Total Odds API** | | **~100-500 of 10,690 remaining** |

## File Changes Summary

| File | Action |
|------|--------|
| `nba_backtest.js` | Rewrite: consolidate, env var API key, real tip times, DST, team quality, CLI args |
| `nba_backtest_24_25.js` | Delete (consolidated into `nba_backtest.js`) |
| `grade_backtest.py` | Rewrite: consolidate, CLI args |
| `grade_backtest_24_25.py` | Delete (consolidated into `grade_backtest.py`) |
| `analyze_backtest.py` | Fix: `away_fat`/`home_fat` bug, add team-quality analysis section |
| `.gitignore` | New |
| `requirements.txt` | New |
| `package.json` | New |

## Risks

1. **Improved model flags different games** — the 56.9% baseline may shift. Could go up or down. This is the whole point of re-running, but we should be prepared for either outcome.
2. **Rate limiting extends runtime** — BallDontLie at 5 req/min means ~2-3 hours per season for the backtest. Plan for this.
3. **The 25-26 season may still underperform** — if the market has gotten sharper at pricing fatigue, no model improvement will recover the edge. The team-quality filter may help, but it's not guaranteed.
4. **Live tool changes require careful testing** — the nightly GitHub Action runs automatically. A broken `update_results.py` would silently fail and stop logging results.
5. **Consolidation regression** — merging duplicate scripts without automated tests risks silent breakage. Mitigated by the pre-consolidation regression check in Phase 1.3.
6. **Live tool uses different API (SGO vs BDL)** — model changes cannot be copy-pasted to the live tool. SGO returns data in a different structure. Phase 4.6 deployment requires translation, not just file replacement.
