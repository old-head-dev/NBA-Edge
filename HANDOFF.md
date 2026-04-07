# Session Handoff — 2026-03-21 (Session 2)

## What Was Done

### Local Project (NBA Model)
- `68e744e` Committed outstanding analysis scripts, reports, and future plan doc
- Merged `feature/model-improvements` → `master` (fast-forward)

### Live Tool (NBA-Edge repo — all deployed to GitHub Pages)

**Signal Rules (Tiers 1-2):**
- `d691f3c` V2.1 signal engine: SPREAD (delta>=4, home BTB, spread -1 to -9.5), UNDER (3 confidence tiers +++/++/+, Away=A only, total<234 gate), SPREAD-FLIP new signal (delta>=4, away BTB, spread -1 to -6.5)
- `d801073` Tank watch warnings (UTA/WAS/POR/CHA/BKN) with "tank risk" badge
- `2008004` FLIP only fires when Odds API provides spread data (no false signals without odds)

**Fatigue Model:**
- Sleep scoring: <4hrs = +4 (removed old <2hrs = +5 tier)
- `a5fa172` Sleep formula simplified: arrival-to-10am, no plane sleep stacking, no Scenario C +1.5 bonus
- `d97c8e9` Wake-up cap aligned to 10am (34.0) across all paths (road BTB, home-home, Scenario B)
- `1a798c0` Fixed crash from dangling hotelSleepHrs/planeSleepHrs references

**New Features (Tier 3):**
- `1fad292` Odds API integration — manual refresh only (↻ ODDS button), localStorage key, averages across bookmakers
- Signal Mode toggle — hides non-actionable games
- `635e888` Signal rules reference section at bottom of page
- `eb1a54e` Odds font matched to signal strip; total ≥234 warning in red

**Results Dashboard (results.html):**
- FLIP filter button, confidence tiers in signal pills, flip_ats display, compound signal types

**Nightly Script (update_results.py):**
- All signal rules mirrored (SPREAD gate -1 to -9.5, FLIP gate -1 to -6.5, UNDER total<234)
- flip_ats grading, under_confidence in results.json
- Same fatigue model fixes (10am cap, no plane sleep, no +1.5)

## What's Left

1. **Monitor nightly action** — Watch results.html each morning for 3-5 days to confirm the nightly grader works with the new signal rules. First graded game under V2.1 rules will appear tomorrow morning.
2. **Update TANK_WATCH monthly** — Currently hardcoded: UTA, WAS, POR, CHA, BKN. Check standings periodically.
3. **Win% accumulator (deferred)** — Plan called for dynamic wpct tracking in Python. TANK_WATCH proxy is sufficient for now. Revisit if team quality shifts mid-season.
4. **Reconcile local backtest** — The local `nba_backtest.js` still uses the old sleep formula (tipLocal-3.0, plane sleep stacking, Scenario C +1.5). If you re-run backtests, scores will differ from the live tool. Consider updating the local backtest to match the simplified formula (10am cap, no extras).
5. **Tiers 4-5 (future)** — Saved at `docs/superpowers/specs/2026-03-21-model-architecture-future-plan.md`. Includes continuous scoring, empirical weights, net rating, threshold validation.

## Known Issues & Gotchas

- **Browser caching on mobile** — GitHub Pages caches aggressively. After deploying changes, may need to clear Safari cache or use incognito to see updates on iPhone.
- **Local backtest divergence** — Local `nba_backtest.js` sleep formula now differs from live tool. Live uses fixed 10am cap; local uses tipLocal-3.0 which produces near-zero hotel sleep due to coordinate system mismatch. The live tool's formula is correct per user direction.
- **NBA-Edge cloned locally** — The GitHub repo is now also cloned at `C:\Users\jkher\Documents\Claude\NBA-Edge` for direct editing. Push from there for live tool changes.
- **Odds API credits** — Manual refresh only. Each click = 1 API call. ~10,690 credits remaining on $30/month plan.
- **`pr-1-full-diff.txt`** — Untracked temp file in NBA-Edge repo from the code review. Can be deleted.

## Starter Prompt

```
Read HANDOFF.md in the NBA Model project. This continues work on the NBA Edge fatigue betting model. The V2.1 live tool is deployed at https://old-head-dev.github.io/NBA-Edge/nba_edge_v2.html with refined signal rules, SPREAD-FLIP signal, Odds API integration, and fatigue model fixes. The nightly grading script has been updated to match. The NBA-Edge repo is cloned at C:\Users\jkher\Documents\Claude\NBA-Edge. Key next step: monitor the nightly action results for the next few days to confirm V2.1 signals are being graded correctly. If re-running backtests, note the local nba_backtest.js sleep formula diverges from the live tool — update it to match (fixed 10am wake-up cap, no plane sleep stacking, no Scenario C +1.5).
```
