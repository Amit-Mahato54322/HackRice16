"""CreditPick scoring engine.

Pure Python: data in, data out. 

Each card is scored in dollars:

    score = reward - risk


Statement timing is absent for the same reason: Nessie exposes no statement
close date or billing cycle, so the float term and the "pay it down before it
reports" discount both ran on dates we made up.

The tradeoff is that `reward` is a straight rate lookup. The modelling that
remains is `risk_term`, which prices utilization damage in dollars instead of
flagging it -- which is still a trade no rewards app makes.
"""

# --- tunable coefficients (no magic numbers inline) -------------------------

# FICO damage from utilization is not linear; it steps at thresholds.
#
# The breakpoints sit just *under* the round numbers -- 28.9% rather than 30%
# -- which matters: a card at 29.5% has already crossed. Reported consistently
# by practitioners (myFICO); FICO does not publish them, so these are
# well-sourced folklore rather than peer-reviewed figures.
PER_CARD_FICO_STEPS = [(0.289, 0), (0.489, 8), (0.689, 15), (0.889, 25)]

# FICO scores per-card *and* overall utilization, and the aggregate figure has
# an extra low breakpoint at 8.9% that per-card does not. Aggregate damage is
# the larger of the two effects, so the magnitudes live here rather than in a
# separate weighting constant.
AGGREGATE_FICO_STEPS = [(0.089, 0), (0.289, 10), (0.489, 25), (0.689, 45), (0.889, 70)]

# The same utilization damage costs a high scorer far more points than a low
# one: maxing out cards runs ~110-130 points off a ~790 profile but only ~30-50
# off a ~600 profile. Anchors for a linear interpolation, so the risk term
# scales with who the user actually is instead of assuming one profile.
SCORE_SENSITIVITY_ANCHORS = [(600.0, 40.0), (790.0, 120.0)]
REFERENCE_SCORE = 740.0
DEFAULT_BASELINE_SCORE = 740.0

# A purchase that would take a card past this fraction of its limit is
# excluded: the charge is likely to be declined at the terminal, so
# recommending the card would be useless rather than merely expensive.
MAX_UTIL_RATIO = 0.95

DEFAULT_CATEGORY = "other"


# --- rates -----------------------------------------------------------------


def effective_rate(card, category):
    """Rate for this category, in dollars per dollar spent."""
    return card["rates"].get(category, card["base_rate"]) * card["point_value"]


def base_effective_rate(card):
    return card["base_rate"] * card["point_value"]


# --- scoring terms ---------------------------------------------------------


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


def fico_cost(util, steps=None):
    """FICO points lost at this utilization. A step function, not a curve.

    Every source treats utilization as thresholds rather than a smooth curve,
    so this deliberately does not interpolate.
    """
    cost = 0
    for threshold, points in steps or PER_CARD_FICO_STEPS:
        if util >= threshold:
            cost = points
    return cost


def score_sensitivity(baseline_score):
    """How much one utilization step costs *this* user, relative to average.

    Linear interpolation between the anchor profiles, clamped outside them.
    Returns a multiplier on the point costs, 1.0 at the reference score.
    """
    (low_score, low_damage), (high_score, high_damage) = SCORE_SENSITIVITY_ANCHORS

    def damage(score):
        score = max(low_score, min(high_score, float(score)))
        span = high_score - low_score
        return low_damage + (score - low_score) / span * (high_damage - low_damage)

    return damage(baseline_score) / damage(REFERENCE_SCORE)


def aggregate_utilization(state, charge_id=None, extra=0.0):
    """Total balance over total limit across the whole wallet.

    If charge_id is given, `extra` is added to that card's balance (models
    the purchase landing on it).
    """
    balance = 0.0
    limit = 0.0
    for card_id, card_state in state["cards"].items():
        card_limit = card_state.get("limit") or 0.0
        if card_limit <= 0:
            continue
        balance += card_state.get("balance", 0.0)
        limit += card_limit
        if card_id == charge_id:
            balance += extra
    return (balance / limit) if limit > 0 else 0.0


