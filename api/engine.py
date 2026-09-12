"""CardPilot scoring engine.

Pure Python: data in, data out. No I/O beyond loading the card database,
no framework imports, no LLM calls. Every number is arithmetic you can
point at.

Build status: steps 1-2 (card db, wallet state, cap-aware reward term).
Sign-up bonus, protection, float and risk terms land in later steps.
"""

import json
import os
from datetime import date, timedelta

# --- tunable coefficients (no magic numbers inline) -------------------------

WARRANTY_COEF = 0.02
PURCHASE_COEF = 0.01
PRICE_COEF = 0.005
PROTECTION_MIN = 200

GRACE_DAYS = 21
FLOAT_APR = 0.05

FICO_STEPS = [(0.30, 0), (0.50, 8), (0.70, 15), (0.90, 25)]
MAX_UTIL_RATIO = 0.95
PROTECTION_MODE_UTIL = 0.30
STATEMENT_FAR_DAYS = 20
STATEMENT_FAR_DISCOUNT = 0.3

DEFAULT_CATEGORY = "other"

_DB_PATH = os.path.join(os.path.dirname(__file__), "data", "card_db.json")

MERCHANT_CATEGORIES = {
    "heb": "groceries",
    "kroger": "groceries",
    "whole foods": "groceries",
    "trader joes": "groceries",
    "shell": "gas",
    "exxon": "gas",
    "chevron": "gas",
    "united": "travel",
    "marriott": "travel",
    "delta": "travel",
    "chipotle": "dining",
    "torchys": "dining",
    "netflix": "streaming",
    "cvs": "drugstores",
    "best buy": "electronics",
    "apple store": "electronics",
}


def load_cards(path=_DB_PATH):
    with open(path) as f:
        return json.load(f)


def categorize(merchant):
    """Keyword lookup, deliberately dumb. Real MCC mapping is out of scope."""
    key = (merchant or "").strip().lower()
    if key in MERCHANT_CATEGORIES:
        return MERCHANT_CATEGORIES[key]
    for name, category in MERCHANT_CATEGORIES.items():
        if name in key:
            return category
    return DEFAULT_CATEGORY


def seed_wallet(today=None):
    """The demo wallet. Statement dates are relative so the demo never rots."""
    today = today or date.today()

    def close_in(days):
        return (today + timedelta(days=days)).isoformat()

    return {
        "dollars_per_fico_point": 2.0,
        "protection_mode": False,
        "cards": {
            # 6% groceries but only $50 of cap headroom left this year
            "amex_bcp": {
                "balance": 1240.00,
                "limit": 5000.00,
                "cap_used": {"groceries": 5950.00},
                "sub_progress": 0.00,
                "statement_close": close_in(16),
            },
            "citi_dc": {
                "balance": 900.00,
                "limit": 9000.00,
                "cap_used": {},
                "sub_progress": 0.00,
                "statement_close": close_in(3),
            },
            # deliberately loaded up: 68% utilization
            "freedom_flex": {
                "balance": 2040.00,
                "limit": 3000.00,
                "cap_used": {"groceries": 300.00},
                "sub_progress": 0.00,
                "statement_close": close_in(9),
            },
            "chase_sapphire_reserve": {
                "balance": 1800.00,
                "limit": 20000.00,
                "cap_used": {},
                "sub_progress": 0.00,
                "statement_close": close_in(25),
            },
            # active sign-up bonus: $750 on $4000, $800 in so far
            "venture_x": {
                "balance": 800.00,
                "limit": 15000.00,
                "cap_used": {},
                "sub_progress": 800.00,
                "statement_close": close_in(12),
            },
        },
    }


# --- scoring terms ---------------------------------------------------------


def reward_term(card, card_state, amount, category):
    """Cap-aware reward value in dollars.

    Dollars above the remaining category cap headroom earn the base rate,
    not the bonus rate. This split is the core of the engine.
    """
    bonus_rate = card["rates"].get(category, card["base_rate"])
    cap = card.get("caps", {}).get(category)

    if cap is None:
        bonus_part = amount
    else:
        used = card_state.get("cap_used", {}).get(category, 0.0)
        remaining = max(0.0, cap - used)
        bonus_part = min(amount, remaining)

    rest = amount - bonus_part
    reward = (bonus_part * bonus_rate + rest * card["base_rate"]) * card["point_value"]

    return {
        "reward": reward,
        "bonus_rate": bonus_rate,
        "bonus_part": bonus_part,
        "base_part": rest,
        "cap": cap,
        "cap_remaining": None if cap is None else max(0.0, cap - card_state.get("cap_used", {}).get(category, 0.0)),
    }


def score_card(card_id, card, card_state, amount, category, state):
    """Score one card. Only the reward term exists so far."""
    detail = reward_term(card, card_state, amount, category)
    score = detail["reward"]
    return {
        "card": card_id,
        "card_name": card["name"],
        "score": score,
        "breakdown": {
            "reward": detail["reward"],
            "protection": 0.0,
            "float": 0.0,
            "risk": 0.0,
        },
        "detail": detail,
    }


def rank(state, merchant, amount, cards=None, category=None):
    """Rank every card in the wallet for this purchase, best first."""
    cards = cards if cards is not None else load_cards()
    category = category or categorize(merchant)

    scored = [
        score_card(card_id, cards[card_id], card_state, amount, category, state)
        for card_id, card_state in state["cards"].items()
        if card_id in cards
    ]
    scored.sort(key=lambda r: r["score"], reverse=True)
    return {"category": category, "amount": amount, "all_cards": scored}
