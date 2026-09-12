"""CreditPick scoring engine.

Pure Python: data in, data out. No framework imports, no database, no network,
no LLM calls. Every number is arithmetic you can point at -- if a judge asks
how a figure was produced, we trace it line by line.

Each card is scored in dollars:

    score = reward + protection + float - opportunity - risk

`opportunity` is the piece no shipping rewards product models: consuming a
dollar of bonus-category cap headroom today removes it from a pot that future
spend would have used. See `shadow_prices` for how that price is derived.
"""

from datetime import date

# --- tunable coefficients (no magic numbers inline) -------------------------

# Purchase protection. Expected-value estimates (claim probability x payout),
# not derived from claims data. Calibratable, and stated as such in the pitch.
WARRANTY_COEF = 0.02
PURCHASE_COEF = 0.01
PRICE_COEF = 0.005
PROTECTION_MIN = 200.0

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


# --- cap bookkeeping -------------------------------------------------------
#
# A card has two kinds of cap. A plain `caps` entry caps one category on its
# own. A `cap_groups` entry is a single pot shared across several categories --
# how real rotating-category cards work, and the reason headroom is genuinely
# scarce rather than per-category free inventory. Both are addressed by a "cap
# key": for a plain cap the key is the category name, for a group it is the
# group name. `cap_used` is keyed the same way.


def cap_constraints(card):
    """Yield (cap_key, cap_dollars, [categories]) for every cap on the card."""
    for category, cap in (card.get("caps") or {}).items():
        yield category, cap, [category]
    for key, group in (card.get("cap_groups") or {}).items():
        yield key, group["cap"], list(group["categories"])


def cap_key_for(card, category):
    """Which cap constrains this category on this card, if any."""
    for key, _cap, categories in cap_constraints(card):
        if category in categories:
            return key
    return None


def cap_headroom(card, card_state, category):
    """Dollars of bonus-rate spend left for this category. None = uncapped."""
    key = cap_key_for(card, category)
    if key is None:
        return None
    caps = dict((k, c) for k, c, _ in cap_constraints(card))
    return max(0.0, caps[key] - (card_state.get("cap_used") or {}).get(key, 0.0))


def effective_rate(card, category):
    """Bonus rate for this category, in dollars per dollar spent."""
    return card["rates"].get(category, card["base_rate"]) * card["point_value"]


def base_effective_rate(card):
    return card["base_rate"] * card["point_value"]


# --- shadow pricing: what a dollar of cap headroom is actually worth --------


def blended_rate(card, card_state, category, category_spend):
    """Average rate a card would pay across a whole category's spend.

    A card with $50 of 6% headroom left is not a 6% card for $4,200 of
    projected groceries -- it is a 1% card with a rounding error attached.
    Same split as the reward term, applied to forecast spend instead of a
    single purchase, so alternatives are compared at the scale they'd serve.
    """
    headroom = cap_headroom(card, card_state, category)
    if headroom is None:
        return effective_rate(card, category)
    if category_spend <= 0:
        return base_effective_rate(card)
    bonus_part = min(category_spend, headroom)
    rest = category_spend - bonus_part
    earned = bonus_part * effective_rate(card, category) + rest * base_effective_rate(card)
    return earned / category_spend


def best_alternative_rate(cards, state, category, exclude_id, category_spend):
    """Best rate any *other* card can sustain across this category's spend."""
    best = 0.0
    for card_id, card in cards.items():
        if card_id == exclude_id:
            continue
        card_state = state["cards"].get(card_id)
        if card_state is None:
            continue
        best = max(best, blended_rate(card, card_state, category, category_spend))
    return best


def shadow_prices(cards, state):
    """Marginal value of one dollar of cap headroom, per (card_id, cap_key).

    This is the dual variable on each cap constraint. The allocation problem
    -- spread projected spend across cards to maximize reward, subject to caps
    -- decomposes per cap constraint, so the optimum is a greedy fill and the
    dual is exact. No LP solver required, and the arithmetic stays explainable.

    For each cap: rank the categories it covers by *advantage*, the rate this
    card pays over the best alternative. Fill headroom from the top. If
    projected spend exhausts the headroom, the price is the advantage of the
    marginal category -- the first one that does not fit. If headroom is never
    exhausted it is not scarce, and the price is zero.
    """
    spend = state.get("spend_profile") or {}
    prices = {}

    for card_id, card in cards.items():
        card_state = state["cards"].get(card_id)
        if card_state is None:
            continue

        for key, cap, categories in cap_constraints(card):
            headroom = max(0.0, cap - (card_state.get("cap_used") or {}).get(key, 0.0))
            if headroom <= 0:
                # Nothing left to protect; the reward term already drops to base.
                prices[(card_id, key)] = 0.0
                continue

            claims = []
            for category in categories:
                category_spend = spend.get(category, 0.0)
                advantage = effective_rate(card, category) - best_alternative_rate(
                    cards, state, category, card_id, category_spend
                )
                if advantage > 0:
                    claims.append((advantage, category_spend))
            claims.sort(reverse=True)

            filled = 0.0
            price = 0.0
            for advantage, category_spend in claims:
                if filled + category_spend >= headroom:
                    price = advantage
                    break
                filled += category_spend
            prices[(card_id, key)] = price

    return prices


# --- scoring terms ---------------------------------------------------------