def risk_term(card_state, amount, state, card_id=None):
    """Dollar-denominated cost of the FICO damage this purchase would do.

    The differentiator: utilization is priced, not merely flagged, so the
    engine can decline cash back to protect a score. Three inputs no rewards
    app combines -- the per-card step crossing, the aggregate step crossing,
    and how much a point is worth to this particular user, which scales with
    their baseline score.
    """
    limit = card_state.get("limit") or 0.0
    if limit <= 0:
        return 0.0
    balance = card_state.get("balance", 0.0)
    per_point = state.get("dollars_per_fico_point", 2.0)

    per_card = fico_cost((balance + amount) / limit) - fico_cost(balance / limit)

    old_aggregate = aggregate_utilization(state)
    new_aggregate = aggregate_utilization(state, charge_id=card_id, extra=amount)
    aggregate = fico_cost(new_aggregate, AGGREGATE_FICO_STEPS) - fico_cost(
        old_aggregate, AGGREGATE_FICO_STEPS
    )

    sensitivity = score_sensitivity(state.get("baseline_score", DEFAULT_BASELINE_SCORE))
    return (per_card + aggregate) * per_point * sensitivity


# --- disqualifiers ---------------------------------------------------------


def disqualify(card_state, amount):
    """Reason this card cannot be used at all, or None.

    Checked before scoring. A disqualified card is excluded from ranking but
    still returned with its reason, so the UI can show why it was skipped
    rather than silently dropping it.

    Neither reason is a judgment call: a missing credit limit means utilization
    cannot be computed at all, and a charge past 95% of the limit is likely to
    be declined at the terminal. Nothing is excluded for being merely
    expensive -- that is what the risk term is for.
    """
    limit = card_state.get("limit") or 0.0
    if limit <= 0:
        return "no credit limit on record"

    projected = card_state.get("balance", 0.0) + amount
    if projected > limit * MAX_UTIL_RATIO:
        return "would exceed %d%% of limit" % int(MAX_UTIL_RATIO * 100)

    return None


# --- explanation -----------------------------------------------------------


def build_why(detail, category):
    """One sentence naming the tradeoff. The client owns all other formatting."""
    rate_pct = detail["rate"] * 100

    if detail["is_bonus_category"]:
        why = "%.3g%% on %s" % (rate_pct, category)
    else:
        why = "%.3g%% flat" % rate_pct

    if detail.get("risk", 0) > 0.005:
        why += "; utilization damage costs $%.2f" % detail["risk"]

    return why


# --- scoring ---------------------------------------------------------------


def score_card(card_id, card, card_state, amount, category, state):
    """Score one card in dollars, with every term broken out."""
    detail = reward_term(card, amount, category)
    risk = risk_term(card_state, amount, state, card_id)

    detail["risk"] = risk
    score = detail["reward"] - risk

    return {
        "card": card_id,
        "card_name": card["name"],
        "score": score,
        "reward_rate": detail["rate"],
        "estimated_value": detail["reward"],
        "breakdown": {
            "reward": detail["reward"],
            "risk": -risk or 0.0,  # avoid -0.0
        },
        "why": build_why(detail, category),
        "detail": detail,
    }


def rank(state, category, amount, cards):
    """Rank every card in the wallet for this purchase, best first.

    Returns eligible cards sorted by score, plus the disqualified ones with
    their reasons so the UI can show what was skipped and why.
    """
    scored = []
    disqualified = []

    for card_id, card_state in state["cards"].items():
        card = cards.get(card_id)
        if card is None:
            continue
        reason = disqualify(card_state, amount)
        if reason:
            disqualified.append(
                {"card": card_id, "card_name": card["name"], "reason": reason}
            )
            continue
        scored.append(score_card(card_id, card, card_state, amount, category, state))

    def _projected_util(scored_card):
        cs = state["cards"].get(scored_card["card"], {})
        limit = cs.get("limit") or 0.0
        if limit <= 0:
            return 1.0  # unknown limit -> least preferred on a tie
        return (cs.get("balance", 0.0) + amount) / limit

    # Tie on score -> prefer lower projected utilization.
    scored.sort(key=lambda r: (round(r["score"], 2), -_projected_util(r)), reverse=True)
    return {
        "category": category,
        "amount": amount,
        "all_cards": scored,
        "disqualified": disqualified,
    }
