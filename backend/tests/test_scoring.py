"""Scoring scenarios with full per-card detail.

Deterministic wallet (mirrors the 6 real mapped cards) so the math is
verifiable. For each scenario it prints, per card:
  priority, balance now->after, utilization before->after, cashback,
  risk, score, savings vs average.
And asserts the winner + the arithmetic.

Run: python backend/tests/test_scoring.py   (from repo root)
"""

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from app.scoring import engine, savings  # noqa: E402

# rates are effective decimals, point_value 1.0 (VectorMint-cached shape).
CARDS = {
    "sapphire": {"name": "Chase Sapphire Preferred", "point_value": 1.0, "base_rate": 0.0125,
                 "rates": {"travel": 0.0625, "dining": 0.0375, "gas": 0.0375,
                           "online_shopping": 0.0375, "streaming": 0.0375}},
    "venture": {"name": "Capital One Venture", "point_value": 1.0, "base_rate": 0.02,
                "rates": {"travel": 0.05}},
    "bofa": {"name": "BofA Customized Cash", "point_value": 1.0, "base_rate": 0.01,
             "rates": {"groceries": 0.02, "dining": 0.03, "gas": 0.03,
                       "travel": 0.03, "online_shopping": 0.03}},
    "amex_gold": {"name": "Amex Gold", "point_value": 1.0, "base_rate": 0.012,
                  "rates": {"dining": 0.048, "groceries": 0.048, "travel": 0.06}},
    "blue_cash": {"name": "Blue Cash Preferred", "point_value": 1.0, "base_rate": 0.01,
                  "rates": {"groceries": 0.06, "streaming": 0.06, "gas": 0.03, "travel": 0.03}},
    "freedom": {"name": "Chase Freedom Unlimited", "point_value": 1.0, "base_rate": 0.0188,
                "rates": {"travel": 0.0625, "dining": 0.0375, "online_shopping": 0.0375}},
}


def fresh_state():
    return {
        "dollars_per_fico_point": 2.0,
        "baseline_score": 740.0,
        "cards": {
            "sapphire":  {"balance": 2500.0, "limit": 10000.0},
            "venture":   {"balance": 5200.0, "limit": 8000.0},
            "bofa":      {"balance": 800.0,  "limit": 5000.0},
            "amex_gold": {"balance": 1500.0, "limit": 12000.0},
            "blue_cash": {"balance": 3200.0, "limit": 6000.0},
            "freedom":   {"balance": 4800.0, "limit": 7000.0},
        },
    }


def run(place, category, amount):
    state = fresh_state()
    result = engine.rank(state, category, amount, CARDS)
    rows = savings.annotate(result, state, amount)
    summ = savings.summary(result)

    print("\n" + "=" * 92)
    print(f"  {place}  —  ${amount:.0f} {category}")
    print("=" * 92)
    print(f"  {'#':<2}{'card':<26}{'balance now->after':>22}"
          f"{'util before->after':>22}{'cash':>7}{'risk':>8}{'score':>8}{'vs avg':>8}")
    print("  " + "-" * 88)
    for c in rows:
        bal = f"${c['balance_now']:.0f}->${c['balance_after']:.0f}"
        util = f"{c['current_utilization']}%->{c['projected_utilization']}%"
        risk = c["breakdown"]["risk"]
        star = " *" if c["is_best"] else ""
        print(f"  {c['priority']:<2}{c['card_name'][:24]:<26}{bal:>22}{util:>22}"
              f"{c['estimated_value']:>7.2f}{risk:>8.2f}{c['score']:>8.2f}"
              f"{c['savings_vs_average']:>8.2f}{star}")
    print(f"\n  WINNER: {summ['best_card_name']}   "
          f"saved ${summ['saved']:.2f}  (best ${summ['best_value']:.2f} - average ${summ['average_value']:.2f})")
    return result, rows, summ


# --- math checks -----------------------------------------------------------


def check(name, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if not cond and detail else ""))
    return cond


def main():
    ok = True

    # Scenario 1: HEB groceries.
    result, rows, summ = run("HEB", "groceries", 100.0)
    best = rows[0]
    ok &= check("HEB winner is Blue Cash Preferred (6%)", best["card_name"] == "Blue Cash Preferred")
    ok &= check("winner has priority 1", best["priority"] == 1)
    ok &= check("reward = rate x amount", abs(best["estimated_value"] - 0.06 * 100) < 1e-9,
                f"{best['estimated_value']}")
    ok &= check("BofA (16%) ranks above Venture (65%) on the 2% tie",
                [r["card_name"] for r in rows].index("BofA Customized Cash")
                < [r["card_name"] for r in rows].index("Capital One Venture"))

    # Scenario 2: Nike.com online shopping.
    result2, rows2, summ2 = run("Nike.com", "online_shopping", 120.0)
    best2 = rows2[0]
    ok &= check("Nike winner is Chase Sapphire (3.75%)", best2["card_name"] == "Chase Sapphire Preferred")
    ok &= check("Freedom (same 3.75% but 68% util) is demoted, not the winner",
                best2["card_name"] != "Chase Freedom Unlimited")

    # Cross-cutting math invariants (both scenarios).
    for tag, res, rws, sm in (("HEB", result, rows, summ), ("Nike", result2, rows2, summ2)):
        scores = [r["score"] for r in rws]
        ok &= check(f"{tag}: winner has max score", sm["best_value"] == round(max(scores), 2))
        ok &= check(f"{tag}: score = reward - risk (each card)",
                    all(abs(r["score"] - (r["breakdown"]["reward"] + r["breakdown"]["risk"])) < 1e-9 for r in rws))
        ok &= check(f"{tag}: below_optimal = best - card (each)",
                    all(r["below_optimal"] == round(max(scores) - r["score"], 2) for r in rws))
        avg = sum(scores) / len(scores)
        ok &= check(f"{tag}: saved = best - average", sm["saved"] == round(max(scores) - avg, 2))
        ok &= check(f"{tag}: winner savings_vs_average == headline saved",
                    rws[0]["savings_vs_average"] == sm["saved"])

    print("\n" + ("ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
