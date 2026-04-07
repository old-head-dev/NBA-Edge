# V3 Live Tool Deployment — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace V2's complex fatigue-based live tool with V3's validated simple-rule signals. Deploy S2 (home B2B + traveled → bet away ATS) as the primary signal, track B2 (both B2B + both traveled → home ATS) as monitoring-only, and update the nightly grading pipeline and results dashboard to match.

**Architecture:** The live tool (GitHub Pages), nightly grading script (GitHub Action), and results dashboard all get updated. V3's signal detection is dramatically simpler than V2 — checking "did the home team play away yesterday?" replaces the entire fatigue scoring system. This eliminates the fragile JS/Python model duplication problem.

**Tech Stack:** Browser JavaScript (live tool + dashboard), Python (nightly script), GitHub Pages deployment, BDL + SGO APIs.

**Spec:** `docs/superpowers/specs/2026-04-07-v3-fresh-start-design.md`
**Analysis backing:** `backtest/v3/data/processed/signal_audit_report.txt` — S2 validated at 4/6 leave-one-season-out folds, 3/3 recent seasons, 57-61% away ATS.

---

## Context for the Implementer

### What V3 Signals Replace

**V2 had 3 signals** (all killed by the audit):
- SPREAD: complex fatigue delta >= 4, home on BTB, spread gate -1 to -9.5
- SPREAD-FLIP: same delta, away on BTB, spread gate -1 to -6.5 (reversed direction)
- UNDER: both teams fatigue >= 5, away scenario A, total < 234

**V3 has 2 signals** (validated by 6-season analysis):
- **S2 (PRIMARY):** Home team on B2B AND traveled (played away yesterday) AND away team NOT on B2B → **Bet Away ATS**. Historical: 57-61% across 3 modern seasons.
- **B2 (MONITORING ONLY):** Both teams on B2B AND both traveled → **Track Home ATS** (not a bet recommendation yet). Historical: 57% home, 4/6 folds, but small per-season Ns. Needs more data.

### How to Detect S2 and B2

The detection logic is simple — no fatigue scores needed:

**For each game today, look up each team's PREVIOUS game (from BDL 6-day history):**

```
S2 fires when ALL of:
  1. Home team played YESTERDAY (B2B)
  2. Home team's yesterday game was AWAY (at a different arena → they traveled home)
  3. Away team did NOT play yesterday (not on B2B)

B2 fires when ALL of:
  1. Home team played yesterday (B2B) AND traveled (was away yesterday)
  2. Away team also played yesterday (B2B)
  (Note: away team always traveled to get to tonight's game, so no need to check)
```

**Travel distance** (for display/context, not signal logic):
- Haversine distance from home team's yesterday-game arena to their home arena
- Use ARENAS dict from `backtest/v3/arenas.py` (already built)

### What Stays the Same

- GitHub Pages deployment from repo root on `main`
- BDL API for game schedules and 6-day history
- Odds API for live closing lines (manual refresh, localStorage key)
- SGO API for nightly grading
- GitHub Action at 12:00 UTC
- Arena coordinates and Haversine formula (copy from backtest/v3/arenas.py)

### Key Files

