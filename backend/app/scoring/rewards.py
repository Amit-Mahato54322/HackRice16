"""Card reward data: the local catalog and the VectorMint normalizer.

Two sources, in that order of preference:

1. **VectorMint** (`GET /v1/cards/{id}/rewards`), cached on
   `CardProduct.cached_reward_json` at mapping time. Its reward rules are
   normalized here into the shape the engine expects.
2. **`card_db.json`**, a small local catalog used when nothing has been cached
   yet. Hand-entered, and only figures an issuer publishes on its own product
   page.

Scope note: VectorMint's reward rules carry no machine-readable spending cap,
and its welcome offers are deliberately not read. Category caps and sign-up
bonuses are out of the model by decision -- see engine.py.
"""

import json
from pathlib import Path

_DB_PATH = Path(__file__).resolve().parent / "card_db.json"

# VectorMint states the unit on every rule, e.g.
#   {"category_id": "dining", "rate": 3, "unit": "points_per_dollar"}
# so the convention is read per rule rather than assumed globally. Both units
# below are stored the same way -- as a fraction of the dollar spent -- with
# point_value carrying the cents-per-point conversion.
POINTS_PER_DOLLAR = "points_per_dollar"
PERCENT_UNITS = {"percent", "percent_cash_back", "percentage"}

# Category ids VectorMint uses for the "everything else" rule.
BASE_CATEGORY_IDS = {"other", "all", "everything", "general", "base"}

# No consumer card pays more than this on a category; anything above it means
# the payload was misread rather than that the card is extraordinary.
MAX_PLAUSIBLE_RATE = 0.30

DEFAULT_BASE_RATE = 0.01
DEFAULT_POINT_VALUE = 1.0


def load_catalog(path=_DB_PATH):
    """Card id -> {name, annual_fee, point_value, base_rate, rates}."""
    with open(path) as f:
        return json.load(f)


def lookup(catalog, card_key):
    """One card's local reward data, or None when the key is unknown."""
    if not card_key:
        return None
    return catalog.get(card_key)


def _as_rate(value, unit):
    """Convert one VectorMint rule to a fraction of the dollar spent.

    `3 points_per_dollar` and `3 percent` both store as 0.03; what separates
    them is point_value, the cents each point is worth.
    """
    value = float(value)
    unit = (unit or "").strip().lower()

    if unit == POINTS_PER_DOLLAR or unit in PERCENT_UNITS:
        return value / 100.0
    # Unknown unit: fall back on magnitude. A rule expressed as 0.03 is already
    # a fraction; one expressed as 3 is not.
    return value / 100.0 if value > 1.0 else value


def normalize_reward_json(cached, fallback=None):
    """Turn a cached VectorMint payload into the shape the engine expects.

    Accepts the documented `reward_rules` list, and tolerates a bare mapping of
    category -> rate for hand-built fixtures. A payload that yields no usable
    rule falls back to the local catalog entry rather than silently scoring the
    card at the wrong rate.

    point_value is not something VectorMint publishes -- what a point is worth
    depends on how the holder redeems it -- so it comes from the local catalog.
    """
    fallback = fallback or {}
    if not cached:
        return fallback or None

    rules = cached.get("reward_rules") or cached.get("rates") or cached.get("categories")

    # app/services/vectormint.py hands back a flat {category: rate} mapping
    # rather than a nested rule list, so treat the payload itself as the
    # mapping when it holds no rule collection but does hold numbers.
    if not rules and all(
        isinstance(value, (int, float)) for value in cached.values()
    ):
        rules = cached

    rates = {}
    base_rate = None

    if isinstance(rules, dict):
        parsed = [(k, v, None) for k, v in rules.items()]
    elif isinstance(rules, list):
        parsed = [
            (
                rule.get("category_id") or rule.get("category") or rule.get("name"),
                rule.get("rate") if rule.get("rate") is not None else rule.get("multiplier"),
                rule.get("unit"),
            )
            for rule in rules
            if isinstance(rule, dict)
        ]
    else:
        parsed = []

    for category, value, unit in parsed:
        if not category or value is None:
            continue
        rate = _as_rate(value, unit)
        if rate > MAX_PLAUSIBLE_RATE:
            continue
        category = str(category).strip().lower()
        if category in BASE_CATEGORY_IDS:
            base_rate = rate
        else:
            rates[category] = rate

    if not rates and base_rate is None:
        return fallback or None

    if base_rate is None:
        base_rate = fallback.get("base_rate", DEFAULT_BASE_RATE)

    annual_fee = cached.get("annual_fee")
    if annual_fee is None:
        annual_fee = fallback.get("annual_fee", 0)

    return {
        "name": (
            cached.get("official_name")
            or cached.get("name")
            or fallback.get("name")
            or "Card"
        ),
        "annual_fee": annual_fee,
        "point_value": fallback.get("point_value", DEFAULT_POINT_VALUE),
        "base_rate": base_rate,
        "rates": rates,
    }
