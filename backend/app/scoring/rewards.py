"""The card catalog: reward rates, base rates, point values.

Nessie is the only external API in the stack. It supplies balances, purchase
history, and merchant categories -- but no reward rates, and its `rewards`
field is a flat points balance rather than a rate per category. So rates live
here, hand-entered for the demo cards, read from `card_db.json`.

This is the one piece of hand-maintained data the engine scores on, and it is
deliberately narrow: only figures a card issuer publishes on its own product
page and that anyone can verify in a minute. Category caps, sign-up bonuses and
purchase-protection terms are *not* here -- those were removed because
modelling them meant inventing usage and claim figures no source publishes.

Scaling this to 200 cards is data entry, not modelling. That is the honest
limitation to state.
"""

import json
from pathlib import Path

_DB_PATH = Path(__file__).resolve().parent / "card_db.json"


def load_catalog(path=_DB_PATH):
    """Card id -> {name, annual_fee, point_value, base_rate, rates}."""
    with open(path) as f:
        return json.load(f)


def lookup(catalog, card_key):
    """One card's reward data, or None when the key is not in the catalog."""
    if not card_key:
        return None
    return catalog.get(card_key)
