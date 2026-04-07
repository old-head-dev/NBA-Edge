# NBA Edge V3 — Fresh Start Design Spec

**Date:** 2026-04-07
**Status:** Approved by user, pending implementation plan
**Context:** V2 audit revealed in-sample mining, arbitrary fatigue scoring, and cross-season instability. V3 is a complete rebuild — not an iteration on V2.

---

## Background: Why V3 Exists

### V2 Audit Results (2026-04-07)

The NBA Edge model went live in March 2026 with three signals (SPREAD, SPREAD-FLIP, UNDER). Live performance through April 5:

| Signal | Backtest | Live | Verdict |
|--------|----------|------|---------|
| SPREAD | ~57% | 5-5 (50%) | No edge |
| FLIP | 61.7% | 1-5 (17%) | Catastrophic — one-season artifact |
| UNDER | 62-66% | 0-3 (0%) | Too small to conclude but not encouraging |
| **Combined** | **~66%** | **6-13 (31%)** | **Model does not work** |

### Root Causes Identified

1. **In-sample mining.** Signal thresholds (delta >= 4, spread -1 to -9.5, total < 234) were selected because they had the best win rates in the backtest data. Both seasons were combined — no out-of-sample validation was ever performed.

2. **Arbitrary fatigue scoring.** The fatigue "model" assigned made-up weights: Scenario A = +5, timezone = +0.5/hr, sleep < 4hrs = +4, etc. These weights were judgment calls, never empirically validated. A team scoring "7" vs "4" was pseudo-precision — arbitrary numbers producing arbitrary differences.

3. **Cross-season instability.** The FLIP signal reversed between seasons (43.4% in 24-25, 61.7% in 25-26). When combined, it averaged to 51.1% — pure noise. The deployed spread gate cherry-picked the subset that looked good in each season through different mechanisms.

4. **Pre-assumed bet directions.** V2 assumed "home fatigued → bet away" without testing whether the market over-adjusts or under-adjusts. The FLIP signal was born from this confusion — "the logical side was losing, so flip it" — rather than letting data determine direction.

### MLB Parallel

An MLB model project went through 20+ sessions building 5 betting models. All showed 60-75% backtest win rates. All lost money live. The root cause was identical: testing "does this feature predict outcomes?" instead of "does this feature beat the market's implied probability?" Features that predict outcomes may already be priced in.

---

## V3 Design Philosophy

### Three Rules

1. **No composite scores.** No combining travel + sleep + timezone into a single number with made-up weights. Each factor is tested independently first. Only combine factors if there's evidence each contributes independently — and then with empirically derived weights, not guesses.

2. **Out-of-sample or it doesn't count.** Every signal must be validated on data it was NOT designed on. Define rules on seasons 1 through N, test UNCHANGED on season N+1. If we tweak after seeing results, we restart validation.

3. **Broad before narrow.** Test the broadest version of each signal first (e.g., "home on B2B"). Only add filters (spread ranges, distance thresholds) if the broad version already shows edge AND the filter improves it in both train and test sets.

### Core Principle: Observe First, Theorize Second

For every schedule condition, measure:
- **ATS split:** Home covers X%, Away covers Y%
- **O/U split:** Over X%, Under Y%
- **Per season individually**, not combined
- **With Wilson confidence intervals**, not just point estimates

No pre-assumed bet directions. No pre-assumed markets. The data tells us what's real.

### What "Edge" Means

At standard -110 juice, break-even is 52.38%. A real edge means:
- Consistent above 52.38% in at least 60% of individual seasons (minimum 3 seasons total)
- Never catastrophically below 48% in any single season
- 95% confidence interval lower bound > 50% (or within 1pp of 50% with consistent direction across all seasons)
- Survives out-of-sample validation (leave-one-season-out)

**Push handling:** Pushes are excluded from win/loss denominator (standard practice). A 5W-3L-2P record is 5/8 = 62.5%, not 5/10.

Professional NBA bettors target 53-55%. A 55% ATS rate at -110 is a genuine, valuable finding. V2's mistake was expecting 60%+ — those rates only exist through in-sample mining.

---

## Definitions

