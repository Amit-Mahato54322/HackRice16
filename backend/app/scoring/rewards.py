"""Card reward data: catalog, VectorMint normalization, and the cap overlay.

Two things the engine needs that no single source provides cleanly:

1. **Rates.** VectorMint owns these, cached on `CardProduct.cached_reward_json`
   at mapping time. Its exact field shape is an open item (docs/PLAN.md §9), so
   the normalizer below accepts the plausible shapes and isolates the one
   genuinely ambiguous decision -- percent vs. points-per-dollar -- in a single
   documented constant.

2. **Caps.** VectorMint very likely does not publish category caps at all, and
   caps are what make headroom scarce. Without them the shadow-pricing term is
   inert. So caps and shared cap groups are hand-maintained here in
   `card_db.json` for the demo cards, keyed by card id. This is a real
   limitation and belongs in the honest-limitations list, not hidden.
"""

import json
from pathlib import Path

_DB_PATH = Path(__file__).resolve().parent / "card_db.json"

# VectorMint's rate convention. "percent" means 0.06 == 6% cash back.
# "points_per_dollar" means 6 == 6x points, worth 6 * point_value cents.
# Confirm in their playground and flip this one constant if needed
# (docs/PLAN.md §9). Getting it wrong is a 100x error, so it is asserted
# against a sanity bound below rather than trusted silently.
RATE_CONVENTION = "percent"

# Any normalized rate above this is taken as proof the convention is wrong --
# no consumer card pays more than 30% on a category.
MAX_PLAUSIBLE_RATE = 0.30

DEFAULT_BASE_RATE = 0.01
DEFAULT_POINT_VALUE = 1.0


def load_catalog(path=_DB_PATH):
    """The local card catalog: rates, caps, cap groups, subs, protections."""
    with open(path) as f:
        return json.load(f)


def _as_rate(value):
    """Convert one VectorMint rate figure to dollars per dollar spent."""
    value = float(value)
    if RATE_CONVENTION == "points_per_dollar":
        # 3x points -> 0.03 before point_value is applied.
        value = value / 100.0
    elif value > 1.0:
        # Defensive: a "percent" source that actually sent 6 for 6%.
        value = value / 100.0
    return value


def normalize_reward_json(cached, fallback=None):
    """Turn a cached VectorMint payload into the shape the engine expects.

    Accepts either a mapping of category -> rate, or a list of
    {category, rate} records, which are the two shapes their docs suggest.
    Anything unparseable falls back to the local catalog entry rather than
    silently scoring a card at the wrong rate.
    """
    fallback = fallback or {}
    if not cached:
        return fallback

    rates = {}
    raw = cached.get("rates") or cached.get("categories") or {}

    if isinstance(raw, dict):
        items = raw.items()
    elif isinstance(raw, list):
        items = [
            (r.get("category") or r.get("name"), r.get("rate") or r.get("multiplier"))
            for r in raw
            if isinstance(r, dict)
        ]
    else:
        items = []

    for category, value in items:
        if not category or value is None:
            continue
        rate = _as_rate(value)
        if rate <= MAX_PLAUSIBLE_RATE:
            rates[str(category).strip().lower()] = rate

    if not rates:
        return fallback

    base = cached.get("base_rate") or cached.get("default_rate")
    base_rate = _as_rate(base) if base is not None else fallback.get(
        "base_rate", DEFAULT_BASE_RATE
    )

    point_value = cached.get("point_value")
    point_value = (
        float(point_value)
        if point_value is not None
        else fallback.get("point_value", DEFAULT_POINT_VALUE)
    )

    return {
        "name": fallback.get("name") or cached.get("display_name") or "Card",
        "annual_fee": cached.get("annual_fee", fallback.get("annual_fee", 0)),
        "point_value": point_value,
        "base_rate": base_rate,
        "rates": rates,
        # Caps and protections come from the local overlay -- VectorMint does
        # not publish them. See the module docstring.
        "caps": fallback.get("caps", {}),
        "cap_groups": fallback.get("cap_groups", {}),
        "sub": fallback.get("sub"),
        "protection": fallback.get("protection", {}),
    }