def reward_term(card, card_state, amount, category):
    """Cap-aware reward value in dollars.

    Dollars above the remaining cap headroom earn the base rate, not the bonus
    rate. This split is the core of the engine.
    """
    bonus_rate = card["rates"].get(category, card["base_rate"])
    headroom = cap_headroom(card, card_state, category)

    bonus_part = amount if headroom is None else min(amount, headroom)
    rest = amount - bonus_part
    reward = (bonus_part * bonus_rate + rest * card["base_rate"]) * card["point_value"]

    return {
        "reward": reward,
        "bonus_rate": bonus_rate,
        "bonus_part": bonus_part,
        "base_part": rest,
        "cap_remaining": headroom,
    }


def sub_term(card, card_state, amount):
    """Sign-up bonus value earned by this purchase.

    While a minimum-spend requirement is open, every dollar toward it is worth
    far more than any category multiplier -- typically 15-25 cents, which
    correctly swamps a 6% category bonus.
    """
    sub = card.get("sub")
    if not sub:
        return 0.0, 0.0
    progress = card_state.get("sub_progress", 0.0)
    if progress >= sub["min_spend"]:
        return 0.0, 0.0
    rate = sub["value"] / sub["min_spend"]
    return amount * rate, rate


def opportunity_term(card, card_id, category, bonus_part, prices):
    """Cost of consuming scarce cap headroom that is worth more elsewhere.

    Spending bonus-rate dollars today removes them from a pot that future
    spend in other categories would have used. Charging that displaced value
    against the purchase is what lets the engine decline a headline rate.
    """
    key = cap_key_for(card, category)
    if key is None:
        return 0.0, 0.0
    price = prices.get((card_id, key), 0.0)
    return bonus_part * price, price


def protection_term(card, amount):
    """Expected value of purchase protection, meaningful only on big tickets."""
    if amount <= PROTECTION_MIN:
        return 0.0
    p = card.get("protection") or {}
    return (
        p.get("warranty_years", 0) * amount * WARRANTY_COEF
        + bool(p.get("purchase_protection")) * amount * PURCHASE_COEF
        + bool(p.get("price_protection")) * amount * PRICE_COEF
    )


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
    engine can decline cash back to protect a score. Two components -- the
    per-card step crossing, plus a weighted aggregate-utilization crossing,
    because FICO looks at both.
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

    sensitivity = score_sensitivity(
        state.get("baseline_score", DEFAULT_BASELINE_SCORE)
    )
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


def build_why(card, detail, amount):
    """One sentence naming the tradeoff. The client owns all other formatting."""
    rate_pct = detail["bonus_rate"] * 100
    base_pct = card["base_rate"] * 100

    if detail["bonus_part"] <= 0:
        why = "%.3g%% flat" % base_pct
    elif detail["base_part"] > 0:
        why = "%.3g%% on the first $%.0f, then %.3g%% -- category cap is nearly spent" % (
            rate_pct,
            detail["bonus_part"],
            base_pct,
        )
    elif detail["bonus_rate"] > card["base_rate"]:
        why = "%.3g%% category rate" % rate_pct
    else:
        why = "%.3g%% flat, no cap" % base_pct

    if detail.get("sub_rate", 0) > 0:
        why += ", plus %.0f cents per dollar toward the sign-up bonus" % (
            detail["sub_rate"] * 100
        )

    if detail.get("opportunity", 0) > 0.005:
        why += " -- but that cap is worth %.0f cents more per dollar elsewhere, so it nets %.3g%%" % (
            detail["headroom_price"] * 100,
            (detail["bonus_rate"] - detail["headroom_price"]) * 100,
        )

    if detail.get("protection", 0) > 0.005:
        why += "; %d-year extended warranty on a $%.0f purchase" % (
            (card.get("protection") or {}).get("warranty_years", 0),
            amount,
        )

    if detail.get("risk", 0) > 0.005:
        why += "; utilization damage costs $%.2f" % detail["risk"]

    return why


# --- scoring ---------------------------------------------------------------


def score_card(card_id, card, card_state, amount, category, state, prices, today=None):
    """Score one card in dollars, with every term broken out."""
    detail = reward_term(card, card_state, amount, category)
    sub_value, sub_rate = sub_term(card, card_state, amount)
    opportunity, price = opportunity_term(
        card, card_id, category, detail["bonus_part"], prices
    )
    protection = protection_term(card, amount)
    float_value = float_term(card_state, amount, today)
    risk = risk_term(card_state, amount, state, today, card_id)

    reward = detail["reward"] + sub_value
    score = reward + protection + float_value - opportunity - risk

    detail.update(
        {
            "sub_value": sub_value,
            "sub_rate": sub_rate,
            "opportunity": opportunity,
            "headroom_price": price,
            "protection": protection,
            "float": float_value,
            "risk": risk,
        }
    )

    return {
        "card": card_id,
        "card_name": card["name"],
        "score": score,
        "reward_rate": detail["bonus_rate"],
        "estimated_value": reward,
        "breakdown": {
            "reward": reward,
            "opportunity": -opportunity,
            "protection": protection,
            "float": float_value,
            "risk": -risk,
        },
        "why": build_why(card, detail, amount),
        "detail": detail,
    }


def rank(state, category, amount, cards, today=None):
    """Rank every card in the wallet for this purchase, best first.

    Returns eligible cards sorted by score, plus the disqualified ones with
    their reasons so the UI can show what was skipped and why.
    """
    prices = shadow_prices(cards, state)
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
            score_card(card_id, card, card_state, amount, category, state, prices, today)
        )

    scored.sort(key=lambda r: r["score"], reverse=True)
    return {
        "category": category,
        "amount": amount,
        "all_cards": scored,
        "disqualified": disqualified,
    }
