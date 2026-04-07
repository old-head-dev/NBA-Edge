# NBA Model + NBA-Edge Consolidation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge NBA Model (local-only) into NBA-Edge (GitHub repo) to eliminate the redundant two-folder structure, with zero downtime to the live tool.

**Architecture:** Copy NBA Model files into new subdirectories (`backtest/`, `tools/`, `docs/`) within NBA-Edge. Live deployment files at repo root stay untouched. Add `.gitignore` to prevent data files from bloating the remote. Rewrite CLAUDE.md as a unified project doc.

**Tech Stack:** Git, bash, file operations. No application code changes.

---

## Task 1: Create Directory Structure and Copy Files

**Files:**
- Create directories: `backtest/`, `backtest/data/`, `tools/`, `docs/`, `docs/superpowers/specs/`, `docs/superpowers/plans/`
- Copy: 5 scripts → `backtest/`
- Copy: 4 tools → `tools/`
- Copy: all data files → `backtest/data/`
- Copy: all docs → `docs/`
- Copy: `HANDOFF.md` → root

Source: `C:\Users\jkher\Documents\Claude\NBA Model\`
Destination: `C:\Users\jkher\Documents\Claude\NBA-Edge\`

- [ ] **Step 1: Create directories**

```bash
cd "C:/Users/jkher/Documents/Claude/NBA-Edge"
mkdir -p backtest/data tools docs/superpowers/specs docs/superpowers/plans
```

- [ ] **Step 2: Copy backtest scripts**

```bash
cd "C:/Users/jkher/Documents/Claude"
cp "NBA Model/nba_backtest.js" NBA-Edge/backtest/
cp "NBA Model/grade_backtest.py" NBA-Edge/backtest/
cp "NBA Model/analyze_backtest.py" NBA-Edge/backtest/
cp "NBA Model/deep_analysis.py" NBA-Edge/backtest/
cp "NBA Model/unexplored_analysis.py" NBA-Edge/backtest/
```

- [ ] **Step 3: Copy tools**

```bash
cd "C:/Users/jkher/Documents/Claude"
cp "NBA Model/proxy.py" NBA-Edge/tools/
cp "NBA Model/debug_api.py" NBA-Edge/tools/
cp "NBA Model/check_usage.py" NBA-Edge/tools/
cp "NBA Model/nba-injury-links.html" NBA-Edge/tools/
```

- [ ] **Step 4: Copy ALL data files (CSVs, xlsx, txt outputs, logs)**

```bash
cd "C:/Users/jkher/Documents/Claude"

# Critical v2 data
cp "NBA Model/NBA_Backtest_24_25_v2.csv" NBA-Edge/backtest/data/
cp "NBA Model/NBA_Backtest_25_26_v2.csv" NBA-Edge/backtest/data/
cp "NBA Model/graded_backtest_24_25_v2.csv" NBA-Edge/backtest/data/
cp "NBA Model/graded_backtest_25_26_v2.csv" NBA-Edge/backtest/data/
cp "NBA Model/graded_backtest_24_25_v2_analysis.txt" NBA-Edge/backtest/data/
cp "NBA Model/graded_backtest_25_26_v2_analysis.txt" NBA-Edge/backtest/data/

# Legacy/historical data
cp "NBA Model/NBA_Backtest_24_25.csv" NBA-Edge/backtest/data/
cp "NBA Model/NBA_Backtest_graded.csv" NBA-Edge/backtest/data/
cp "NBA Model/NBA Backtest - flagged_games.csv" NBA-Edge/backtest/data/
cp "NBA Model/flagged_games.csv" NBA-Edge/backtest/data/
cp "NBA Model/graded_backtest.csv" NBA-Edge/backtest/data/
cp "NBA Model/graded_backtest_24_25.csv" NBA-Edge/backtest/data/
cp "NBA Model/graded_backtest_24_25_analysis.txt" NBA-Edge/backtest/data/
cp "NBA Model/regression_reference.csv" NBA-Edge/backtest/data/

# xlsx files
cp "NBA Model/NBA Backtest - Back-up copy.xlsx" NBA-Edge/backtest/data/
cp "NBA Model/NBA_Backtest.xlsx" NBA-Edge/backtest/data/
cp "NBA Model/NBA_Backtest_24_25.xlsx" NBA-Edge/backtest/data/

