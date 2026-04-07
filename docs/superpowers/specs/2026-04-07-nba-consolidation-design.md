# NBA Model + NBA-Edge Consolidation — Design Spec

**Date:** 2026-04-07
**Goal:** Merge NBA Model (local-only analysis workspace) into NBA-Edge (live GitHub repo) to eliminate redundant two-folder structure. Zero downtime — the live tool, GitHub Pages URL, nightly Action, and all secrets must continue working unchanged.

## What Changes

NBA Model files move into the NBA-Edge repo under new subdirectories. Live deployment files stay exactly where they are.

## What Does NOT Change

- `index.html`, `nba_edge_v2.html`, `results.html`, `icon.jpg` — untouched at repo root
- `data/results.json` — untouched
- `scripts/update_results.py` — untouched
- `.github/workflows/nightly.yml` — untouched
- GitHub Pages URL: `old-head-dev.github.io/NBA-Edge/`
- GitHub Actions secrets: `SGO_API_KEY`, `BDL_API_KEY`
- GitHub Pages publish source (deploys from root of `main`)

## Target Folder Structure

```
NBA-Edge/
├── index.html                        # LIVE — GitHub Pages entry
├── nba_edge_v2.html                  # LIVE — betting signals tool
├── results.html                      # LIVE — results dashboard
├── icon.jpg                          # LIVE — favicon/PWA icon
├── data/
│   └── results.json                  # LIVE — nightly results log
├── scripts/
│   └── update_results.py             # LIVE — nightly GitHub Action script
├── .github/
│   └── workflows/
│       └── nightly.yml               # LIVE — 12:00 UTC cron
│
├── backtest/                         # NEW — analysis pipeline
│   ├── nba_backtest.js               # Backtest engine (JS, CLI)
│   ├── grade_backtest.py             # Grading script (Python)
│   ├── analyze_backtest.py           # Statistical analysis
│   ├── deep_analysis.py              # Cross-season analysis
│   ├── unexplored_analysis.py        # Ad-hoc analysis
│   └── data/                         # All backtest CSVs + outputs
│       ├── NBA_Backtest_24_25_v2.csv
│       ├── NBA_Backtest_25_26_v2.csv
│       ├── graded_backtest_24_25_v2.csv
│       ├── graded_backtest_25_26_v2.csv
│       ├── graded_backtest_24_25_v2_analysis.txt
│       ├── graded_backtest_25_26_v2_analysis.txt
│       ├── backtest_24_25_log.txt
│       ├── backtest_25_26_log.txt
│       ├── regression_reference.csv
│       ├── NBA_Backtest_24_25.csv          # legacy v1
│       ├── NBA_Backtest_graded.csv         # legacy v1
│       ├── NBA_Backtest - flagged_games.csv
│       ├── graded_backtest.csv             # legacy pre-v2
│       ├── graded_backtest_24_25.csv       # legacy pre-v2
│       └── NBA Backtest - Back-up copy.xlsx
│
├── tools/                            # NEW — utilities
│   ├── proxy.py                      # Local proxy for injury reports
│   ├── nba-injury-links.html        # Injury report scraper tool
│   ├── debug_api.py                  # Odds API debugging
│   └── check_usage.py               # SGO API quota checker
│
├── docs/                             # NEW — reference material
│   ├── NBA Edge Master Plan.pdf      # Original planning document
│   ├── MLB_LESSONS_AUDIT.md          # Moved from repo root
│   └── superpowers/                  # Specs + plans from NBA Model
│       ├── specs/
│       │   ├── 2026-03-20-nba-model-improvements-design.md
│       │   ├── 2026-03-20-future-improvements-v2.md
│       │   └── 2026-03-21-model-architecture-future-plan.md
│       └── plans/
│           └── 2026-03-20-nba-model-improvements.md
│
├── package.json                      # NEW — npm scripts for backtest
├── requirements.txt                  # NEW — Python deps
├── .gitignore                        # UPDATED — add backtest data patterns
├── CLAUDE.md                         # REWRITTEN — merged context from both repos
└── HANDOFF.md                        # From NBA Model (session history)
```

## Files NOT Migrated

These stay in the NBA Model folder (local only, not worth migrating):

- `V1 Github Files/` — already deleted in workspace review
- `.claude/` directory — workspace-specific settings, not transferable
- `icon.jpg` — duplicate of NBA-Edge's copy

## .gitignore Updates

Add patterns to prevent backtest data from bloating the remote repo:

```gitignore
# Backtest data (local-only, too large for git)
backtest/data/
*.xlsx
```

The backtest CSVs and analysis outputs exist locally but won't be pushed to GitHub.

## CLAUDE.md Merge Strategy

Rewrite as a single unified project doc. Key sections:

1. **Project Overview** — one project, fatigue-based NBA betting model
2. **Folder Structure** — live deployment (root), analysis pipeline (backtest/), utilities (tools/)
3. **Live Deployment** — GitHub Pages + nightly Action details
4. **Backtest Pipeline** — how to run backtest → grade → analyze
5. **APIs** — BDL, Odds API, SGO with key locations
6. **Gotchas** — sleep formula (authoritative = live tool), plus existing gotchas from both repos
7. **Verify Before Done** — consolidated checklist

Remove the "two-folder" documentation since it's now one folder.

## package.json Updates

Update script paths to reflect new `backtest/` location:

```json
{
  "scripts": {
    "backtest": "node backtest/nba_backtest.js",
    "backtest:24-25": "node backtest/nba_backtest.js --start 2024-11-01 --end 2025-04-13",
    "backtest:25-26": "node backtest/nba_backtest.js --start 2025-11-01 --end 2026-04-13"
  }
}
```

## Migration Steps (High Level)

1. Copy files from NBA Model into NBA-Edge with new folder structure
2. Update `.gitignore` with backtest data patterns
3. Update `package.json` script paths
4. Move `MLB_LESSONS_AUDIT.md` from root to `docs/`
5. Rewrite `CLAUDE.md` as merged doc
6. Commit and push to `old-head-dev/NBA-Edge`
7. Verify: GitHub Pages still works, nightly Action still runs, all files present locally
8. Update workspace HANDOFF.md and cleanup plan to mark this work as completed
9. After verification: NBA Model folder can be archived or deleted at user's discretion

## Risks

- **LOW:** GitHub Pages serves from repo root — new subdirectories (`backtest/`, `tools/`, `docs/`) won't interfere since Pages serves any static file at root
- **LOW:** Nightly Action references `scripts/update_results.py` and `data/results.json` by path — both unchanged
- **NONE:** No code logic changes. All scripts work the same, just from new paths.