- **B2B (back-to-back):** Team played 0 calendar days ago (yesterday). Simple binary — no complex scenario classification.
- **Traveled:** Team's previous game was at a different arena than tonight's game (i.e., they had to travel to reach tonight's venue). For home teams, "traveled" means they played away in their previous game and flew home. For away teams, "traveled" means their previous game was at a different away arena (or at home).
- **Travel distance:** Haversine distance between previous game arena and tonight's game arena. Already computed in codebase via arena coordinates.
- **Long travel:** Distance > 1000 miles (boundary inclusive — 1000mi counts as long travel).
- **Schedule density:** "3-in-4" = team's 3rd game in 4 calendar days. "4-in-6" = team's 4th game in 6 calendar days.
- **Altitude:** Game at DEN or UTA arena, and visiting team has not played at DEN/UTA in the past 4 days.
- **ATS split:** For a set of games, the percentage where home covered vs away covered (pushes excluded from denominator).
- **O/U split:** For a set of games, the percentage that went over vs under (pushes excluded from denominator).
- **Win%:** Team's win percentage at the time of the game (cumulative season record through previous game), used for tanking filter.

---

## Signals to Test

### Schedule Conditions

Every condition is tested in BOTH ATS directions AND both O/U directions. No pre-assumed bets.

**One-Sided Fatigue:**

| ID | Condition | Measurements |
|----|-----------|-------------|
| S1 | Home on B2B, away NOT on B2B | ATS split + O/U split |
| S2 | Home on B2B + traveled, away NOT on B2B | ATS split + O/U split |
| S3 | Home on B2B + long travel (>1000mi), away NOT on B2B | ATS split + O/U split |
| S4 | Away on B2B, home NOT on B2B | ATS split + O/U split |
| S5 | Away on B2B + traveled, home NOT on B2B | ATS split + O/U split |
| S6 | Away on B2B + long travel (>1000mi), home NOT on B2B | ATS split + O/U split |

Note: One-sided signals explicitly exclude games where both teams are on B2B. Those games are captured in B1-B3.

**Both-Fatigued:**

Note: The away (road) team always traveled to the game venue. So "at least one traveled" is always true — the meaningful distinction is whether the HOME team also traveled (played away yesterday and flew back).

| ID | Condition | Measurements |
|----|-----------|-------------|
| B1 | Both on B2B, only road team traveled (home had home-home B2B) | ATS split + O/U split |
| B2 | Both on B2B, both teams traveled (home also played away yesterday) | ATS split + O/U split |

**Schedule Density:**

| ID | Condition | Measurements |
|----|-----------|-------------|
| D1 | Home on 3-in-4 or 4-in-6 | ATS split + O/U split |
| D2 | Away on 3-in-4 or 4-in-6 | ATS split + O/U split |

**Altitude (Exploratory):**

| ID | Condition | Measurements |
|----|-----------|-------------|
| A1 | Visitor at DEN/UTA on B2B with travel | ATS split + O/U split |

**Control (Baseline):**

| ID | Condition | Measurements |
|----|-----------|-------------|
| C1 | Neither team on B2B | ATS split + O/U split (baseline that all signals must beat) |

### Sleep Estimation Layer

For every B2B game with travel, compute **estimated sleep hours** as a continuous variable based on physics/logistics:

- Game ends = tip time + ~2.5 hrs (game duration)
- Post-game departure = game end + ~2.5 hrs (showers, media, bus to airport)
- Flight time = distance / 500 mph
- Hotel arrival = landing + ~45 min (tarmac, transport to hotel)
- Wake-up ≈ 10am local time (next day)
- Estimated sleep = max(0, wake-up - arrival)

For B2B without travel (home-home): sleep = max(0, 10am - (tip time + 5.0 hrs))

When tip time is unavailable (some older BDL seasons): default to 7:30pm ET (19:30). Flag these games so sleep-layer analysis can optionally exclude them.

This is NOT converted to a fatigue score. It stays as a continuous number. If Phase 1 shows sleep does NOT outperform distance as a predictor, the sleep formula is killed entirely — not kept as dead code.

Test signals at three granularity levels to determine if sleep estimation adds value:

| Layer | Granularity | Example |
|-------|------------|---------|
| Binary | B2B yes/no, traveled yes/no | Broadest, hardest to overfit |
| Distance | <500mi, 500-1500mi, >1500mi | Simple proxy for sleep impact |
| Estimated sleep | <4hrs, 4-6hrs, 6+hrs | Most granular, tests if sleep adds value over distance |

If estimated sleep hours correlates more strongly with ATS/OU outcomes than distance alone, it earns its place in the Phase 2 regression model. If distance alone performs equally well, sleep estimation is unnecessary complexity.

### Tanking Filter

Teams actively tanking (resting starters, playing developmental lineups) create noise that can inflate or mask real signals. Tanking is primarily a post-All-Star-break phenomenon — teams make their playoff push/tank decision around the trade deadline.

**Approach:** Segment analysis by season phase, apply tanking filter only post-ASB.

1. Run every signal analysis for three season segments:
   - Full season (all games)
   - Pre-All-Star break only
   - Post-All-Star break only

2. For post-ASB segment, also run with tanking teams excluded:
   - Test at multiple win% thresholds: .250, .300, .350 (win% at ASB)
   - Compare whether signal rates change meaningfully with/without tanking teams

3. In the live tool: tanking filter only activates after the All-Star break each season. Before ASB, all teams are treated equally. After ASB, teams below the validated win% threshold are flagged.

---

## Data Pipeline

### Stage 1: Data Collection

**Requirement: Every regular season game, not just pre-filtered "fatigued" games.**

For each season (target: 18 seasons, 2007-2025):

1. **Load game data and closing lines from free datasets**
   - Primary source: Kaggle "NBA Betting Data" CSV (2007-2025) — contains dates, teams, scores, closing spreads, closing totals, moneylines
   - Supplement: GitHub sportsbookreview-scraper JSON (2011-2022) — has both opening AND closing lines for cross-reference and CLV analysis
   - Recent supplement: Kaggle MGM Grand dataset (2021-2026) — confirmed BetMGM closing lines + public betting percentages
   - BDL API used only for tip times (needed for sleep estimation) and to fill any gaps in game data. Cache all BDL responses locally.
   - ~1,230 games per season (82 games × 30 teams / 2)

2. **Validate data quality before building on it**
   - Spot-check at least 10 games per season against known results (ESPN, basketball-reference)
   - Verify: final scores match, closing spreads are plausible, team names are consistent
   - Cross-reference Kaggle vs GitHub datasets for overlapping seasons (2011-2022) — flag discrepancies
   - Log any games with missing or suspicious line data

3. **Compute schedule context for each team in each game:**
   - Days rest since previous game
   - B2B flag (0 days rest)
   - Traveled flag (different arena than previous game)
   - Travel distance (Haversine from arena coordinates — already in codebase)
   - Estimated sleep hours (for B2B games with travel)
   - Timezone change (eastbound/westbound, hours)
   - Schedule density: 3-in-4 flag, 4-in-6 flag
   - Altitude flag: playing at DEN/UTA without game there in past 4 days
   - Current season win% at game time (for tanking filter, post-ASB only)

4. **Output:** `full_season_YYYY_YY.csv` — every game with all schedule tags, lines, and results

**CSV Schema:**
```
date, away, home, away_score, home_score,
home_spread, close_total,
away_days_rest, home_days_rest,
away_b2b, home_b2b,
away_traveled, home_traveled,
away_travel_dist, home_travel_dist,
away_est_sleep, home_est_sleep,
away_tz_change, home_tz_change,
away_3in4, home_3in4, away_4in6, home_4in6,
away_at_altitude, home_is_altitude,
away_win_pct, home_win_pct,
ats_result, ou_result
```

### Stage 2: Signal Analysis

For each condition in the signal matrix:
1. Filter games matching the condition
2. Compute ATS split: home covers %, away covers %, push %
3. Compute O/U split: over %, under %, push %
4. Break down per-season
5. Wilson 95% confidence intervals on everything
6. Flag signals where one side exceeds 52.38% consistently

**Output:** `signal_audit_report.txt` — complete numerical results, no editorial

### Stage 3: Validation

For signals that pass Stage 2 (consistent direction above 52.38% in majority of seasons):

1. **Leave-one-season-out cross-validation:**
   - For each season S: define signal direction from all OTHER seasons, test on S
   - Record whether direction holds and the win rate on the held-out season

2. **Monotonicity check:**
   - For continuous variables (distance, sleep), does more fatigue consistently predict better outcomes in the identified direction?
   - Operationalized: Spearman rank correlation > 0.6 across buckets, no single bucket reversing by more than 5 percentage points from the overall trend

3. **CLV tracking (live deployment only):**
   - The Odds API historical endpoint provides closing line snapshots only — not opening lines. Therefore CLV analysis is NOT possible on historical backtest data.
   - Once signals are deployed live, track opening line at signal identification time vs closing line at game time. This measures whether value remains by the time we bet.
   - CLV is a Phase 2+ metric for live monitoring, not a Phase 1 validation gate.

**Output:** `validation_report.txt` — out-of-sample results, monotonicity analysis

---

## Phased Implementation

### Phase 1: Simple Rules (Approach A)

Build the data pipeline. Collect maximum seasons. Run the full signal matrix using binary and distance-bucketed conditions. Identify which conditions (if any) show consistent above-break-even performance in a specific direction.

**Success criteria:** At least one signal above 53% in the majority of individual seasons with 95% CI excluding (or nearly excluding) 50%.

**If Phase 1 fails:** No signals pass validation. The fatigue thesis doesn't beat the market. Pause the model rather than mining for new thresholds. Consider pivoting to the lineup/injury intelligence approach (future Phase 3).

### Phase 2: Empirical Model (Approach B)

Only proceed if Phase 1 identifies real signals.

Build a logistic regression using individual fatigue components as features:
- Travel distance (continuous)
- Estimated sleep hours (continuous, if Phase 1 showed it adds value)
- Days rest (continuous)
- Timezone change (continuous)
- Schedule density flags
- Altitude flag
- Opponent rest differential
- Season win% (tanking proxy)

Target: ATS outcome. Proper leave-one-season-out cross-validation. Regularization to prevent overfitting.

The model outputs a probability, not a fatigue score. Compare model probability to market implied probability (from the spread). Only signal when the gap exceeds a threshold.

### Phase 3: Lineup/Injury Intelligence (Future)

Separate from the fatigue model. Exploits information timing — late injury reports, rest decisions, lineup changes that haven't been priced into lines yet. Different thesis, different signal type, additive to Phases 1-2.

Not in scope for this spec.

---

## What V3 Kills From V2

| V2 Component | Status | Reason |
|--------------|--------|--------|
| Fatigue score formula | Killed | Arbitrary weights, never validated |
| Scenario A/B/C classification | Killed | Replaced by simple: traveled yes/no, distance |
| Sleep → score conversion | Killed | Arbitrary step function (+4/+2/+1/+0) |
| FLIP signal | Killed | One-season artifact, combined = 51.1% (noise) |
| Delta >= 4 threshold | Killed | Mined from backtest data |
| Spread gate (-1 to -9.5) | Killed | Mined from backtest data |
| Total gate (< 234) | Killed | Mined from backtest data |
| Pre-computed analysis files | Killed | Generated with buggy code, in-sample conclusions |
| Hardcoded TANK_WATCH list | Killed | Replaced by dynamic win% cutoff |

## What V3 Keeps From V2

| V2 Component | Status | Reason |
|--------------|--------|--------|
| Arena coordinates + Haversine distance | Kept | Math, not opinion |
| BDL API integration | Kept | Game data source (needs expansion for all games) |
| Odds API integration | Kept | Closing line source (needs historical expansion) |
| GitHub Pages deployment | Kept | Infrastructure works |
| Nightly grading pipeline | Updated | For V3 signals once validated |
| Sleep estimation formula | Kept as continuous variable | Physics-based, tested for value-add |
| Results dashboard | Updated | For V3 signals once validated |

---

## Data Sources

### Historical Closing Lines (FREE — No Odds API Needed)

Research identified free datasets that cover 17+ seasons of NBA closing lines, eliminating the need for Odds API credits for historical data:

**Primary: Kaggle "NBA Betting Data" (cviaxmiwnptr)**
- Coverage: 2007-08 through 2024-25 (17+ seasons, actively maintained)
- Data: closing spreads, totals, moneylines, quarter scores, final scores
- Source: SBRO closing lines (2007-2023) + ESPN (2023+)
- Format: CSV, free download
- Caveat: moneylines missing from ESPN portion (Jan 2023+); needs quality validation

**Supplement: GitHub sportsbookreview-scraper (pre-scraped archive)**
- Coverage: 2011-12 through 2021-22 (11 seasons, 13,903 records)
- Data: BOTH opening AND closing spreads/totals + moneylines
- Format: JSON
- Value: cross-reference Kaggle data quality; opening lines enable CLV analysis on historical data
- **Security: Download ONLY the data file (`data/nba_archive_10Y.json`). Do NOT clone the repo, install its dependencies, or run its Python scraper code (`cli.py`). We need the pre-scraped data, not the scraper tool.**

**Recent: Kaggle MGM Grand Dataset**
- Coverage: 2021-22 through 2025-26 (through Feb 2026 ASB)
- Data: confirmed BetMGM closing lines + public betting percentages
- Value: fills the most recent seasons with explicit closing-line labels

**Combined coverage: 2007-2025 (~22,000+ regular season games across 18 seasons).** This dramatically exceeds the 3-5 seasons we originally planned for, making validation much more powerful.

### APIs (Live/Current Season Only)

- **BallDontLie (BDL):** Tip times and gap-fill for game data not in the free datasets. Free tier, ~5 req/min. Cache all responses locally, re-fetch only on miss.
- **The Odds API:** Retained ONLY for live/current season closing lines (nightly grading). NOT used for historical backtest — free datasets cover that. $30/month plan sufficient for live use. Credits preserved for MLB model.
- **SportsGameOdds (SGO):** Used by nightly script for live grading. Stays as-is.

### Data Strategy

1. **Historical (one-time, free):** Download Kaggle CSV + GitHub JSON data file. Merge and cross-reference for quality. Supplement with BDL for tip times only. Validate via spot-checks against known results. Zero recurring API cost.
2. **Current season (ongoing):** Odds API or SGO for closing lines (nightly grading). BDL for tip times if needed. Existing $30/month plan covers this.
3. **Missing line data:** Games without closing line data from any source are excluded from ATS/O/U analysis but included in schedule context (so downstream B2B/rest calculations remain correct).
4. **Data integrity:** All downloaded datasets are plain data files (CSV, JSON) loaded with standard Python parsers (pandas, json module). No third-party code is executed. Spot-check validation is mandatory before any analysis runs on the data.

### Implementation Language

V3 data pipeline and analysis in **Python** (pandas, scipy for Wilson intervals, statsmodels for Phase 2 regression). The V2 backtest was Node.js — V3 is a complete rebuild, and Python is the natural choice for data analysis. The live tool remains browser JavaScript (GitHub Pages).

### Game Filtering

- **Include:** Regular season games only
- **Exclude:** Preseason, play-in tournament, playoffs, All-Star game
- **Method:** Use BDL API `postseason=false` filter, plus exclude games before late October and after mid-April (safety net for edge cases)

---

## Success Metrics

| Metric | What It Means | Target |
|--------|---------------|--------|
| Cross-season consistency | Signal above 52.38% in at least 60% of individual seasons (min 3 seasons) | Required |
| Out-of-sample win rate | Win rate on held-out season (leave-one-out) | > 52.38% |
| Confidence interval | 95% Wilson CI | Lower bound > 50%, or within 1pp of 50% with consistent direction |
| Monotonicity | More fatigue → stronger signal for continuous vars | Spearman ρ > 0.6, no bucket reversal > 5pp |
| CLV | Signal has value vs closing line | Positive avg CLV (live deployment only, not historical) |
| Sample size per season | Enough games to be meaningful | N >= 30 for broadest version of each signal |

---

## Anti-Patterns to Avoid

These are the mistakes that killed V2 and the MLB models. Explicit rules to prevent recurrence.

1. **No threshold mining.** Do not test delta >= 2, 3, 4, 5, 6 and pick the best. Either use a theory-driven threshold or test continuous.

2. **No combined-season-only analysis.** Every number must be reported per-season. Combined stats mask reversals (see: FLIP at 51.1% combined hiding 43.4% / 61.7% split).

3. **No cherry-picked subsets.** Do not report "home B2B with spread -2 to -5 in January against non-tanking teams" as a signal. Each filter must independently justify itself.

4. **No claiming validation on training data.** "66% combined across both seasons" is not validation when rules were designed on that data.

5. **No premature deployment.** Signals go live only after passing out-of-sample validation. Not before.

6. **No arbitrary scoring.** If a weight can't be derived from data or physics, it doesn't belong in the model.

7. **Accept thin edges.** 54% at -110 is a real finding worth deploying. Don't chase 65% — that only exists through overfitting.

8. **No iterating on held-out data.** If validation shows 51% on the held-out season, do NOT tweak a threshold "just slightly" and re-test. That is training on the test set. If a signal fails validation, it fails. Go back to the hypothesis, not the threshold.
