"""
NBA Edge Model Audit — Comprehensive Cross-Season Analysis
============================================================
Answers the critical questions from the MLB Lessons Audit:
1. Do the same signal rules produce similar win rates in BOTH seasons?
2. Is the underlying fatigue thesis valid (before threshold mining)?
3. Is the FLIP signal a real effect or a one-season artifact?
4. Does the UNDER signal hold across seasons?
5. Are the deployed thresholds optimal, or just lucky in-sample picks?

Uses raw graded CSV data — no reliance on pre-computed analysis files.
"""
import csv
import math
import os
import sys

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def sleep_modifier(sleep_hrs):
    """Fatigue points from sleep deprivation — matches live tool formula."""
    if sleep_hrs < 4:
        return 4
    elif sleep_hrs < 6:
        return 2
    elif sleep_hrs < 7:
        return 1
    else:
        return 0


def correct_scenario_c(row):
    """Fix Scenario C sleep inflation from backtest.

    The backtest (nba_backtest.js line 186) adds +1.5 hrs to Scenario C sleep
    that the live tool does NOT add. This inflates sleep → deflates fatigue
    for home teams on away→home BTB. We correct by subtracting 1.5 from sleep
    and adjusting the fatigue score by the difference in sleep modifier.
    """
    corrected = False

    # Home team on Scenario C
    if row.get("home_scenario", "").strip() == "C":
        orig_sleep_str = row.get("home_sleep", "")
        if orig_sleep_str and orig_sleep_str.strip():
            orig_sleep = float(orig_sleep_str)
            corrected_sleep = max(0, orig_sleep - 1.5)
            old_mod = sleep_modifier(orig_sleep)
            new_mod = sleep_modifier(corrected_sleep)
            fatigue_adj = new_mod - old_mod  # positive = more fatigued
            row["home_fatigue"] = min(10.0, round((row["home_fatigue"] + fatigue_adj) * 10) / 10)
            row["home_sleep_corrected"] = corrected_sleep
            row["home_fatigue_adj"] = fatigue_adj
            corrected = True

    # Away team on Scenario C (rare — away team came home then went away again?)
    # Actually Scenario C = away→home, so this only applies to home team.
    # But check anyway for data integrity.
    if row.get("away_scenario", "").strip() == "C":
        orig_sleep_str = row.get("away_sleep", "")
        if orig_sleep_str and orig_sleep_str.strip():
            orig_sleep = float(orig_sleep_str)
            corrected_sleep = max(0, orig_sleep - 1.5)
            old_mod = sleep_modifier(orig_sleep)
            new_mod = sleep_modifier(corrected_sleep)
            fatigue_adj = new_mod - old_mod
            row["away_fatigue"] = min(10.0, round((row["away_fatigue"] + fatigue_adj) * 10) / 10)
            row["away_sleep_corrected"] = corrected_sleep
            row["away_fatigue_adj"] = fatigue_adj
            corrected = True

    return corrected