| File | Action | Description |
|------|--------|-------------|
| `nba_edge_v3.html` | **Create** | New V3 live tool (replaces v2) |
| `results_v3.html` | **Create** | New V3 results dashboard |
| `scripts/update_results.py` | **Modify** | Replace V2 signal detection with V3 |
| `data/results_v3.json` | **Create** | Fresh results log for V3 signals |
| `.github/workflows/nightly.yml` | **Modify** | Point to updated script |
| `index.html` | **Modify** | Update landing page links to V3 |
| `nba_edge_v2.html` | **Keep** | Preserve V2 as archive (don't delete) |
| `results.html` | **Keep** | Preserve V2 results as archive |

---

### Task 1: V3 Live Tool — Signal Detection Engine

**Files:**
- Create: `nba_edge_v3.html`

Build the core JavaScript signal detection. This is the heart of the tool.

- [ ] **Step 1: Create nba_edge_v3.html with base structure**

Start with a clean HTML file. Include:
- `<head>` with meta viewport, title "NBA EDGE V3", dark theme CSS (same aesthetic as V2)
- Constants section: `ARENAS` dict (30 teams with lat/lon/tz — copy from backtest/v3/arenas.py), `ALTITUDE_ARENAS`, Haversine function
- BDL API config: base URL `https://api.balldontlie.io/v1`, headers with API key

- [ ] **Step 2: Write the game history fetcher**

```javascript
async function fetchRecentGames(dateStr) {
  // Fetch games from the last 6 days using BDL API
  // Returns array of game objects sorted by date
  // Each game: { date, home_team, visitor_team, home_team_score, visitor_team_score, status }
}
```

Reuse V2's BDL fetch pattern (it works). The key difference: we only need dates and team abbreviations — no complex fatigue analysis.

- [ ] **Step 3: Write the schedule context builder**

```javascript
function buildTeamHistory(recentGames) {
  // For each team, build ordered list of recent games
  // Returns: { "BOS": [{date, arena, wasHome}, ...], "LAL": [...], ... }
}

function getScheduleContext(team, gameDate, gameArena, teamHistory) {
  // gameArena = home team abbreviation (game is always at home team's arena)
  // Returns: { isB2B, traveled, travelDist, prevArena, daysRest }
  // isB2B: team played yesterday (calendar days between == 1)
  // traveled: yesterday's game was at a different arena than TONIGHT'S arena
  //   (must match backtest/v3/schedule.py line 176: prev_arena != arena_tonight)
  // travelDist: haversine(prevArena, gameArena) — only if traveled
}
```

- [ ] **Step 4: Write the signal detector**

```javascript
function detectSignals(game, teamHistory) {
  const homeCtx = getScheduleContext(game.home, game.date, teamHistory);
  const awayCtx = getScheduleContext(game.away, game.date, teamHistory);

  const signals = [];

  // S2: Home B2B + traveled, away NOT B2B → Bet Away ATS
  if (homeCtx.isB2B && homeCtx.traveled && !awayCtx.isB2B) {
    signals.push({
      id: 'S2',
      type: 'primary',
      label: 'BET AWAY ATS',
      detail: `Home team (${game.home}) flew home from ${homeCtx.prevArena} last night (${homeCtx.travelDist}mi)`,
      confidence: 'VALIDATED',  // 4/6 folds, 57-61%
    });
  }

  // B2: Both B2B + both traveled → Track Home ATS (monitoring)
  if (homeCtx.isB2B && homeCtx.traveled && awayCtx.isB2B) {
    signals.push({
      id: 'B2',
      type: 'monitoring',
      label: 'TRACKING: HOME ATS',
      detail: `Both teams on B2B. Home (${game.home}) traveled ${homeCtx.travelDist}mi.`,
      confidence: 'MONITORING',  // 4/6 folds but small N — not yet a bet
    });
  }

  return signals;
}
```

- [ ] **Step 5: Commit**

```bash
git add nba_edge_v3.html
git commit -m "feat(v3): live tool signal detection — S2 primary, B2 monitoring"
```

---

### Task 2: V3 Live Tool — UI and Rendering

**Files:**
- Modify: `nba_edge_v3.html`

Build the UI layer on top of the signal detection from Task 1.

- [ ] **Step 1: Design the layout**

Structure (top to bottom):
1. **Header bar**: "NBA EDGE" logo (left), "V3" badge, date/time (right), Odds API button
2. **Signal summary cards**: Today's active S2 signals count, running season record, historical hit rate with 95% CI
3. **Games list**: All today's games. Games with signals get a prominent signal card. Games without signals shown in compact form.
4. **Signal card design** for S2:
   - Signal pill: "S2 — BET AWAY" in green
   - Matchup: "BOS @ LAL" with team abbreviations
   - Context line: "LAL flew home from DEN last night (862mi)"
   - Closing spread (from Odds API, if available)
   - Travel distance visualization (simple bar or number)
5. **B2 monitoring card** — same layout but muted colors, "MONITORING" badge instead of "BET"
6. **Signal rules reference** at bottom: S2 definition, historical stats, B2 explanation

- [ ] **Step 2: Write the CSS**

Dark theme matching V2 aesthetic. Key classes:
- `.signal-card` — prominent card for S2 games
- `.signal-card.monitoring` — muted version for B2
- `.signal-pill.primary` — green badge for S2
- `.signal-pill.monitoring` — gray/amber badge for B2
- `.stat-card` — summary stat boxes at top
- `.game-row.no-signal` — compact row for non-signal games

- [ ] **Step 3: Write the render functions**

```javascript
function renderSignalSummary(signals) {
  // Top bar: "2 signals today | Season: 8W-5L (61.5%) | Historical: 57-61% [CI: 52.9-68.8%]"
}

function renderGameCard(game, signals) {
  // If S2/B2 signal → full signal card with details
  // If no signal → compact one-line row
}

function renderSignalReference() {
  // Bottom section explaining S2 and B2 with historical stats
}
```

- [ ] **Step 4: Wire up the main flow**

```javascript
async function main() {
  const today = getCurrentDateET();
  const recentGames = await fetchRecentGames(today);
  const todayGames = await fetchTodayGames(today);
  const teamHistory = buildTeamHistory(recentGames);

  const gameSignals = todayGames.map(game => ({
    game,
    signals: detectSignals(game, teamHistory),
  }));

  // Sort: signal games first, then by game time
  gameSignals.sort((a, b) => b.signals.length - a.signals.length);

  renderSignalSummary(gameSignals);
  gameSignals.forEach(gs => renderGameCard(gs.game, gs.signals));
  renderSignalReference();
}
```

- [ ] **Step 5: Add Odds API integration**

Copy V2's Odds API pattern (localStorage key, manual refresh button). When odds are loaded, overlay closing spread on signal cards. This enables CLV tracking:
- Record the spread at the time the user views the signal
- Compare to closing spread after the game (handled by nightly script)

- [ ] **Step 6: Add date navigation**

Copy V2's date picker pattern — prev/next day buttons, calendar picker. Allows viewing past days' signals and results.

- [ ] **Step 7: Test in browser**

Open `nba_edge_v3.html` in browser. Verify:
- Games load from BDL API
- S2 signals fire for home teams that played away yesterday
- B2 signals fire when both teams are B2B + traveled
- Non-signal games show in compact form
- Odds API overlay works

- [ ] **Step 8: Commit**

```bash
git add nba_edge_v3.html
git commit -m "feat(v3): live tool UI — signal cards, summary stats, odds overlay"
```

---

### Task 3: Nightly Grading Script — V3 Signals

**Files:**
- Modify: `scripts/update_results.py`
- Create: `data/results_v3.json`

- [ ] **Step 1: Define V3 results schema**

```json
{
  "version": "3.0",
  "games": [
    {
      "date": "2026-04-08",
      "matchup": "BOS @ LAL",
      "away": "BOS",
      "home": "LAL",
      "away_score": 112,
      "home_score": 105,
      "signal": "S2",
      "signal_detail": "LAL flew home from DEN (862mi)",
      "home_b2b": true,
      "home_traveled": true,
      "home_travel_dist": 862,
      "away_b2b": false,
      "close_spread": -3.5,
      "close_total": 224.5,
      "ats_result": "away",
      "ou_result": "under",
      "signal_result": "WIN"
    }
  ],
  "meta": {
    "last_updated": "2026-04-08T12:00:00Z",
    "model_version": "V3-S2",
    "historical_rate": "57-61% away ATS (6 seasons, 300 games)"
  }
}
```

`signal_result` derivation:
- S2: "WIN" if ats_result == "away", "LOSS" if "home", "PUSH" if "push"
- B2: "WIN" if ats_result == "home", "LOSS" if "away", "PUSH" if "push"

- [ ] **Step 2: Refactor update_results.py signal detection**

Replace V2's `get_betting_signals()` / `analyze_fatigue()` / `compute_fatigue_score()` with:

```python
def detect_v3_signals(game, team_history):
    """Detect V3 signals for a game.
    
    Returns list of signal dicts, or empty list if no signals.
    """
    home = game["home"]
    away = game["away"]
    
    home_ctx = get_schedule_context(home, game["date"], team_history)
    away_ctx = get_schedule_context(away, game["date"], team_history)
    
    signals = []
    
    # S2: Home B2B + traveled, away NOT B2B
    if home_ctx["is_b2b"] and home_ctx["traveled"] and not away_ctx["is_b2b"]:
        signals.append({
            "signal": "S2",
            "bet_direction": "away",
            "detail": f"{home} flew home from {home_ctx['prev_arena']} ({home_ctx['travel_dist']}mi)",
        })
    
    # B2: Both B2B + both traveled
    if home_ctx["is_b2b"] and home_ctx["traveled"] and away_ctx["is_b2b"]:
        signals.append({
            "signal": "B2",
            "bet_direction": "home",
            "detail": f"Both B2B. {home} traveled {home_ctx['travel_dist']}mi",
        })
    
    return signals

def get_schedule_context(team, game_date, game_arena, team_history):
    """Simple schedule context — just B2B and travel detection.
    
    game_arena: the HOME team abbreviation (game is always at home arena).
    Must match backtest/v3/schedule.py definition: traveled = prev_arena != arena_tonight.
    """
    prev_games = team_history.get(team, [])
    if not prev_games:
        return {"is_b2b": False, "traveled": False, "travel_dist": 0, "prev_arena": None}
    
    last = prev_games[-1]
    days_since = (game_date - last["date"]).days
    is_b2b = days_since == 1  # played exactly yesterday (not today, not 2+ days ago)
    
    # "traveled" = previous game was at a different arena than TONIGHT's game arena
    # For home team: prev_arena != their own arena (they were away yesterday)
    # For away team: prev_arena != tonight's venue (they came from somewhere else)
    traveled = last["arena"] != game_arena
    travel_dist = 0
    if traveled:
        travel_dist = haversine(ARENAS[last["arena"]], ARENAS[game_arena])
    
    return {
        "is_b2b": is_b2b,
        "traveled": traveled,
        "travel_dist": round(travel_dist),
        "prev_arena": last["arena"],
    }
```

- [ ] **Step 3: Update the grading logic**

Replace V2 grading (edge_ats, flip_ats, under_result) with V3 grading:

```python
def grade_signal(signal, ats_result):
    """Grade a V3 signal result."""
    if signal["signal"] == "S2":
        # S2 bets AWAY
        if ats_result == "away": return "WIN"
        if ats_result == "home": return "LOSS"
        return "PUSH"
    elif signal["signal"] == "B2":
        # B2 tracks HOME
        if ats_result == "home": return "WIN"
        if ats_result == "away": return "LOSS"
        return "PUSH"
```

- [ ] **Step 4: Update JSON writing**

Write to `data/results_v3.json` (not results.json — keep V2 results intact). Append new game records, update meta.

- [ ] **Step 5: Remove V2 fatigue code**

Delete from update_results.py:
- `compute_fatigue_score()`, `analyze_fatigue()`, `estimate_btb_sleep()`
- `get_betting_signals()` (V2 version)
- All scenario classification code (A/B/C)
- TANK_WATCH list
- Any V2-specific constants

Keep:
- BDL API fetch functions
- SGO API fetch functions  
- Haversine, ARENAS dict
- Team history builder
- Date/timezone utilities
- Git commit logic

- [ ] **Step 6: Test locally**

```bash
python scripts/update_results.py --dry-run
```

Verify it detects correct signals for yesterday's games without writing to JSON.

- [ ] **Step 7: Commit**

```bash
git add scripts/update_results.py data/results_v3.json
git commit -m "feat(v3): nightly grading — S2 primary signal, B2 monitoring, V3 results schema"
```

---

### Task 4: V3 Results Dashboard

**Files:**
- Create: `results_v3.html`

- [ ] **Step 1: Build results dashboard**

Structure:
1. **Header**: "NBA EDGE V3 RESULTS", link back to live tool
2. **Summary cards**: S2 record (W-L, win%), B2 record (W-L, win%), Combined, with 95% Wilson CIs
3. **Model validation bar**: S2 progress toward 50+ samples, current rate vs historical baseline (57-61%)
4. **Filter row**: Signal type (ALL / S2 / B2), Result (WINS / LOSSES / PUSHES)
5. **Results table**: Date, Matchup, Signal, Travel Distance, Spread, ATS Result, Signal Result

Load from `data/results_v3.json`.

- [ ] **Step 2: Add Wilson CI computation in JavaScript**

```javascript
function wilsonCI(wins, total, z = 1.96) {
  if (total === 0) return { lo: 0, hi: 0 };
  const p = wins / total;
  const denom = 1 + z * z / total;
  const centre = (p + z * z / (2 * total)) / denom;
  const spread = z * Math.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denom;
  return { lo: Math.max(0, centre - spread), hi: Math.min(1, centre + spread) };
}
```

Display: "S2: 8W-5L — 61.5% [43.1-77.0%] | Historical: 57-61%"

- [ ] **Step 3: Test with sample data**

Create `data/results_v3.json` with 2-3 sample entries to verify the dashboard renders correctly.

- [ ] **Step 4: Commit**

```bash
git add results_v3.html
git commit -m "feat(v3): results dashboard with Wilson CIs and signal filtering"
```

---

### Task 5: GitHub Action Update + Landing Page

**Files:**
- Modify: `.github/workflows/nightly.yml`
- Modify: `index.html`

- [ ] **Step 1: Update nightly workflow**

The workflow should now commit changes to `data/results_v3.json` instead of (or in addition to) `data/results.json`. Update the git add/commit step.

If the script writes to `data/results_v3.json`, update the workflow's commit step:
```yaml
- name: Commit results
  run: |
    git add data/results_v3.json
    git diff --cached --quiet || git commit -m "results: $(date -u +%Y-%m-%d)"
    git push
```

- [ ] **Step 2: Update landing page**

`index.html` should link to V3 as the primary tool:
- Main link → `nba_edge_v3.html`
- Results link → `results_v3.html`
- Keep V2 links as "Archive" at the bottom (don't delete)

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/nightly.yml index.html
git commit -m "feat(v3): update nightly action and landing page for V3 deployment"
```

- [ ] **Step 4: Push and verify deployment**

```bash
git push origin main
```

Check:
- `https://old-head-dev.github.io/NBA-Edge/nba_edge_v3.html` loads
- `https://old-head-dev.github.io/NBA-Edge/results_v3.html` loads
- GitHub Action tab shows next run scheduled

---

### Task 6: Verify End-to-End

**No new files — integration verification.**

- [ ] **Step 1: Open V3 live tool in browser**

Navigate to `nba_edge_v3.html`. Verify:
- Today's games load
- S2 signals appear for correct games (home team played away yesterday)
- B2 monitoring signals appear where appropriate
- Non-signal games shown in compact form
- Odds API overlay works

- [ ] **Step 2: Check nightly action**

After the next 12:00 UTC run, check:
- `data/results_v3.json` has new entries
- Signal detection matches what the live tool showed yesterday
- ATS results are correctly graded

- [ ] **Step 3: Verify results dashboard**

Open `results_v3.html`. Confirm:
- Data loads from results_v3.json
- Summary cards compute W-L correctly
- Wilson CIs display
- Filters work

- [ ] **Step 4: Cross-check with V2 results**

For any game that BOTH V2 and V3 flagged, compare:
- Did V3's simpler signal detection reach the same conclusion as V2's complex fatigue model?
- Do the grading outcomes match?

- [ ] **Step 5: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix(v3): integration fixes from end-to-end verification"
git push
```

---

## Decision Gate

After 2-3 weeks of live V3 results (~10-20 S2 signals):

1. **Is S2 performing near its historical rate?** (Above 52.38% → continue. Below 45% → pause and investigate.)
2. **Is B2 accumulating useful data?** (Track direction and rate — if 10+ games and still >55% home, consider promoting to primary.)
3. **Is CLV positive?** (Are we getting value at the lines we see, or has the market already moved?)

## Notes for Implementer

- **Do NOT delete V2 files.** Keep `nba_edge_v2.html`, `results.html`, `data/results.json` as archives. Users may want to reference historical V2 results.
- **Arena data formats differ between JS and Python.** The backtest `arenas.py` uses integer UTC offsets (`"tz": -5`). The existing `update_results.py` uses IANA timezone names (`"America/New_York"`) for `ZoneInfo()` calls. For the Python nightly script, keep the IANA format already in use. For the JS live tool, integer offsets are fine (only used for display, not date math). Don't blindly copy one format into the other.
- **Keep `SGO_TEAM_MAP` and `abbr()`** in update_results.py — these map SGO's long-form team IDs to 3-letter abbreviations. Still needed for game discovery.
- **The Haversine function** already exists in both V2 HTML and Python. Reuse the existing implementations.
- **Signal detection must be identical** in the JS live tool and the Python nightly script. The "traveled" definition MUST match `backtest/v3/schedule.py` line 176: `prev_arena != arena_tonight` (NOT `prev_arena != team_home_arena`). Test a few games in both to confirm they agree.
- **results_v3.json starts empty** — `{"version": "3.0", "games": [], "meta": {"last_updated": null}}`. Commit this seed file BEFORE the first GitHub Action run so `git add` doesn't fail.
- **Mobile responsiveness:** V2's responsive CSS works well on iPhone. Carry the same responsive patterns into V3. Test on iPhone Safari — verify signal cards are readable, no horizontal scroll.
- **Historical rate display:** Show the combined rate with full Wilson CI (56.8% [50.8-62.6%]) and per-season breakdown. Do NOT display "57-61%" as a standalone range — this cherry-picks the good seasons. The spec's anti-pattern #2 requires per-season reporting.
- **Push handling in win% display:** Exclude pushes from the denominator per spec. A 5W-3L-2P record displays as 5/8 = 62.5%, not 5/10.
- **ET date handling in JS:** `getCurrentDateET()` must derive the current Eastern Time date using timezone-aware logic, not just `new Date()`. A West Coast user at 11pm PT is already in the next ET day. V2 handles this — reuse the pattern.
- **Nightly workflow transition:** Update the Action to commit `data/results_v3.json`. Remove the `data/results.json` line from git add (V2 script no longer writes to it). V2 results are preserved as-is but no longer updated.
- **LOSO validation was run interactively** during the design session (6 seasons including 2025-26 MGM data). Results: S2 passed 4/6 folds (3/3 recent). A formal `validation_report.txt` should be generated and saved by running `python -m v3.validate_signals` before deployment.
