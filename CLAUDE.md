# CLAUDE.md — NBA Edge

## Overview

Fatigue-based NBA betting edge model with live deployment and backtesting pipeline. Mixed Python/JavaScript.

**Remote:** `old-head-dev/NBA-Edge` — GitHub Pages + nightly GitHub Action.
**Live URL:** `https://old-head-dev.github.io/NBA-Edge/`

## Folder Structure

```
Root (live deployment — served by GitHub Pages):
  index.html, nba_edge_v2.html, results.html, icon.jpg
  data/results.json — nightly results log
  scripts/update_results.py — nightly GitHub Action script

backtest/ — analysis pipeline (local-only, not deployed):
  nba_backtest.js — backtest engine (CLI: --start, --end)
  grade_backtest.py — grading script (CLI: --input, --output, CSV+XLSX)
  analyze_backtest.py — statistical analysis with team quality
  deep_analysis.py, unexplored_analysis.py — cross-season analysis
  data/ — all backtest CSVs, graded results, analysis outputs (gitignored)

tools/ — utilities:
  proxy.py — local proxy for NBA injury report parsing
  nba-injury-links.html — injury report scraper tool
  debug_api.py — Odds API debugging
  check_usage.py — SGO API quota checker

docs/ — reference material:
  NBA Edge Master Plan.pdf, MLB_LESSONS_AUDIT.md
  superpowers/ — specs and plans from model development
```

## Live Deployment

- **GitHub Pages** serves from repo root on `main` branch
- **Nightly Action** (`.github/workflows/nightly.yml`) runs at 12:00 UTC (9am ET)
  - Fetches finalized games via SGO API, grades signals, appends to `data/results.json`
  - Commits and pushes automatically
  - Secrets: `SGO_API_KEY`, `BDL_API_KEY` (configured in GitHub repo settings)

## Backtest Pipeline

```
1. Run backtest:     npm run backtest -- --start YYYY-MM-DD --end YYYY-MM-DD
2. Grade results:    python backtest/grade_backtest.py --input <csv> --output <csv>
3. Analyze:          python backtest/analyze_backtest.py <graded_csv>
```

## APIs

- **BallDontLie** (`BDL_API_KEY`) — Game schedules, scores, history. Free tier, ~5 req/min.
- **The Odds API** (`ODDS_API_KEY`) — Historical and live closing lines. $30/month plan, 20K credits.
- **SportsGameOdds** (`SGO_API_KEY`) — Used by nightly script only for finalized scores/lines.

## Signal Rules (V2.1)

- **SPREAD:** fatigue delta >= 4, home on BTB, spread -1 to -9.5 — bet away ATS
- **SPREAD-FLIP:** fatigue delta >= 4, away on BTB, spread -1 to -6.5 — bet away ATS (market over-correction)
- **UNDER:** both teams >= 5 fatigue, away on road-trip BTB (Scenario A only), total < 234
  - Confidence: +++ (home home-home), ++ (home Scenario C), + (other)

## Gotchas

- **Sleep formula (AUTHORITATIVE):** Live tool (`nba_edge_v2.html`) uses fixed 10am (34.0) wake-up, no plane sleep, no Scenario C +1.5. This is the CORRECT formula. Local backtest (`backtest/nba_backtest.js`) is OUTDATED — uses `tipLocal - 3.0` wake-up with plane sleep stacking. Before re-running any backtests, update local to match the live formula.
- **PowerShell encoding:** NEVER use `>` for Node.js redirect. Use `cmd /c "node script.js > output.csv"`.
- **Live tool uses SGO, not BDL:** The nightly `update_results.py` uses SportsGameOdds API. Can't copy-paste BDL-based code.
- **File safety:** Never modify CSV/data files in-place. Copy first, transform the copy.
- **Browser caching:** GitHub Pages caches aggressively on mobile. Clear Safari cache or use incognito after deploys.
- **Odds API:** Manual refresh only. Each click = 1 API call. Key stored in browser localStorage.

## Git State

- Branch: `main`
- Tags: `v1.0-baseline` (pre-improvement), `v1.0-pre-v2-signals` (pre-V2.1)

## Verify Before Done

- Live tool: open `nba_edge_v2.html` in browser, confirm it loads and calculates
- GitHub Pages: verify live URL works after push
- Nightly Action: check Actions tab — next run should succeed
- Backtest: `npm run backtest -- --start <recent> --end <recent>`, confirm valid output
- Grading: `python backtest/grade_backtest.py --input <csv> --output <csv>`, verify no errors
