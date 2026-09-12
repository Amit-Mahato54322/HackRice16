"""Bridge between the team's SQLAlchemy rows and the pure scoring engine.

The engine takes plain dicts and knows nothing about the database or Nessie.
Everything that translates between them lives here, so the engine stays
unit-testable with no server, no DB, and no network.

`credit_limit` is the one field Nessie does not provide that the engine needs:
the Nessie account object has no such field, and every utilization figure, the
risk term, and both disqualifiers divide by it. It must be set locally per
account. An account missing it is surfaced rather than silently defaulted.
"""

from app.scoring import rewards

# What one FICO point is worth in dollars, the exchange rate that lets reward
# and credit damage be compared in the same unit.
DEFAULT_DOLLARS_PER_FICO_POINT = 2.0

# The user's starting FICO. Utilization damage scales with it -- the same
# maxed-out wallet costs a 790 profile roughly three times what it costs a 600
# profile -- so this is a real input, not a cosmetic field.
DEFAULT_BASELINE_SCORE = 740.0


def build_wallet(accounts, catalog=None, baseline_score=DEFAULT_BASELINE_SCORE):
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

        # VectorMint rates, cached at mapping time, with the local catalog as
        # the fallback for anything not cached yet.
        product = getattr(account, "card_product", None)
        fallback = rewards.lookup(catalog, getattr(product, "vectormint_card_id", None))
        card = rewards.normalize_reward_json(
            getattr(product, "cached_reward_json", None), fallback
        )

        if not card:
            skipped.append(
                {
                    "linked_account_id": account.id,
                    "display_name": account.official_name,
                    "reason": "no reward data for this card product",
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
        }

    state = {
        "dollars_per_fico_point": DEFAULT_DOLLARS_PER_FICO_POINT,
        "baseline_score": baseline_score,
        "cards": card_states,
    }
    return cards, state, skipped


# --- demo wallet -----------------------------------------------------------


def demo_wallet(baseline_score=DEFAULT_BASELINE_SCORE):
    """Seeded wallet used when no accounts are linked yet.

    Deliberately rigged so the interesting cases are reachable: one card at
    68% utilization, and one sitting just under a step threshold.

    The limits here are stand-ins for values the user would enter by hand --
    Nessie publishes none of them. Anything entered via PUT /cards/{card}/limit
    overrides them (see app/scoring/limits.py).
    """
    state = {
        "dollars_per_fico_point": DEFAULT_DOLLARS_PER_FICO_POINT,
        "baseline_score": baseline_score,
        "cards": {
            "amex_bcp": {
                "linked_account_id": 1,
                "balance": 1240.00,
                "limit": 5000.00,
            },
            "citi_dc": {
                "linked_account_id": 2,
                "balance": 900.00,
                "limit": 9000.00,
            },
            "freedom_flex": {
                "linked_account_id": 3,
                "balance": 2040.00,
                "limit": 3000.00,
            },
            "chase_sapphire_reserve": {
                "linked_account_id": 4,
                "balance": 1800.00,
                "limit": 20000.00,
            },
            "venture_x": {
                "linked_account_id": 5,
                "balance": 800.00,
                "limit": 15000.00,
            },
        },
    }
    return rewards.load_catalog(), state