def load_csv(filename):
    """Load graded CSV, apply Scenario C sleep correction, return list of dicts."""
    path = os.path.join(DATA_DIR, filename)
    rows = []
    corrections = 0
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            # Type conversions
            r["away_fatigue"] = float(r["away_fatigue"]) if r["away_fatigue"] else 0.0
            r["home_fatigue"] = float(r["home_fatigue"]) if r["home_fatigue"] else 0.0
            r["max_fatigue"] = float(r["max_fatigue"]) if r["max_fatigue"] else 0.0
            r["both_tired"] = r["both_tired"].strip().lower() == "true"
            r["home_spread"] = float(r["home_spread"]) if r["home_spread"] else None
            r["close_total"] = float(r["close_total"]) if r["close_total"] else None
            r["away_score"] = int(r["away_score"]) if r["away_score"] else None
            r["home_score"] = int(r["home_score"]) if r["home_score"] else None

            # Apply Scenario C sleep correction BEFORE computing derived fields
            if correct_scenario_c(r):
                corrections += 1
                # Recompute max_fatigue and both_tired after correction
                r["max_fatigue"] = max(r["away_fatigue"], r["home_fatigue"])
                r["both_tired"] = r["away_fatigue"] >= 5 and r["home_fatigue"] >= 5

            # Compute fatigue delta (always positive = magnitude of gap)
            r["fatigue_delta"] = abs(r["away_fatigue"] - r["home_fatigue"])
            # Who is more fatigued
            r["home_more_fatigued"] = r["home_fatigue"] > r["away_fatigue"]
            r["away_more_fatigued"] = r["away_fatigue"] > r["home_fatigue"]
            # ATS outcome: did AWAY cover?
            r["away_covered"] = r["ats_result"].strip().lower() == "away" if r["ats_result"] else None
            r["home_covered"] = r["ats_result"].strip().lower() == "home" if r["ats_result"] else None
            # Under result
            r["under_hit"] = r.get("under_result", "").strip().upper() == "WIN"
            # Game total
            if r["away_score"] is not None and r["home_score"] is not None:
                r["game_total"] = r["away_score"] + r["home_score"]
            else:
                r["game_total"] = None
            # Is BTB (away)
            r["away_is_btb"] = r["away_scenario"].strip() not in ("rest", "") if r.get("away_scenario") else False
            # Is BTB (home)
            r["home_is_btb"] = r["home_scenario"].strip() not in ("rest", "") if r.get("home_scenario") else False
            # Recompute edge_side after correction (fatigue may have shifted)
            if r["home_fatigue"] > r["away_fatigue"]:
                r["edge_side_corrected"] = "AWAY EDGE"
            elif r["away_fatigue"] > r["home_fatigue"]:
                r["edge_side_corrected"] = "HOME EDGE"
            else:
                r["edge_side_corrected"] = r["edge_side"].strip()
            rows.append(r)
    print(f"  Loaded {filename}: {len(rows)} games, {corrections} Scenario C corrections applied")
    return rows


def wilson_ci(wins, total, z=1.96):
    """Wilson score confidence interval for binomial proportion."""
    if total == 0:
        return 0.0, 0.0, 0.0
    p = wins / total
    denom = 1 + z**2 / total
    centre = (p + z**2 / (2 * total)) / denom
    spread = z * math.sqrt((p * (1 - p) + z**2 / (4 * total)) / total) / denom
    return max(0, centre - spread), min(1, centre + spread), p


def record_str(wins, total):
    """Format W-L record with win rate and 95% CI."""
    losses = total - wins
    if total == 0:
        return "0-0 (no data)"
    lo, hi, pct = wilson_ci(wins, total)
    return f"{wins}W {losses}L = {pct*100:.1f}%  [95% CI: {lo*100:.1f}%-{hi*100:.1f}%]  (n={total})"


