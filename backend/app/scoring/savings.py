"""Savings math on a ranked result.

  value / score = net dollars (reward - risk); highest = use first
  below_optimal = best score - this card
  saved         = best score - average score (per purchase)
"""

from __future__ import annotations


def _reward(scored: dict) -> float:
    """Cash-back dollars for a scored card, before the risk term."""
    return scored.get("estimated_value", scored.get("breakdown", {}).get("reward", 0.0))


def utilization(card_state: dict, amount: float) -> dict:
    """This card's utilization now, and after the purchase."""
    limit = card_state.get("limit") or 0.0
    balance = card_state.get("balance", 0.0)
    if limit <= 0:
        return {"current_pct": None, "projected_pct": None}
    return {
        "current_pct": round(balance / limit * 100, 1),
        "projected_pct": round((balance + amount) / limit * 100, 1),
    }


def annotate(result: dict, state: dict, amount: float) -> list[dict]:
    """Add priority, balances, utilization, and savings to each ranked card."""
    cards = result.get("all_cards", [])
    if not cards:
        return []

    best = cards[0]
    best_value = best["score"]
    best_reward = _reward(best)
    card_states = state.get("cards", {})
    avg_value = sum(c["score"] for c in cards) / len(cards)

    annotated = []
    for position, scored in enumerate(cards, start=1):
        cs = card_states.get(scored["card"], {})
        balance = cs.get("balance", 0.0)
        util = utilization(cs, amount)
        gap = round(best_value - scored["score"], 2)
        annotated.append(
            {
                **scored,
                "priority": position,
                "balance_now": round(balance, 2),
                "balance_after": round(balance + amount, 2),
                "current_utilization": util["current_pct"],
                "projected_utilization": util["projected_pct"],
                "is_best": scored is best,
                "below_optimal": gap,
                "savings_vs_average": round(scored["score"] - avg_value, 2),
                "saved_vs_this": gap,  # same number, kept for mobile contract
                "extra_cash_vs_this": round(best_reward - _reward(scored), 2),
            }
        )
    return annotated


def summary(result: dict) -> dict | None:
    """Headline savings for one purchase (best vs average), or None if empty."""
    cards = result.get("all_cards", [])
    if not cards:
        return None

    best = cards[0]
    worst = cards[-1]
    second = cards[1] if len(cards) > 1 else None

    count = len(cards)
    avg_value = sum(c["score"] for c in cards) / count
    avg_reward = sum(_reward(c) for c in cards) / count

    return {
        "best_card": best["card"],
        "best_card_name": best["card_name"],
        "best_value": round(best["score"], 2),
        "best_reward": round(_reward(best), 2),
        "average_value": round(avg_value, 2),
        "saved": round(best["score"] - avg_value, 2),
        "extra_cash": round(_reward(best) - avg_reward, 2),
        "next_best_card_name": second["card_name"] if second else None,
        "next_best_value": round(second["score"], 2) if second else None,
        "saved_vs_next_best": round(best["score"] - second["score"], 2) if second else 0.0,
        "saved_vs_worst": round(best["score"] - worst["score"], 2),
        "worst_card_name": worst["card_name"],
        "eligible_count": count,
    }