# Logs
cp "NBA Model/backtest_24_25_log.txt" NBA-Edge/backtest/data/
cp "NBA Model/backtest_25_26_log.txt" NBA-Edge/backtest/data/
cp "NBA Model/output_log.txt" NBA-Edge/backtest/data/
```

- [ ] **Step 5: Copy docs**

```bash
cd "C:/Users/jkher/Documents/Claude"
cp "NBA Model/NBA Edge Master Plan.pdf" NBA-Edge/docs/
cp "NBA Model/docs/superpowers/specs/2026-03-20-nba-model-improvements-design.md" NBA-Edge/docs/superpowers/specs/
cp "NBA Model/docs/superpowers/specs/2026-03-20-future-improvements-v2.md" NBA-Edge/docs/superpowers/specs/
cp "NBA Model/docs/superpowers/specs/2026-03-21-model-architecture-future-plan.md" NBA-Edge/docs/superpowers/specs/
cp "NBA Model/docs/superpowers/plans/2026-03-20-nba-model-improvements.md" NBA-Edge/docs/superpowers/plans/
```

Note: The consolidation spec and this plan are already in `docs/superpowers/` — they were created there during brainstorming.

- [ ] **Step 6: Copy HANDOFF.md**

```bash
cp "C:/Users/jkher/Documents/Claude/NBA Model/HANDOFF.md" "C:/Users/jkher/Documents/Claude/NBA-Edge/HANDOFF.md"
```

- [ ] **Step 7: Move MLB_LESSONS_AUDIT.md from root to docs/**

```bash
cd "C:/Users/jkher/Documents/Claude/NBA-Edge"
git mv MLB_LESSONS_AUDIT.md docs/MLB_LESSONS_AUDIT.md
```

- [ ] **Step 8: Verify file counts**

```bash
cd "C:/Users/jkher/Documents/Claude/NBA-Edge"
echo "=== backtest scripts ==="
ls backtest/*.js backtest/*.py | wc -l
# Expected: 5

echo "=== tools ==="
ls tools/ | wc -l
# Expected: 4

echo "=== backtest data ==="
ls backtest/data/ | wc -l
# Expected: 21

echo "=== docs ==="
ls docs/ | wc -l
# Expected: 3 (NBA Edge Master Plan.pdf, MLB_LESSONS_AUDIT.md, superpowers/)

echo "=== root check ==="
test -f HANDOFF.md && echo "HANDOFF.md present"
test -f docs/MLB_LESSONS_AUDIT.md && echo "MLB_LESSONS_AUDIT.md in docs/"
```

---

## Task 2: Create .gitignore

NBA-Edge currently has NO .gitignore. Create one that prevents backtest data from being pushed to the remote while keeping live deployment files tracked.

**Files:**
- Create: `C:\Users\jkher\Documents\Claude\NBA-Edge\.gitignore`

- [ ] **Step 1: Create .gitignore**

Write this file at `C:\Users\jkher\Documents\Claude\NBA-Edge\.gitignore`:

```gitignore
# Backtest data (local-only, reproducible from scripts)
backtest/data/

# Work artifacts
*.xlsx
*.bak
*.log

# Editor/IDE
.claude/
.vscode/
node_modules/

# OS
Thumbs.db
Desktop.ini
```

- [ ] **Step 2: Verify gitignore works**

```bash
cd "C:/Users/jkher/Documents/Claude/NBA-Edge"
git status --short backtest/data/
# Expected: NO output (data files should be ignored)

git status --short backtest/nba_backtest.js
# Expected: ?? backtest/nba_backtest.js (script IS visible, not ignored)
```

---

## Task 3: Update package.json

Copy `package.json` and `requirements.txt` from NBA Model, then update script paths to reflect the new `backtest/` location.

**Files:**
- Create: `C:\Users\jkher\Documents\Claude\NBA-Edge\package.json`
- Create: `C:\Users\jkher\Documents\Claude\NBA-Edge\requirements.txt`

- [ ] **Step 1: Write package.json with updated paths**

Write this file at `C:\Users\jkher\Documents\Claude\NBA-Edge\package.json`:

```json
{
  "name": "nba-edge-model",
  "version": "2.0.0",
  "description": "NBA fatigue-based betting edge model — backtest and analysis tools",
  "scripts": {
    "backtest": "node backtest/nba_backtest.js",
    "backtest:24-25": "node backtest/nba_backtest.js --start 2024-11-01 --end 2025-04-13",
    "backtest:25-26": "node backtest/nba_backtest.js --start 2025-11-01 --end 2026-04-13"
  },
  "engines": {
    "node": ">=18.0.0"
  }
}
```

- [ ] **Step 2: Copy requirements.txt**

```bash
cp "C:/Users/jkher/Documents/Claude/NBA Model/requirements.txt" "C:/Users/jkher/Documents/Claude/NBA-Edge/requirements.txt"
```

---

## Task 4: Write Merged CLAUDE.md

Rewrite CLAUDE.md as a single unified project document. Merges context from both the NBA Model and NBA-Edge repos.

**Files:**
- Create: `C:\Users\jkher\Documents\Claude\NBA-Edge\CLAUDE.md`

- [ ] **Step 1: Write the merged CLAUDE.md**

Use the Write tool to create `C:\Users\jkher\Documents\Claude\NBA-Edge\CLAUDE.md` with the content below. Note: this content has inner code fences, so the Write tool (not a code block) must be used.

**CLAUDE.md content — copy exactly:**

The file should contain these sections in order:

**Heading:** `# CLAUDE.md — NBA Edge`

**## Overview**
Fatigue-based NBA betting edge model with live deployment and backtesting pipeline. Mixed Python/JavaScript.
Remote: `old-head-dev/NBA-Edge` — GitHub Pages + nightly GitHub Action.
Live URL: `https://old-head-dev.github.io/NBA-Edge/`

**## Folder Structure** (in a fenced code block):
- Root: live deployment files (index.html, nba_edge_v2.html, results.html, icon.jpg, data/results.json, scripts/update_results.py)
- backtest/: analysis pipeline — nba_backtest.js, grade_backtest.py, analyze_backtest.py, deep_analysis.py, unexplored_analysis.py, data/ (gitignored)
- tools/: proxy.py, nba-injury-links.html, debug_api.py, check_usage.py
- docs/: NBA Edge Master Plan.pdf, MLB_LESSONS_AUDIT.md, superpowers/ (specs + plans)

**## Live Deployment**
- GitHub Pages serves from repo root on `main` branch
- Nightly Action (`.github/workflows/nightly.yml`) runs at 12:00 UTC (9am ET)
- Fetches finalized games via SGO API, grades signals, appends to `data/results.json`
- Commits and pushes automatically
- Secrets: `SGO_API_KEY`, `BDL_API_KEY` (configured in GitHub repo settings)

**## Backtest Pipeline** (in a fenced code block):
1. Run backtest: `npm run backtest -- --start YYYY-MM-DD --end YYYY-MM-DD`
2. Grade results: `python backtest/grade_backtest.py --input <csv> --output <csv>`
3. Analyze: `python backtest/analyze_backtest.py <graded_csv>`

**## APIs**
- BallDontLie (`BDL_API_KEY`) — Game schedules, scores, history. Free tier, ~5 req/min.
- The Odds API (`ODDS_API_KEY`) — Historical and live closing lines. $30/month plan, 20K credits.
- SportsGameOdds (`SGO_API_KEY`) — Used by nightly script only for finalized scores/lines.

**## Signal Rules (V2.1)**
- SPREAD: fatigue delta >= 4, home on BTB, spread -1 to -9.5 → bet away ATS
- SPREAD-FLIP: fatigue delta >= 4, away on BTB, spread -1 to -6.5 → bet away ATS (market over-correction)
- UNDER: both teams >= 5 fatigue, away on road-trip BTB (Scenario A only), total < 234. Confidence: +++ (home home-home), ++ (home Scenario C), + (other)

**## Gotchas**
- **Sleep formula (AUTHORITATIVE):** Live tool (`nba_edge_v2.html`) uses fixed 10am (34.0) wake-up, no plane sleep, no Scenario C +1.5. This is the CORRECT formula. Local backtest (`backtest/nba_backtest.js`) is OUTDATED — uses `tipLocal - 3.0` wake-up with plane sleep stacking. Before re-running any backtests, update local to match the live formula.
- **PowerShell encoding:** NEVER use `>` for Node.js redirect. Use `cmd /c "node script.js > output.csv"`.
- **Live tool uses SGO, not BDL:** The nightly `update_results.py` uses SportsGameOdds API. Can't copy-paste BDL-based code.
- **File safety:** Never modify CSV/data files in-place. Copy first, transform the copy.
- **Browser caching:** GitHub Pages caches aggressively on mobile. Clear Safari cache or use incognito after deploys.
- **Odds API:** Manual refresh only. Each click = 1 API call. Key stored in browser localStorage.

**## Git State**
- Branch: `main`
- Tags: `v1.0-baseline` (pre-improvement), `v1.0-pre-v2-signals` (pre-V2.1)

**## Verify Before Done**
- Live tool: open `nba_edge_v2.html` in browser, confirm it loads and calculates
- GitHub Pages: verify live URL works after push
- Nightly Action: check Actions tab — next run should succeed
- Backtest: `npm run backtest -- --start <recent> --end <recent>`, confirm valid output
- Grading: `python backtest/grade_backtest.py --input <csv> --output <csv>`, verify no errors

---

## Task 5: Commit and Push

Stage all new files, commit with a descriptive message, and push to origin.

**Files:**
- All new/modified files in NBA-Edge repo

- [ ] **Step 1: Review what will be committed**

```bash
cd "C:/Users/jkher/Documents/Claude/NBA-Edge"
git status
```

Expected: New files in `backtest/`, `tools/`, `docs/`, plus `.gitignore`, `package.json`, `requirements.txt`, `CLAUDE.md`, `HANDOFF.md`. NO files from `backtest/data/` (gitignored). `MLB_LESSONS_AUDIT.md` shows as renamed (root → docs/).

- [ ] **Step 2: Stage files**

```bash
cd "C:/Users/jkher/Documents/Claude/NBA-Edge"
git add \
  backtest/nba_backtest.js \
  backtest/grade_backtest.py \
  backtest/analyze_backtest.py \
  backtest/deep_analysis.py \
  backtest/unexplored_analysis.py \
  tools/ \
  docs/ \
  .gitignore \
  package.json \
  requirements.txt \
  CLAUDE.md \
  HANDOFF.md
```

Note: Do NOT `git add backtest/data/` — these are gitignored and should stay local-only.

- [ ] **Step 3: Verify staging**

```bash
cd "C:/Users/jkher/Documents/Claude/NBA-Edge"
git diff --cached --stat
```

Expected: ~20-25 files staged. Zero files from `backtest/data/`.

- [ ] **Step 4: Commit**

```bash
cd "C:/Users/jkher/Documents/Claude/NBA-Edge"
git commit -m "$(cat <<'EOF'
feat: consolidate NBA Model into NBA-Edge repo

Merge local-only NBA Model workspace into this repo:
- backtest/ — backtest engine, grading, analysis scripts
- tools/ — proxy, injury links, API utilities
- docs/ — master plan, MLB lessons audit, specs, plans

Live deployment files unchanged. Backtest data gitignored
(local-only). CLAUDE.md rewritten as unified project doc.
EOF
)"
```

- [ ] **Step 5: Push to origin**

```bash
cd "C:/Users/jkher/Documents/Claude/NBA-Edge"
git push origin main
```

---

## Task 6: Verify Deployment

Confirm the live tool, GitHub Pages, and nightly Action are all unaffected.

- [ ] **Step 1: Verify GitHub Pages serves correctly**

Open `https://old-head-dev.github.io/NBA-Edge/` in a browser (or use curl):

```bash
curl -s -o /dev/null -w "%{http_code}" "https://old-head-dev.github.io/NBA-Edge/"
# Expected: 200

curl -s -o /dev/null -w "%{http_code}" "https://old-head-dev.github.io/NBA-Edge/nba_edge_v2.html"
# Expected: 200

curl -s -o /dev/null -w "%{http_code}" "https://old-head-dev.github.io/NBA-Edge/results.html"
# Expected: 200
```

- [ ] **Step 2: Verify GitHub Actions workflow is intact**

```bash
cd "C:/Users/jkher/Documents/Claude/NBA-Edge"
gh workflow list
# Expected: "Nightly Results Update" workflow listed and active

gh run list --limit 3
# Expected: Recent runs visible, no failures caused by this commit
```

- [ ] **Step 3: Verify local backtest data is preserved**

```bash
cd "C:/Users/jkher/Documents/Claude/NBA-Edge"
ls backtest/data/*.csv | wc -l
# Expected: 10+ CSV files present locally

ls backtest/data/*.xlsx | wc -l
# Expected: 3 xlsx files present locally

git status backtest/data/
# Expected: Nothing — all ignored
```

---

## Task 7: Update Workspace Documentation

Mark the consolidation as completed in the workspace root HANDOFF.md and the cleanup plan.

**Files:**
- Modify: `C:\Users\jkher\Documents\Claude\HANDOFF.md`
- Modify: `C:\Users\jkher\Documents\Claude\docs\superpowers\plans\2026-04-06-workspace-review-cleanup.md`

- [ ] **Step 1: Update workspace HANDOFF.md**

Replace the entire contents of `C:\Users\jkher\Documents\Claude\HANDOFF.md` with a new handoff reflecting this session's work:

```markdown
# Session Handoff — 2026-04-07

## What Was Done

**NBA Model + NBA-Edge Consolidation:**
- Merged NBA Model (local-only analysis workspace) into NBA-Edge (GitHub repo)
- New structure: `backtest/` (5 scripts), `tools/` (4 utilities), `docs/` (specs, plans, master plan)
- Live deployment files untouched at repo root — zero downtime
- Created `.gitignore` to keep backtest data local-only
- Rewrote `CLAUDE.md` as unified project doc
- All 21 historical data files preserved in `backtest/data/` (gitignored)
- Moved `MLB_LESSONS_AUDIT.md` from root to `docs/`

This completes item #1 from the 2026-04-06 workspace review deferred list.

## What's Left

Remaining deferred items from 2026-04-06 workspace review:
1. ~~NBA Model + NBA-Edge consolidation~~ — **DONE**
2. **Create React Native + iOS HIG design skill** — Replace removed SwiftUI skills with one tailored to RN + Expo.
3. **Install/trial dev-browser** — v0.2.6 stable on Windows. Install alongside claude-in-chrome for headless work.
4. **Portfolio-level permissions review** — 21 entries in portfolio settings may need cleanup.

NBA Model folder (`C:\Users\jkher\Documents\Claude\NBA Model\`) can be archived or deleted at user's discretion — all files have been migrated.

## Known Issues

- NBA backtest sleep formula (`backtest/nba_backtest.js`) is still outdated vs live tool. Must update before re-running backtests.
- BytheNumbers shows modified submodule (`01-Empty`) — pre-existing.

## Starter Prompt

```
Continue workspace maintenance. The NBA consolidation is done (see HANDOFF.md). Remaining deferred items:

1. Create a React Native + iOS HIG design skill
2. Install dev-browser alongside claude-in-chrome
3. Portfolio permissions review (21 entries)
```
```

- [ ] **Step 2: Update cleanup plan — mark consolidation as done**

In `C:\Users\jkher\Documents\Claude\docs\superpowers\plans\2026-04-06-workspace-review-cleanup.md`, find the "Deferred Items" section at the bottom and update it:

Find:
```
1. **NBA Model + NBA-Edge consolidation** — Merge into single repo. Requires GitHub Pages migration, Actions update, and pipeline verification. Dedicated session.
```

Replace with:
```
1. ~~**NBA Model + NBA-Edge consolidation**~~ — **COMPLETED 2026-04-07.** See `NBA-Edge/docs/superpowers/specs/2026-04-07-nba-consolidation-design.md` and `NBA-Edge/docs/superpowers/plans/2026-04-07-nba-consolidation.md`.
```

- [ ] **Step 3: Commit workspace doc updates**

```bash
cd "C:/Users/jkher/Documents/Claude"
git add HANDOFF.md "docs/superpowers/plans/2026-04-06-workspace-review-cleanup.md"
git commit -m "$(cat <<'EOF'
docs: mark NBA consolidation as completed in workspace docs

Update HANDOFF.md with consolidation session results.
Mark item #1 as done in the 2026-04-06 cleanup plan.
EOF
)"
```