def section(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


def subsection(title):
    print(f"\n--- {title} ---")


def analyze_season(rows, label):
    """Run full analysis on one season's data."""
    section(f"SEASON: {label}")

    total = len(rows)
    print(f"Total flagged games: {total}")

    # Show Scenario C correction impact
    flipped = sum(1 for r in rows if r["edge_side"].strip() != r["edge_side_corrected"])
    sc_games = sum(1 for r in rows if r.get("home_scenario", "").strip() == "C" or r.get("away_scenario", "").strip() == "C")
    print(f"Scenario C games: {sc_games}, edge side changed after correction: {flipped}")

    # Count edge sides (using corrected values)
    home_edge = [r for r in rows if r["edge_side_corrected"] == "HOME EDGE"]
    away_edge = [r for r in rows if r["edge_side_corrected"] == "AWAY EDGE"]
    print(f"HOME EDGE games (away more fatigued): {len(home_edge)}")
    print(f"AWAY EDGE games (home more fatigued): {len(away_edge)}")

    # =========================================
    # Q1: SPREAD signal (AWAY EDGE, bet AWAY)
    # =========================================
    subsection("SPREAD SIGNAL — Bet AWAY when HOME is fatigued")

    # Broadest: all AWAY EDGE games, bet away
    away_edge_wins = sum(1 for r in away_edge if r["away_covered"])
    away_edge_valid = sum(1 for r in away_edge if r["away_covered"] is not None)
    print(f"  All AWAY EDGE, bet away: {record_str(away_edge_wins, away_edge_valid)}")

    # Add home BTB filter
    ae_hbtb = [r for r in away_edge if r["home_is_btb"]]
    ae_hbtb_w = sum(1 for r in ae_hbtb if r["away_covered"])
    ae_hbtb_v = sum(1 for r in ae_hbtb if r["away_covered"] is not None)
    print(f"  + Home on BTB:            {record_str(ae_hbtb_w, ae_hbtb_v)}")

    # Test delta thresholds (THE MINING TEST)
    print(f"\n  Delta threshold scan (looking for monotonic relationship):")
    for delta in [0, 1, 2, 3, 4, 5, 6, 7, 8]:
        subset = [r for r in ae_hbtb if r["fatigue_delta"] >= delta]
        w = sum(1 for r in subset if r["away_covered"])
        v = sum(1 for r in subset if r["away_covered"] is not None)
        marker = " <-- DEPLOYED" if delta == 4 else ""
        print(f"    delta >= {delta}: {record_str(w, v)}{marker}")

    # Test spread gates
    print(f"\n  Spread gate scan (AWAY EDGE + home BTB + delta >= 4):")
    base = [r for r in ae_hbtb if r["fatigue_delta"] >= 4 and r["home_spread"] is not None]
    for lo, hi, label in [(-20, -10, "Home -10+"), (-9.5, -7, "Home -7 to -9.5"),
                           (-6.5, -3, "Home -3 to -6.5"), (-2.5, -1, "Home -1 to -2.5"),
                           (-9.5, -1, "Home -1 to -9.5 (DEPLOYED)"),
                           (-6.5, -1, "Home -1 to -6.5"),
                           (-20, 0, "All home favorites")]:
        subset = [r for r in base if lo <= r["home_spread"] <= hi]
        w = sum(1 for r in subset if r["away_covered"])
        v = sum(1 for r in subset if r["away_covered"] is not None)
        print(f"    {label}: {record_str(w, v)}")

    # =========================================
    # Q2: FLIP signal (HOME EDGE, bet AWAY — counterintuitive)
    # =========================================
    subsection("FLIP SIGNAL — Bet AWAY when AWAY is fatigued (market over-correction thesis)")

    # Natural direction: HOME EDGE, bet HOME
    he_home_w = sum(1 for r in home_edge if r["home_covered"])
    he_home_v = sum(1 for r in home_edge if r["home_covered"] is not None)
    print(f"  HOME EDGE, bet HOME (natural): {record_str(he_home_w, he_home_v)}")

    # Flipped: HOME EDGE, bet AWAY
    he_away_w = sum(1 for r in home_edge if r["away_covered"])
    he_away_v = sum(1 for r in home_edge if r["away_covered"] is not None)
    print(f"  HOME EDGE, bet AWAY (FLIP):    {record_str(he_away_w, he_away_v)}")

    # FLIP with away BTB + delta thresholds
    he_abtb = [r for r in home_edge if r["away_is_btb"]]
    print(f"\n  FLIP + Away on BTB:            {record_str(sum(1 for r in he_abtb if r['away_covered']), sum(1 for r in he_abtb if r['away_covered'] is not None))}")

    print(f"\n  FLIP delta threshold scan (away BTB, bet away):")
    for delta in [0, 1, 2, 3, 4, 5, 6, 7, 8]:
        subset = [r for r in he_abtb if r["fatigue_delta"] >= delta]
        w = sum(1 for r in subset if r["away_covered"])
        v = sum(1 for r in subset if r["away_covered"] is not None)
        marker = " <-- DEPLOYED" if delta == 4 else ""
        print(f"    delta >= {delta}: {record_str(w, v)}{marker}")

    # FLIP spread gates
    print(f"\n  FLIP spread gate scan (away BTB + delta >= 4):")
    flip_base = [r for r in he_abtb if r["fatigue_delta"] >= 4 and r["home_spread"] is not None]
    for lo, hi, label in [(-20, -10, "Home -10+"), (-9.5, -7, "Home -7 to -9.5"),
                           (-6.5, -3, "Home -3 to -6.5"), (-2.5, -1, "Home -1 to -2.5"),
                           (-6.5, -1, "Home -1 to -6.5 (DEPLOYED)"),
                           (-9.5, -1, "Home -1 to -9.5"),
                           (-20, 0, "All home favorites")]:
        subset = [r for r in flip_base if lo <= r["home_spread"] <= hi]
        w = sum(1 for r in subset if r["away_covered"])
        v = sum(1 for r in subset if r["away_covered"] is not None)
        print(f"    {label}: {record_str(w, v)}")

    # =========================================
    # Q3: UNDER signal (both tired, bet UNDER)
    # =========================================
    subsection("UNDER SIGNAL — Bet UNDER when both teams fatigued")

    both = [r for r in rows if r["both_tired"]]
    both_under_w = sum(1 for r in both if r["ou_result"].strip().lower() == "under")
    both_under_v = sum(1 for r in both if r["ou_result"].strip().lower() in ("under", "over"))
    print(f"  Both tired (>=5), game goes under: {record_str(both_under_w, both_under_v)}")

    # Add away BTB
    both_abtb = [r for r in both if r["away_is_btb"]]
    bab_w = sum(1 for r in both_abtb if r["ou_result"].strip().lower() == "under")
    bab_v = sum(1 for r in both_abtb if r["ou_result"].strip().lower() in ("under", "over"))
    print(f"  + Away on BTB:                    {record_str(bab_w, bab_v)}")

    # Add scenario A
    both_a = [r for r in both_abtb if r["away_scenario"].strip() == "A"]
    ba_w = sum(1 for r in both_a if r["ou_result"].strip().lower() == "under")
    ba_v = sum(1 for r in both_a if r["ou_result"].strip().lower() in ("under", "over"))
    print(f"  + Away scenario A:                {record_str(ba_w, ba_v)}")

    # Total gate
    print(f"\n  UNDER total gate scan (both tired + away BTB + scenario A):")
    for gate in [220, 225, 228, 230, 232, 234, 236, 240]:
        subset = [r for r in both_a if r["close_total"] is not None and r["close_total"] < gate]
        w = sum(1 for r in subset if r["ou_result"].strip().lower() == "under")
        v = sum(1 for r in subset if r["ou_result"].strip().lower() in ("under", "over"))
        marker = " <-- DEPLOYED" if gate == 234 else ""
        print(f"    total < {gate}: {record_str(w, v)}{marker}")

    # No gate at all
    no_gate = both_a
    ng_w = sum(1 for r in no_gate if r["ou_result"].strip().lower() == "under")
    ng_v = sum(1 for r in no_gate if r["ou_result"].strip().lower() in ("under", "over"))
    print(f"    no total gate:  {record_str(ng_w, ng_v)}")

    return {
        "away_edge_raw": (away_edge_wins, away_edge_valid),
        "flip_raw": (he_away_w, he_away_v),
        "under_both_tired": (both_under_w, both_under_v),
        "home_edge": home_edge,
        "away_edge": away_edge,
    }


def cross_season_comparison(s1_data, s2_data, s1_label, s2_label):
    """Compare key metrics across seasons to test stability."""
    section("CROSS-SEASON STABILITY TEST")
    print("If thresholds are NOT overfit, the same rules should produce similar")
    print("win rates in both seasons. Large divergence = likely overfitting.\n")

    comparisons = [
        ("AWAY EDGE, bet away (raw)", s1_data["away_edge_raw"], s2_data["away_edge_raw"]),
        ("FLIP: HOME EDGE, bet away (raw)", s1_data["flip_raw"], s2_data["flip_raw"]),
        ("UNDER: both tired, game under", s1_data["under_both_tired"], s2_data["under_both_tired"]),
    ]

    for name, (w1, n1), (w2, n2) in comparisons:
        p1 = w1/n1*100 if n1 > 0 else 0
        p2 = w2/n2*100 if n2 > 0 else 0
        diff = abs(p1 - p2)
        stability = "STABLE" if diff < 5 else "MODERATE DIVERGENCE" if diff < 10 else "LARGE DIVERGENCE"
        print(f"  {name}:")
        print(f"    {s1_label}: {w1}W/{n1} = {p1:.1f}%")
        print(f"    {s2_label}: {w2}W/{n2} = {p2:.1f}%")
        print(f"    Gap: {diff:.1f}pp → {stability}")
        print()


def broadest_signal_test(all_rows):
    """Test the broadest possible fatigue signal — no threshold mining.
    Question: does ANY level of home fatigue predict away covering ATS?"""
    section("BROADEST SIGNAL TEST — Does fatigue predict ATS at all?")
    print("Testing with ZERO threshold mining. Just: is home more fatigued?")
    print("If this doesn't work, no amount of threshold tuning will help.\n")

    # All games where home is more fatigued (AWAY EDGE)
    ae = [r for r in all_rows if r["edge_side_corrected"] == "AWAY EDGE"]
    ae_w = sum(1 for r in ae if r["away_covered"])
    ae_v = sum(1 for r in ae if r["away_covered"] is not None)
    print(f"  Home more fatigued → bet away ATS: {record_str(ae_w, ae_v)}")

    # All games where away is more fatigued (HOME EDGE) — bet home
    he = [r for r in all_rows if r["edge_side_corrected"] == "HOME EDGE"]
    he_w = sum(1 for r in he if r["home_covered"])
    he_v = sum(1 for r in he if r["home_covered"] is not None)
    print(f"  Away more fatigued → bet home ATS: {record_str(he_w, he_v)}")

    # All games where both tired → game goes under
    bt = [r for r in all_rows if r["both_tired"]]
    bt_w = sum(1 for r in bt if r["ou_result"].strip().lower() == "under")
    bt_v = sum(1 for r in bt if r["ou_result"].strip().lower() in ("under", "over"))
    print(f"  Both tired (>=5) → game goes under: {record_str(bt_w, bt_v)}")

    # FLIP: away more fatigued → bet AWAY anyway
    he_flip_w = sum(1 for r in he if r["away_covered"])
    he_flip_v = sum(1 for r in he if r["away_covered"] is not None)
    print(f"  Away more fatigued → bet away ATS (FLIP thesis): {record_str(he_flip_w, he_flip_v)}")

    print(f"\n  Break-even at -110: 52.38%")
    print(f"  Any signal above ~55% with n>100 is interesting.")
    print(f"  Anything below 52.38% is worse than random.\n")


def monotonicity_test(all_rows):
    """Test if higher fatigue delta monotonically improves ATS rate.
    A real effect should show: more fatigue gap = better ATS performance.
    An overfit signal shows: spike at one threshold, not monotonic."""
    section("MONOTONICITY TEST — Does more fatigue = better ATS?")
    print("A REAL effect should be monotonic: as delta increases, win rate")
    print("should consistently improve. Random noise looks jagged.\n")

    # AWAY EDGE: bet away, by delta buckets
    ae = [r for r in all_rows if r["edge_side_corrected"] == "AWAY EDGE"]
    print("  AWAY EDGE (bet away) by delta bucket:")
    for lo, hi in [(0, 2), (2, 4), (4, 6), (6, 8), (8, 12)]:
        subset = [r for r in ae if lo <= r["fatigue_delta"] < hi]
        w = sum(1 for r in subset if r["away_covered"])
        v = sum(1 for r in subset if r["away_covered"] is not None)
        print(f"    delta {lo}-{hi}: {record_str(w, v)}")

    # HOME EDGE natural (bet home) by delta buckets
    he = [r for r in all_rows if r["edge_side_corrected"] == "HOME EDGE"]
    print("\n  HOME EDGE (bet home, natural direction) by delta bucket:")
    for lo, hi in [(0, 2), (2, 4), (4, 6), (6, 8), (8, 12)]:
        subset = [r for r in he if lo <= r["fatigue_delta"] < hi]
        w = sum(1 for r in subset if r["home_covered"])
        v = sum(1 for r in subset if r["home_covered"] is not None)
        print(f"    delta {lo}-{hi}: {record_str(w, v)}")

    # FLIP (bet away in HOME EDGE) by delta
    print("\n  HOME EDGE FLIPPED (bet away, FLIP thesis) by delta bucket:")
    for lo, hi in [(0, 2), (2, 4), (4, 6), (6, 8), (8, 12)]:
        subset = [r for r in he if lo <= r["fatigue_delta"] < hi]
        w = sum(1 for r in subset if r["away_covered"])
        v = sum(1 for r in subset if r["away_covered"] is not None)
        print(f"    delta {lo}-{hi}: {record_str(w, v)}")


def deployed_rules_by_season(s1, s2, s1_label, s2_label):
    """Apply EXACT deployed V2.1 rules to each season independently."""
    section("DEPLOYED V2.1 RULES — Applied per-season")
    print("These are the EXACT rules currently live. Testing each season separately.\n")

    for rows, label in [(s1, s1_label), (s2, s2_label)]:
        print(f"\n  === {label} ===")

        # SPREAD: AWAY EDGE + home BTB + delta >= 4 + spread -1 to -9.5
        spread_pool = [r for r in rows
                       if r["edge_side_corrected"] == "AWAY EDGE"
                       and r["home_is_btb"]
                       and r["fatigue_delta"] >= 4
                       and r["home_spread"] is not None
                       and -9.5 <= r["home_spread"] <= -1]
        sw = sum(1 for r in spread_pool if r["away_covered"])
        sv = sum(1 for r in spread_pool if r["away_covered"] is not None)
        print(f"  SPREAD (bet away): {record_str(sw, sv)}")

        # FLIP: HOME EDGE + away BTB + delta >= 4 + spread -1 to -6.5
        flip_pool = [r for r in rows
                     if r["edge_side_corrected"] == "HOME EDGE"
                     and r["away_is_btb"]
                     and r["fatigue_delta"] >= 4
                     and r["home_spread"] is not None
                     and -6.5 <= r["home_spread"] <= -1]
        fw = sum(1 for r in flip_pool if r["away_covered"])
        fv = sum(1 for r in flip_pool if r["away_covered"] is not None)
        print(f"  FLIP (bet away):   {record_str(fw, fv)}")

        # UNDER: both tired + away BTB + away scenario A + total < 234
        under_pool = [r for r in rows
                      if r["both_tired"]
                      and r["away_is_btb"]
                      and r["away_scenario"].strip() == "A"
                      and r["close_total"] is not None
                      and r["close_total"] < 234]
        uw = sum(1 for r in under_pool if r["ou_result"].strip().lower() == "under")
        uv = sum(1 for r in under_pool if r["ou_result"].strip().lower() in ("under", "over"))
        print(f"  UNDER (bet under): {record_str(uw, uv)}")

        # Combined
        total_w = sw + fw + uw
        total_v = sv + fv + uv
        print(f"  COMBINED:          {record_str(total_w, total_v)}")


def spread_movement_analysis(all_rows):
    """Check if the spread already accounts for fatigue.
    If home teams on BTB already get smaller spreads, market is pricing fatigue."""
    section("MARKET PRICING TEST — Is fatigue already in the spread?")
    print("Comparing average home spread on BTB vs non-BTB days.\n")

    # AWAY EDGE games (home is more fatigued)
    ae = [r for r in all_rows if r["edge_side_corrected"] == "AWAY EDGE" and r["home_spread"] is not None]
    ae_btb = [r for r in ae if r["home_is_btb"]]
    ae_rest = [r for r in ae if not r["home_is_btb"]]

    if ae_btb:
        avg_btb = sum(r["home_spread"] for r in ae_btb) / len(ae_btb)
        print(f"  AWAY EDGE, home on BTB:  avg spread = {avg_btb:.1f} (n={len(ae_btb)})")
    if ae_rest:
        avg_rest = sum(r["home_spread"] for r in ae_rest) / len(ae_rest)
        print(f"  AWAY EDGE, home rested:  avg spread = {avg_rest:.1f} (n={len(ae_rest)})")

    # HOME EDGE games (away is more fatigued)
    he = [r for r in all_rows if r["edge_side_corrected"] == "HOME EDGE" and r["home_spread"] is not None]
    he_btb = [r for r in he if r["away_is_btb"]]
    he_rest = [r for r in he if not r["away_is_btb"]]

    if he_btb:
        avg_btb = sum(r["home_spread"] for r in he_btb) / len(he_btb)
        print(f"\n  HOME EDGE, away on BTB:  avg spread = {avg_btb:.1f} (n={len(he_btb)})")
    if he_rest:
        avg_rest = sum(r["home_spread"] for r in he_rest) / len(he_rest)
        print(f"  HOME EDGE, away rested:  avg spread = {avg_rest:.1f} (n={len(he_rest)})")

    # By fatigue score buckets — does higher fatigue = bigger spread adjustment?
    print(f"\n  Average home spread by home fatigue score (AWAY EDGE games):")
    for lo, hi in [(1, 3), (3, 5), (5, 7), (7, 9), (9, 11)]:
        subset = [r for r in ae if lo <= r["home_fatigue"] < hi]
        if subset:
            avg = sum(r["home_spread"] for r in subset) / len(subset)
            print(f"    home fatigue {lo}-{hi}: avg spread = {avg:.1f} (n={len(subset)})")

    print(f"\n  If spreads shrink as fatigue increases, the market IS pricing fatigue.")
    print(f"  Our edge (if any) is only in the RESIDUAL that the market misses.")


def main():
    print("=" * 70)
    print("  NBA EDGE MODEL — FORMAL AUDIT")
    print("  Generated from raw CSV data. No pre-computed analysis used.")
    print("=" * 70)

    s1 = load_csv("graded_backtest_24_25_v2.csv")
    s2 = load_csv("graded_backtest_25_26_v2.csv")

    print(f"\nLoaded: {len(s1)} games (24-25), {len(s2)} games (25-26)")
    print(f"Combined: {len(s1) + len(s2)} games")

    # Per-season analysis
    s1_data = analyze_season(s1, "2024-25")
    s2_data = analyze_season(s2, "2025-26")

    # Cross-season comparison
    cross_season_comparison(s1_data, s2_data, "24-25", "25-26")

    # Combined analysis (broadest signals)
    all_rows = s1 + s2
    broadest_signal_test(all_rows)
    monotonicity_test(all_rows)

    # Deployed rules per-season
    deployed_rules_by_season(s1, s2, "2024-25", "2025-26")

    # Market pricing test
    spread_movement_analysis(all_rows)

    # Final summary
    section("AUDIT VERDICT INPUTS")
    print("Review the above data to answer:")
    print("1. Do AWAY EDGE ATS rates cross-validate? (same direction, similar magnitude)")
    print("2. Does FLIP cross-validate? (if it reverses between seasons, it's noise)")
    print("3. Does UNDER cross-validate? (consistent > 52.38% in both seasons)")
    print("4. Is there a monotonic relationship? (more fatigue = better ATS)")
    print("5. Does the market already price fatigue? (spread shrinks on BTB)")
    print("6. Do deployed rules work in BOTH seasons? (not just combined)")


if __name__ == "__main__":
    main()
