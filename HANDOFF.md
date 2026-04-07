# Session Handoff — 2026-04-07 (V3 Audit & Rebuild)

## What Was Done

### V2 Audit (confirmed model is overfit)
- Ran formal audit per `docs/MLB_LESSONS_AUDIT.md` methodology
- Cross-season analysis: FLIP signal reversed between seasons (43.4% → 61.7% = noise)
- In-sample mining confirmed by user: thresholds mined from backtest data, both seasons combined
- Live results: 6-13 (31%) — model does not work
- `backtest/audit_analysis.py` — standalone V2 audit script (untracked, can delete)

### V3 Phase 1 — Analysis Pipeline (COMPLETE)
- `4a3ff4b` Design spec: `docs/superpowers/specs/2026-04-07-v3-fresh-start-design.md`
- `2025021` Arena module: coordinates, Haversine, team normalization (25 tests)
- `96aa6aa` Data loader: Kaggle CSV + SBR JSON with ATS/OU computation (39 tests)
- `3ab3f49` Data validation: spot-checks, cross-reference, quality reports
- `61f955c` Schedule context engine: B2B, travel, distance, sleep, density, altitude, win% (49 tests)
- `0e180b3` Signal analysis engine: Wilson CI, 12 signal conditions, audit report (70 tests)
- `a7bb895` Validation engine: leave-one-season-out CV, monotonicity checks
- `eca2bb0` Pipeline orchestrator
- `2441c5b` First full pipeline run on 6,150 games (5 seasons)
- Additional analysis: loaded 2025-26 from MGM Kaggle dataset (808 games), ran LOSO across all 6 seasons

**183 tests passing.** Full pipeline at `backtest/v3/`, data at `backtest/v3/data/` (gitignored).

### V3 Signal Findings
- **S2 (Home B2B + traveled → Bet Away ATS):** 4/6 LOSO folds pass, 3/3 recent, combined 56.8% [50.8-62.6%]. Only signal that never reverses direction.
- **B2 (Both B2B + both traveled → Home ATS):** 4/6 folds pass, but per-fold Ns of 18-31. Monitoring only.
- **S4 (Away B2B):** Perfect 50/50 across 6 seasons — market prices away fatigue correctly.
- **All totals signals:** Dead. No O/U edge for any fatigue condition.
- **V2 signals (SPREAD, FLIP, UNDER):** All killed.

### V3 Live Tool Plan (WRITTEN, NOT YET IMPLEMENTED)
- `ae6fc90` Deployment plan: `docs/superpowers/plans/2026-04-07-v3-live-tool-deployment.md`
- 6 tasks: rebuild live HTML tool, update nightly grading, results dashboard, GitHub Action
- Reviewed by code-reviewer agent — critical fixes applied

## What's Left

1. **Implement V3 live tool deployment plan** — the 6-task plan at `docs/superpowers/plans/2026-04-07-v3-live-tool-deployment.md`. This is the next session's work.
2. **Generate formal validation report** — run `python -m v3.validate_signals` to save LOSO results to file (was run interactively but not saved).
3. **Push to remote** — 14 commits ahead of origin. Push after implementation or before if you want to checkpoint.
4. **Phase 2 investigation (future)** — tip time data from BDL API could test whether late tips amplify S2 edge. Distance buckets showed 500-750mi peak (61.7%) but N=75. Worth revisiting with more data.
5. **B2 monitoring** — accumulate 2-3 more seasons before promoting to primary signal.

## Known Issues

- `backtest/audit_analysis.py` is untracked — V2 audit script, can be deleted or committed for reference.
- 14 commits ahead of origin — not yet pushed.
- 2025-26 MGM data covers through ASB (Feb 12, 2026) only — remaining 2025-26 games (Feb-Apr) not in dataset.
- Kaggle dataset has NO tip times (all default to 7:30pm ET) — limits sleep estimation usefulness.
- Free datasets use different team naming conventions: Kaggle=lowercase abbrevs (`gs`, `sa`), SBR=full names (`Warriors`, `Celtics`), MGM=city/nickname (`Golden State`, `LA Lakers`). All normalized by the loader.

## Starter Prompt

```
Read HANDOFF.md in the NBA-Edge project. This continues the V3 rebuild of the NBA Edge fatigue betting model. The V3 analysis pipeline is complete (183 tests, 6 seasons analyzed). One signal survived validation: S2 (home team on B2B + traveled → bet away ATS, 57% across 6 seasons). The next step is implementing the V3 live tool deployment plan at docs/superpowers/plans/2026-04-07-v3-live-tool-deployment.md — 6 tasks: rebuild the HTML live tool around S2, update nightly grading script, results dashboard, and GitHub Action. The plan has been reviewed by a code-reviewer agent with critical fixes applied. Use subagent-driven development to execute.
```
