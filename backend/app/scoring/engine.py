"""CreditPick scoring engine.

Pure Python: data in, data out. No framework imports, no database, no network,
no LLM calls. Every number is arithmetic you can point at -- if a judge asks
how a figure was produced, we trace it line by line.

Each card is scored in dollars:

    score = reward + float - risk

Scope note: the engine models only inputs that come from a real data source --
VectorMint reward rates and Nessie balances. Category caps, sign-up bonuses,
and purchase-protection terms are deliberately absent: no API publishes them,
and scoring on hand-entered figures would mean the output was driven by our own
assumptions rather than by data. The tradeoff is that `reward` is a straight
rate lookup; the modelling that remains is in `risk_term`, which prices
utilization damage in dollars instead of flagging it.
"""

from datetime import date

# --- tunable coefficients (no magic numbers inline) -------------------------

# Float: carrying the balance interest-free until it is actually due.
GRACE_DAYS = 21
FLOAT_APR = 0.05
DAYS_PER_YEAR = 365.0

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

# Utilization reports at statement close, not payment date. A card that closes
# well in the future can be paid down before it ever reports.
STATEMENT_FAR_DAYS = 20
STATEMENT_FAR_DISCOUNT = 0.3

# The same utilization damage costs a high scorer far more points than a low
# one: maxing out cards runs ~110-130 points off a ~790 profile but only ~30-50
# off a ~600 profile. Anchors for a linear interpolation, so the risk term
# scales with who the user actually is instead of assuming one profile.
SCORE_SENSITIVITY_ANCHORS = [(600.0, 40.0), (790.0, 120.0)]
REFERENCE_SCORE = 740.0
DEFAULT_BASELINE_SCORE = 740.0

# Disqualifiers.
MAX_UTIL_RATIO = 0.95
PROTECTION_MODE_UTIL = 0.30

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


def days_to_statement_close(card_state, today=None):
    """Days until this card's balance reports to the bureaus."""
    close = card_state.get("statement_close")
    if not close:
        return 0
    today = today or date.today()
    if isinstance(close, str):
        close = date.fromisoformat(close)
    return max(0, (close - today).days)


def float_term(card_state, amount, today=None):
    """Value of holding the money until the bill is actually due."""
    days_free = days_to_statement_close(card_state, today) + GRACE_DAYS
    return amount * FLOAT_APR * days_free / DAYS_PER_YEAR


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


def aggregate_utilization(state, exclude_id=None, extra=0.0):
    """Total balance over total limit across the whole wallet."""
    balance = 0.0
    limit = 0.0
    for card_id, card_state in state["cards"].items():
        card_limit = card_state.get("limit") or 0.0
        if card_limit <= 0:
            continue
        balance += card_state.get("balance", 0.0)
        limit += card_limit
        if card_id == exclude_id:
            balance += extra
    return (balance / limit) if limit > 0 else 0.0


def risk_term(card_state, amount, state, today=None, card_id=None):
    """Dollar-denominated cost of the FICO damage this purchase would do.

    The differentiator: utilization is priced, not merely flagged, so the
    engine can decline cash back to protect a score. Three inputs no rewards
    app combines -- the per-card step crossing, the aggregate step crossing,
    and how much a point is worth to this particular user.
    """
    limit = card_state.get("limit") or 0.0
    if limit <= 0:
        return 0.0
    balance = card_state.get("balance", 0.0)
    per_point = state.get("dollars_per_fico_point", 2.0)

    per_card = fico_cost((balance + amount) / limit) - fico_cost(balance / limit)

    old_aggregate = aggregate_utilization(state)
    new_aggregate = aggregate_utilization(state, exclude_id=card_id, extra=amount)
    aggregate = fico_cost(new_aggregate, AGGREGATE_FICO_STEPS) - fico_cost(
        old_aggregate, AGGREGATE_FICO_STEPS
    )

    sensitivity = score_sensitivity(state.get("baseline_score", DEFAULT_BASELINE_SCORE))
    penalty = (per_card + aggregate) * per_point * sensitivity

    if days_to_statement_close(card_state, today) > STATEMENT_FAR_DAYS:
        # Plenty of time to pay it down before it ever reports.
        penalty *= STATEMENT_FAR_DISCOUNT

    return penalty


# --- disqualifiers ---------------------------------------------------------


def disqualify(card_state, amount, state):
    """Reason this card cannot be used at all, or None.

    Checked before scoring. A disqualified card is excluded from ranking but
    still returned with its reason, so the UI can show why it was skipped
    rather than silently dropping it.
    """
    limit = card_state.get("limit") or 0.0
    if limit <= 0:
        return "no credit limit on record"

    projected = card_state.get("balance", 0.0) + amount
    if projected > limit * MAX_UTIL_RATIO:
        return "would exceed %d%% of limit" % int(MAX_UTIL_RATIO * 100)

    if state.get("protection_mode") and projected / limit > PROTECTION_MODE_UTIL:
        return "would push utilization over %d%% while protecting your score" % int(
            PROTECTION_MODE_UTIL * 100
        )

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


def score_card(card_id, card, card_state, amount, category, state, today=None):
    """Score one card in dollars, with every term broken out."""
    detail = reward_term(card, amount, category)
    float_value = float_term(card_state, amount, today)
    risk = risk_term(card_state, amount, state, today, card_id)

    detail.update({"float": float_value, "risk": risk})
    score = detail["reward"] + float_value - risk

    return {
        "card": card_id,
        "card_name": card["name"],
        "score": score,
        "reward_rate": detail["rate"],
        "estimated_value": detail["reward"],
        "breakdown": {
            "reward": detail["reward"],
            "float": float_value,
            "risk": -risk,
        },
        "why": build_why(detail, category),
        "detail": detail,
    }


def rank(state, category, amount, cards, today=None):
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
        reason = disqualify(card_state, amount, state)
        if reason:
            disqualified.append(
                {"card": card_id, "card_name": card["name"], "reason": reason}
            )
            continue
        scored.append(
            score_card(card_id, card, card_state, amount, category, state, today)
        )

    scored.sort(key=lambda r: r["score"], reverse=True)
    return {
        "category": category,
        "amount": amount,
        "all_cards": scored,
        "disqualified": disqualified,
    }
