# NBA Edge Model — Audit Required (Lessons from MLB)

**Date:** 2026-04-05  
**Context:** The MLB Model project (5 betting models) went through 20+ sessions of development. Session 19 discovered a fundamental methodology flaw that invalidated most of the work. This document explains what went wrong, how it applies to the NBA model, and exactly what needs to be investigated.

## The MLB Lesson (Read This First)

### What happened
Over 20 sessions, agents built 5 MLB betting models. Each model used backtests showing 60-75% win rates. Scenario mining found patterns (flag combinations) that appeared profitable. The models went live and LOST money across the board:
- K Props: 10-18 (35.7%) — the backtest showed 65%
- NRFI: 7-12 (36.8%) — the backtest showed 64%
- HR Props: 1-9 (10%) — investigation showed zero edge vs market
- Totals: 0-1 (barely fired)

### The root cause
Every session SAID "we're looking for edge against the market" but TESTED "does this feature predict the outcome." These are different questions:

**The test every session ran:**
> When our scenario fires, does the over/under hit more than 52.38% of the time?

**The test nobody ran until session 19:**
> When our scenario fires, does the outcome beat THE MARKET'S IMPLIED PROBABILITY for those specific games?

Example: The K Props model found "elite whiff + K-prone lineup → over hits 65%." Sounds great. But the market ALREADY sets the K line higher for elite whiff pitchers. The market implied probability for those games was ~63%. The real edge was 2%, not 13%. And once in-sample mining inflation was removed, even that 2% disappeared.

**The one-sentence lesson:** A feature that predicts the outcome is NOT the same as a feature the market underprices. The market already knows about most public features (whiff rate, barrel rate, fatigue, etc.). The only edge comes from information the market is SLOW to price or STRUCTURALLY misprices.

## How This Applies to the NBA Model

### Why the NBA model might be DIFFERENT from MLB

Before assuming the NBA model is broken, note some structural advantages:

1. **Fatigue is a game-day condition, not a season-long stat.** Unlike MLB's whiff rate or barrel rate (known all season, easily priced), NBA fatigue changes daily based on specific travel + B2B + time zone combos. The market may be slower to fully price a specific 3-games-in-4-nights West-to-East B2B than it is to price a pitcher's K rate.

2. **Two seasons of backtest data exist** (24-25 and 25-26). Most MLB models only had one season for key signals. If the SAME signal rules produce similar rates across both seasons WITHOUT threshold tweaking, that's genuine cross-validation — stronger evidence than anything K Props had.

3. **NBA juice is standard -110 both sides.** Unlike MLB where juiced lines (-150, -170) hide edge erosion, NBA spread/total bets are straightforward. Break-even is 52.38%. The question is purely: does the spread/total already reflect the fatigue, or does our model catch games where the adjustment is insufficient?

4. **The SPREAD-FLIP thesis is structurally grounded.** "The market over-adjusts for away fatigue" is a specific, testable market behavior claim — similar to MLB's F5/full-game ratio mispricing, which WAS validated.

**Don't go in assuming it's broken. Go in asking the question honestly. It might survive the audit.**

### What the NBA model does (current state)
- Computes fatigue scores based on travel, back-to-backs, sleep deprivation, schedule density
- Fires 3 signal types: SPREAD (bet away when home is fatigued), SPREAD-FLIP (bet away when away is MORE fatigued — counterintuitive market over-correction), UNDER (bet under when both are fatigued)
- Backtest win rates: SPREAD-FLIP 61.7% (N=115), AWAY EDGE 52.8% (N=72), UNDER 62.5% (N=32)

### What needs investigation

#### 1. Does the fatigue model beat the market — with NBA's simpler pricing?

Unlike MLB where variable juice (-130, -170) hides whether you're really beating the market, NBA is standard -110 both sides. So the 52.38% break-even IS the market benchmark for most games. This simplifies the analysis compared to MLB.

However, the spread ITSELF may already incorporate fatigue. When a team is on a back-to-back, books adjust the spread (e.g., from -7 to -3). The question is whether our fatigue score identifies situations where the book's spread adjustment is INSUFFICIENT — not whether fatigue exists, but whether the spread FULLY accounts for it.

**Test to run:** For the same team, compare their spread on fatigued vs non-fatigued days. If the spread already moves 3-4 points on B2B games, the market is pricing fatigue. Our edge (if any) is in the RESIDUAL — the cases where the market's 3-4 point adjustment wasn't enough.

The good news: if our ATS win rates are genuinely 60%+ at standard -110, that IS beating the market. Unlike MLB where 65% against -150 juice is only 2% edge, NBA's 60% at -110 is a clear 8% edge. The simpler pricing makes the audit more straightforward.

#### 2. Are the backtest win rates in-sample?

The signal rules (delta >= 4, spread -1 to -9.5, away Scenario A for under, etc.) — were these thresholds MINED from the same data they were tested on?

