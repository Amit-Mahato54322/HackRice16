"""Bridge between the team's SQLAlchemy rows and the pure scoring engine.

The engine takes plain dicts and knows nothing about the database, Nessie, or
VectorMint. Everything that translates between them lives here, so the engine
stays unit-testable with no server, no DB, and no network.
"""

from datetime import date, timedelta

from app.scoring import rewards

DEFAULT_DOLLARS_PER_FICO_POINT = 2.0
# "Buying a house in 12 months" -- the engine will give up cash back to protect
# the score at this exchange rate.
PROTECTION_MODE_DOLLARS_PER_FICO_POINT = 50.0

# The user's starting FICO. Utilization damage scales with it -- the same
# maxed-out wallet costs a 790 profile roughly three times what it costs a 600
# profile -- so this is a real input, not a cosmetic field.
DEFAULT_BASELINE_SCORE = 740.0


def build_wallet(
    accounts,
    catalog=None,
    protection_mode=False,
    baseline_score=DEFAULT_BASELINE_SCORE,
):
    """Turn LinkedAccount rows into (cards, state) for the engine.

    Accounts are keyed by `linked_account_id` so two accounts mapped to the
    same card product stay distinct. Skipped, with a reason, when:

    - `card_product_id` is null -- synced but not mapped to a real card, so we
      have no reward data and will not guess one (docs/PLAN.md §4)
    - `credit_limit` is null or zero -- every utilization figure, the risk
      penalty, and both disqualifiers divide by it

    Returns (cards, state, skipped).
    """
    catalog = catalog if catalog is not None else rewards.load_catalog()
    cards = {}
    card_states = {}
    skipped = []

    for account in accounts:
        key = str(account.id)

        if getattr(account, "card_product_id", None) is None:
            skipped.append(
                {
                    "linked_account_id": account.id,
                    "display_name": account.official_name,
                    "reason": "not configured -- map it to a card product first",
                }
            )
            continue

        product = getattr(account, "card_product", None)
        catalog_key = getattr(product, "vectormint_card_id", None)
        fallback = catalog.get(catalog_key, {}) if catalog_key else {}
        card = rewards.normalize_reward_json(
            getattr(product, "cached_reward_json", None), fallback
        )

        if not card:
            skipped.append(
                {
                    "linked_account_id": account.id,
                    "display_name": account.official_name,
                    "reason": "no reward data cached for this card product",
                }
            )
            continue

        card = dict(card)
        card["name"] = (
            getattr(product, "display_name", None)
            or account.official_name
            or card.get("name", "Card")
        )
        cards[key] = card

        card_states[key] = {
            "linked_account_id": account.id,
            "balance": float(account.current_balance or 0.0),
            "limit": float(account.credit_limit or 0.0),
            # Neither of these comes from Nessie -- both are set locally per
            # account. See the module docstring.
            "statement_close": getattr(account, "statement_close", None),
        }

    state = {
        "dollars_per_fico_point": (
            PROTECTION_MODE_DOLLARS_PER_FICO_POINT
            if protection_mode
            else DEFAULT_DOLLARS_PER_FICO_POINT
        ),
        "protection_mode": protection_mode,
        "baseline_score": baseline_score,
        "cards": card_states,
    }
    return cards, state, skipped


# --- demo wallet -----------------------------------------------------------


def demo_wallet(today=None, protection_mode=False, baseline_score=DEFAULT_BASELINE_SCORE):
    """Seeded wallet used when no accounts are linked yet.

    Deliberately rigged so the interesting cases are reachable: one card at
    68% utilization, one just under a step threshold, and a spread of statement
    dates. Dates are relative to today so the demo never rots.
    """
    today = today or date.today()

    def close_in(days):
        return (today + timedelta(days=days)).isoformat()

    state = {
        "dollars_per_fico_point": (
            PROTECTION_MODE_DOLLARS_PER_FICO_POINT
            if protection_mode
            else DEFAULT_DOLLARS_PER_FICO_POINT
        ),
        "protection_mode": protection_mode,
        "baseline_score": baseline_score,
        "cards": {
            "amex_bcp": {
                "linked_account_id": 1,
                "balance": 1240.00,
                "limit": 5000.00,
                "statement_close": close_in(16),
            },
            "citi_dc": {
                "linked_account_id": 2,
                "balance": 900.00,
                "limit": 9000.00,
                "statement_close": close_in(3),
            },
            "freedom_flex": {
                "linked_account_id": 3,
                "balance": 2040.00,
                "limit": 3000.00,
                "statement_close": close_in(9),
            },
            "chase_sapphire_reserve": {
                "linked_account_id": 4,
                "balance": 1800.00,
                "limit": 20000.00,
                "statement_close": close_in(25),
            },
            "venture_x": {
                "linked_account_id": 5,
                "balance": 800.00,
                "limit": 15000.00,
                "statement_close": close_in(12),
            },
        },
    }
    return rewards.load_catalog(), state
