# NBA Edge Model — Architecture & Research Future Plan (Tiers 4-5)

**Date:** 2026-03-21
**Status:** Future reference — not currently planned for implementation
**Context:** Extracted from the Tiers 1-3 implementation plan. These items require more data, more seasons, or fundamental model changes. Revisit after V2 signals are validated in live deployment.

---

## Tier 4: Model Architecture Improvements

### 4A. Continuous Fatigue Scoring

Replace the hard FLAG_THRESHOLD=5 gate with confidence tiers (STRONG/MODERATE/WEAK) based on delta + absolute score + spread. Currently a game with fatigue 4.9 is invisible while 5.0 is flagged. Confidence tiers would capture games below the threshold while adding nuance above it.

Suggested tiers:
- STRONG: delta >= 5 + fatigued score >= 6 + spread in sweet spot
- MODERATE: delta >= 4 + fatigued score >= 5 + spread < 0
- WEAK: delta >= 3 OR fatigued score >= 5 (tracking only)

### 4B. Empirically Validate Scoring Weights

Current weights are judgment calls (Scenario A=5, B=3, C=4; sleep<4h=+4, <6h=+2; tz penalty +0.5/hr capped at 1.5; altitude=+1.0). Run logistic regression on 470+ graded games using individual fatigue components as features and ATS outcome as target. Compare model-derived weights vs current. Risk: overfitting with ~12 features on 470 games — use leave-one-season-out cross-validation.

### 4C. Net Rating Instead of Win%

Upgrade team quality filter from simple win% to point differential per game. More stable and predictive. A .400 team losing close games is different from a .400 team getting blown out. Easy to implement — extend the running accumulator to track pointsFor/pointsAgainst.

### 4D. Flag Threshold Validation

Test thresholds 3/4/5/6/7 on full backtest data. The current threshold=5 may be leaving profitable games on the table (survivorship bias). Connected to 4A — if confidence tiers are implemented, this becomes less critical.

---

## Tier 5: Future Research

### 5A. Team-Specific Fatigue Multipliers

IND covers only 20% when fatigued, POR covers 81%. But n=15-19 per team per season is too small. Track across 3+ seasons before implementing.

### 5B. Travel Distance Sweet Spot

200-500mi fatigue games go 66.7% (28W 14L). 0-200mi (local moves like LAL/LAC) go 33.3%. Interesting but small samples.

### 5C. Day-of-Week Effects

Sunday games 44.6%, Saturday 56.0%. Could be noise. Need more seasons.

### 5D. Pace-Adjusted Unders

Filter under signals by combined team pace. Two slow tired teams = stronger under.

### 5E. Market Efficiency Analysis

Compare opening vs closing line movement on BTB games. If lines move 3+ points, market is already pricing fatigue.

---

## Extended Future Improvements

See also: `2026-03-20-future-improvements-v2.md` for additional research items including:
- Market efficiency analysis (opening vs closing lines)
- Player-level injury & load impact
- Pace & tempo adjustment for unders
- Real-time line shopping
- Codebase consolidation (local + GitHub)
- Home court advantage variability
- Season-stage effects
- Statistical validation framework