If the analysis tried delta >= 2, 3, 4, 5, 6, 7, 8 and picked the threshold where the WR looked best — that's in-sample optimization. The spread bucket analysis (line 42-47 in the backtest output) shows exactly this pattern: testing multiple spread ranges and reporting the best.

**Test to run:** Were the signal rules defined BEFORE looking at the 25-26 data? Or were they selected because they had the best WR? If the latter, the rates are inflated.

**Cross-season check:** The 24-25 backtest exists. Were the signal rules from 24-25 applied unchanged to 25-26? If yes, and the rates hold, that's genuine cross-validation. If the rules were tweaked between seasons, the 25-26 rates are semi-in-sample.

#### 3. Sample sizes are dangerously small

| Signal | N | Concern |
|--------|---|---------|
| SPREAD-FLIP (home edge flipped) | 115 | Moderate — but 95% CI is ~52-71% |
| AWAY EDGE | 72 | Small |
| UNDER (both tired) | 32 | Very small — 95% CI is ~44-79% |
| Spread bucket "Home -2.5 to -0.5" | 13 | Meaningless |

The UNDER signal at 62.5% on 32 games has a confidence interval that includes 50%. It could easily be noise.

#### 4. The SPREAD-FLIP signal is the most interesting — and most suspicious

The finding that betting the MORE fatigued away team ATS wins 61.7% is counterintuitive. The explanation is "the market over-adjusts for away fatigue." This is plausible — it's a structural market mispricing theory (the market sees fatigue and over-corrects the spread).

But this is also the most vulnerable to being a one-season artifact. Does SPREAD-FLIP hold in 24-25? If it only exists in 25-26, it's likely noise.

#### 5. The UNDER signal has the same lookahead risk as NRFI

Does the fatigue calculation use information that was known at game time? If fatigue scores use game results from later in the season (e.g., updated travel schedules after postponements), the backtest has lookahead. This is less likely for NBA (schedules are fixed pre-season) but worth confirming.

## Exact Steps for the Audit Session

1. **Read the current backtest analysis files:**
   - `graded_backtest_24_25_v2_analysis.txt`
   - `graded_backtest_25_26_v2_analysis.txt`
   - Compare: do the SAME signal rules produce similar win rates in BOTH seasons?

2. **Check if signal rules were defined before or after seeing the data:**
   - Read session history / git log for when thresholds were set
   - If delta >= 4 was selected because delta >= 3 and delta >= 5 looked worse in the data, it's in-sample

3. **Run the market implied probability test (THE CRITICAL TEST):**
   - For every signaled game, get the closing spread and juice
   - Compute the market's implied ATS probability (e.g., -110 on each side = 52.38%, -130/+110 = different)
   - Compare: does our ATS win rate exceed the market's implied rate for THOSE SPECIFIC GAMES?
   - If our 61.7% is against games where the market implied 55%, our real edge is 6.7%, not 9.3%
   - If our 61.7% is against games where the market implied 60%, our real edge is 1.7% — barely there

4. **Check if fatigue is already in the spread:**
   - Take games where our model says "home is fatigued" — is the home spread already reduced?
   - Compare home spread on fatigued days vs non-fatigued days for the same team
   - If the spread is already 4 points lower on BTB, the market has priced fatigue

5. **Test each component of the fatigue score for LIFT vs market:**
   - Does back-to-back alone provide lift? (or does the spread already account for it?)
   - Does travel distance provide lift beyond B2B?
   - Does time zone change provide lift?
   - Does schedule density provide lift?
   - Same methodology as MLB session 19: test each component INDIVIDUALLY against market implied probability

## What to Do With the Results

Since NBA uses standard -110, the evaluation is simpler than MLB:

- **If ATS win rates cross-validate across both seasons at 55%+:** Genuine edge. The market is under-adjusting spreads for these fatigue patterns. Continue with confidence.
- **If ATS win rates cross-validate at 52.5-55%:** Thin but real edge. Similar to MLB K Props lineup flag. Be selective on which signals to bet.
- **If ATS win rates DON'T cross-validate (strong in one season, coin flip in the other):** In-sample artifact. Same conclusion as MLB's mined scenarios. Pause and investigate.
- **If the spread already fully adjusts for fatigue (fatigued teams' spreads move by the same amount as the performance impact):** The market prices fatigue completely. No edge regardless of ATS rate.

## Anti-Whiplash

This audit should NOT redesign the fatigue model. It should only answer: does the existing model beat the market's implied probability? If yes, keep it. If no, pause it. Do not mine new scenarios, add new features, or "improve" the model in the same session as the audit. Diagnosis and treatment are separate sessions.

## Key Files

- `NBA_Backtest_24_25_v2.csv` / `NBA_Backtest_25_26_v2.csv` — Backtest output data
- `graded_backtest_*_v2.csv` — Graded results with outcomes
- `graded_backtest_*_v2_analysis.txt` — Summary analysis
- `nba_edge_v2.html` (in NBA-Edge repo) — Live signal logic
- `nba_backtest.js` — Backtest engine (note: sleep formula diverges from live tool)
