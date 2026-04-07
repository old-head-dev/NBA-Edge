# NBA Edge Model — Future Improvements (V2 Planning)

**Date:** 2026-03-20
**Status:** Ideas for future reference — not currently planned for implementation
**Context:** Captured during comprehensive model review. Revisit after the current improvement plan (Approach B) is validated.

## Overview

These are potential enhancements that go beyond the current improvement plan. They range from straightforward additions to fundamental model changes. Each should be evaluated based on whether the current model's validated performance warrants further investment.

## 1. Market Efficiency Analysis

### The Question
Does the spread already price in fatigue? If a fatigued home favorite is getting -7 but would be -10 without the fatigue, the market is already giving 3 points of adjustment. The model's edge exists only if the market under-adjusts.

### How to Investigate
- For each flagged game, compare the closing spread against what a "neutral schedule" spread would be (e.g., the team's average ATS margin at home)
- Look at opening-to-closing line movement on BTB games vs non-BTB games
- If the line moves 2-3 points on BTB games, the market is aware of fatigue — the model needs to find games where it moves too little

### What This Would Add
A "market adjustment" column that estimates how many points the market already gave for fatigue. The true edge becomes `model_fatigue_impact - market_adjustment`. This would likely reduce the signal count but increase the win rate on remaining signals.

### Complexity
High. Requires historical opening lines (not currently available from The Odds API historical endpoint, which only captures snapshots) or a line-movement data source.

## 2. Player-Level Injury & Load Impact

### The Question
A team's fatigue resilience depends on roster depth. Golden State on a BTB can manage Curry's minutes across a deep bench. A depleted team with 3 starters out is already stretched — BTB fatigue compounds the problem.

### How to Investigate
- Use the NBA injury report data (the proxy.py infrastructure for this already exists)
- Track the number of listed players per team per game
- Add an "injury burden" modifier to the fatigue score: more injured players = higher effective fatigue

### What This Would Add
A multiplier on the fatigue score based on roster availability. A team at full strength on a BTB is less affected than a team missing 3 rotation players.

### Complexity
Medium. The proxy.py already handles NBA injury report PDFs via Claude Vision. The challenge is automating this for historical games (injury reports aren't archived publicly in a structured format).

## 3. Pace & Tempo Adjustment for Unders

### The Question
The both-tired under signal (66.0% in 24-25) doesn't account for team pace. Two fatigued fast-paced teams might still go over. Two fatigued slow-paced teams are a stronger under.

### How to Investigate
- Pull team pace data (possessions per game) from a public source like basketball-reference or the NBA stats API
- Filter the both-tired under signal by combined pace
- Hypothesis: both-tired + both-slow-pace = stronger under signal

### What This Would Add
A pace-adjusted confidence level for under signals. Could turn the binary "bet under" into a tiered system (strong/moderate/weak).

### Complexity
Low-medium. Pace data is widely available. Integration is a simple lookup + filter.

## 4. Empirically Derived Scoring Weights

### The Question
The current weights (Scenario A=5, B=3, C=4, sleep<4h=+4, etc.) are judgment calls. Are they optimal?

### How to Investigate
- Use logistic regression on the graded backtest data: outcome (WIN/LOSS) as dependent variable, individual fatigue components as independent variables
- Let the data tell you which factors actually predict ATS outcomes
- Compare model-derived weights against current hand-tuned weights

### What This Would Add
Data-backed weights instead of intuition-based ones. Might reveal that some factors (e.g., altitude) matter more or less than assumed.

### Complexity
Medium. Requires enough sample size to be statistically meaningful (~500+ games). Could combine multiple seasons. Python's scikit-learn makes the regression straightforward.

### Risk
Overfitting. With ~15 features and ~300 games per season, there's a real risk of fitting noise. Would need proper train/test splits and cross-validation.

## 5. Net Rating Instead of Win Percentage

### The Question
Win percentage (Phase 3 of current plan) is a blunt instrument. A .400 team that loses close games is different from a .400 team getting blown out nightly.

### How to Investigate
- Calculate net rating (point differential per game) from BallDontLie game data
- Replace the win-percentage filter with a net-rating filter
- Test whether net rating is a better predictor of "will this team compete regardless of fatigue"

### What This Would Add
A more nuanced team-quality signal. Particularly useful for mid-season when W-L records haven't stabilized but point differentials have.

### Complexity
Low. The data is already available. Just requires computing average margin from game scores.

## 6. Proper Statistical Validation Framework

### The Question
Is the 56.9% win rate statistically significant, or could it be luck? With 283 games, a 50% true rate would produce 56.9%+ about 1.4% of the time (p ≈ 0.014). That's suggestive but not conclusive, especially given that the model was tuned looking at this data.

### How to Investigate
- Implement train/test splits: develop rules on 24-25 data, validate on 25-26 data (or vice versa)
- Bootstrap confidence intervals on win rates
- Track expected value (EV) accounting for standard -110 vig, not just win rate
- A 56.9% win rate at -110 yields ~+4.5% ROI — meaningful but thin

### What This Would Add
Honest confidence bounds on whether the edge is real. The difference between "this looks good" and "this is statistically defensible."

### Complexity
Medium. The statistical methods are standard. The challenge is having enough data — ideally 3+ seasons.

## 7. Real-Time Line Shopping

### The Question
The model grades against average closing lines across all books. But the bettor places at one book. If you can find a book offering +8 when the average is +6.5, your effective edge increases.

### How to Investigate
- The Odds API returns individual bookmaker lines, not just averages
- Track the spread of lines across books for flagged games
- Identify which books consistently offer the best line on BTB-fatigued teams

### What This Would Add
A "best available line" column in the live tool, showing which book to bet at and the expected value improvement vs. average line.

### Complexity
Low for analysis. The data is already in the Odds API response — the grading script just averages it currently. Higher for live integration (would need real-time Odds API calls, not historical).

## 8. Consolidate Local + GitHub Codebases

### The Question
The local project (backtest/analysis scripts) and the GitHub Pages tool (live dashboard + nightly grader) are separate codebases with duplicated logic. Changes to one don't automatically propagate to the other.

### How to Investigate
- Map the shared logic between `nba_backtest.js` and `nba_edge_v2.html`
- Map the shared logic between `grade_backtest.py` and `update_results.py`
- Design a shared module structure

### What This Would Add
One source of truth for the fatigue model. Change it once, it updates everywhere. Reduces the risk of the local and live versions diverging.

### Complexity
Medium. The HTML dashboard embeds the fatigue model in inline JavaScript. Extracting it to a shared module would require restructuring the GitHub Pages site (possibly using a build step).

## 9. Home Court Advantage Variability

### The Question
Some arenas (Denver at altitude, Utah at altitude) have measurably different home-court advantages. The current model treats home court as uniform — the only arena-specific factor is the altitude penalty for DEN/UTA visitors.

### How to Investigate
- Compute historical home ATS records by team from BallDontLie data
- Identify teams with significantly above/below-average home court advantage
- Test whether incorporating venue-specific HCA improves signal accuracy

### What This Would Add
A lookup table of historical home ATS performance that adjusts the model's confidence in "home edge" vs "away edge" signals based on where the game is played.

### Complexity
Low-medium. The data is available. The challenge is separating venue effects from team-quality effects.

## 10. Season-Stage Effects

### The Question
Fatigue impacts may differ in early season (conditioning ramp-up, new rosters gelling) vs. late season (playoff implications, rest management, tanking). The analysis script already breaks down by month — if a systematic pattern emerges, a season-stage modifier could be worthwhile.

### How to Investigate
- Analyze win rates by month across multiple seasons
- Look for consistent patterns (e.g., does the model always underperform in April?)
- Test whether a simple "early/mid/late season" modifier improves results

### What This Would Add
A seasonal adjustment that either weights fatigue differently by period or adjusts confidence in signals based on time of year.

### Complexity
Low. The monthly breakdown already exists in the analysis output. Just needs multi-season data to confirm patterns aren't noise.

## 11. Flag Threshold Validation (Survivorship Bias Check)

### The Question
The backtest only analyzes games where `max_score >= 5`. Games just below the threshold (score 4-4.9) are invisible. Is 5 the optimal threshold, or is it an artifact?

### How to Investigate
- Run the backtest without a flag threshold (output all games with any fatigue delta)
- Analyze win rates at threshold 3, 4, 5, 6, 7
- Determine if lowering the threshold captures additional profitable games or if raising it improves win rate enough to offset fewer bets

### What This Would Add
Confidence that the threshold is optimal, or a better threshold that produces more (or better) signals.

### Complexity
Low. Just requires running the backtest with a lower threshold and re-analyzing.

## Priority Ordering (Suggested)

If pursuing these after the current plan validates:

1. **Net rating** (#5) — easiest upgrade to the team-quality filter, data already available
2. **Pace adjustment for unders** (#3) — targeted improvement to the most promising signal
3. **Flag threshold validation** (#11) — low-effort check that could expand signal count
4. **Codebase consolidation** (#8) — reduces maintenance burden before adding more features
5. **Statistical validation** (#6) — honest assessment before investing in more complexity
6. **Season-stage effects** (#10) — low-effort if multi-season data is available
7. **Market efficiency** (#1) — the most important strategic question but hardest to answer
8. **Home court variability** (#9) — moderate effort, moderate potential payoff
9. **Empirical weights** (#4) — only after having 500+ graded games across multiple seasons
10. **Player injury impact** (#2) — high value but hard to automate historically
11. **Line shopping** (#7) — nice-to-have, more about execution than model quality
