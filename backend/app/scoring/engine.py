"""CreditPick scoring engine.

Pure Python: data in, data out. No framework imports, no database, no network,
no LLM calls. Every number is arithmetic you can point at -- if a judge asks
how a figure was produced, we trace it line by line.

The engine answers one question: of the cards you own, which should pay for
this purchase?

    maximize  reward
    subject to  resulting utilization <= the user's ceiling

Reward is a rate lookup. The interesting half is the constraint: a card that
would push utilization past the ceiling is refused no matter what it pays, so
the engine will hand back a 2% card in place of a 5% one. That is a trade no
rewards app makes.

The ceiling is a **user input**, not our estimate. An earlier version priced
utilization damage in dollars instead, which needed three sets of numbers no
source publishes -- FICO step thresholds, a dollar value per FICO point, and
how that scales with a starting score. Every one of those was an assumption
dressed as a measurement. A ceiling the user sets needs none of them: it is
their tolerance, applied to arithmetic on their real balances and limits.

Also absent, for the same reason: category caps, sign-up bonuses, purchase
protection (no API publishes cap usage or claim rates), and statement timing
(Nessie exposes no billing cycle).
"""

# --- tunable coefficients (no magic numbers inline) -------------------------

# A purchase that would take a card past this fraction of its limit is excluded
# regardless of any user ceiling: the charge is likely to be declined at the
# terminal, so recommending the card would be useless rather than expensive.
MAX_UTIL_RATIO = 0.95


# --- rates -----------------------------------------------------------------


def effective_rate(card, category):
    """Rate for this category in dollars per dollar spent, after point value."""
    return card["rates"].get(category, card["base_rate"]) * card["point_value"]


# --- utilization -----------------------------------------------------------


def projected_utilization(card_state, amount):
    """Where this card lands if the purchase goes on it. None if unknowable."""
    limit = card_state.get("limit") or 0.0
    if limit <= 0:
        return None
    return (card_state.get("balance", 0.0) + amount) / limit


# --- scoring ---------------------------------------------------------------


def reward_term(card, amount, category):
    """Reward value in dollars: rate x amount, at this card's point value.

    No cap handling. Category caps are real -- a 6% card with $50 of headroom
    left is not a 6% card -- but no API publishes cap sizes or usage, so
    modelling them would mean inventing the numbers. Consequence to state
    plainly: this figure is an upper bound for any capped card whose cap is
    already spent.
    """
    rate = card["rates"].get(category, card["base_rate"])
    return {
        "reward": amount * rate * card["point_value"],
        "rate": rate,
        "is_bonus_category": category in card["rates"],
    }


def disqualify(card_state, amount, ceiling=None):
    """Reason this card cannot be used, or None.

    Checked before scoring. A disqualified card is excluded from the ranking
    but still returned with its reason, so the UI can show what was skipped
    rather than silently dropping it.

    Nothing here is an estimate. A missing credit limit means utilization
    cannot be computed at all; 95% of the limit is where the charge starts
    getting declined; and the ceiling is whatever the user said it was.
    """
    utilization = projected_utilization(card_state, amount)
    if utilization is None:
        return "no credit limit on record"

    if utilization > MAX_UTIL_RATIO:
        return "would exceed %d%% of limit" % int(MAX_UTIL_RATIO * 100)

    if ceiling is not None and utilization > ceiling:
        return "would take utilization to %d%%, past your %d%% ceiling" % (
            round(utilization * 100),
            round(ceiling * 100),
        )

    return None


def build_why(detail, category):
    """One sentence naming the reason. The client owns all other formatting."""
    rate_pct = detail["rate"] * 100
    if detail["is_bonus_category"]:
        return "%.3g%% on %s" % (rate_pct, category)
    return "%.3g%% flat" % rate_pct


def score_card(card_id, card, card_state, amount, category):
    """Score one card in dollars, with the utilization it would land at."""
    detail = reward_term(card, amount, category)

    return {
        "card": card_id,
        "card_name": card["name"],
        "score": detail["reward"],
        "reward_rate": detail["rate"],
        "estimated_value": detail["reward"],
        "utilization": projected_utilization(card_state, amount),
        "breakdown": {"reward": detail["reward"]},
        "why": build_why(detail, category),
        "detail": detail,
    }


def rank(state, category, amount, cards):
    """Rank every eligible card for this purchase, best-paying first.

    `state["utilization_ceiling"]` is the user's tolerance, as a fraction.
    Absent or None means no ceiling beyond the hard decline limit.
    """
    ceiling = state.get("utilization_ceiling")
    scored = []
    disqualified = []

    for card_id, card_state in state["cards"].items():
        card = cards.get(card_id)
        if card is None:
            continue
        reason = disqualify(card_state, amount, ceiling)
        if reason:
            disqualified.append(
                {"card": card_id, "card_name": card["name"], "reason": reason}
            )
            continue
        scored.append(score_card(card_id, card, card_state, amount, category))

    scored.sort(key=lambda r: r["score"], reverse=True)
    return {
        "category": category,
        "amount": amount,
        "all_cards": scored,
        "disqualified": disqualified,
    }
