"""Bridge between the team's SQLAlchemy rows and the pure scoring engine.

The engine takes plain dicts and knows nothing about the database or Nessie.
Everything that translates between them lives here, so the engine stays
unit-testable with no server, no DB, and no network.

`credit_limit` is the one field Nessie does not provide that the engine needs:
the Nessie account object has no such field, and both disqualifiers divide by
it. It must be set locally per account. An account missing it is surfaced
rather than silently defaulted.
"""

from app.scoring import rewards


def build_wallet(accounts, catalog=None, utilization_ceiling=None):
    """Turn LinkedAccount rows into (cards, state) for the engine.

    Accounts are keyed by `linked_account_id` so two accounts mapped to the
    same card product stay distinct. Skipped, with a reason, when:

    - `card_product_id` is null -- synced but not mapped to a real card, so we
      have no reward data and will not guess one (docs/PLAN.md §4)
    - `credit_limit` is null or zero -- both disqualifiers divide by it

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
        "utilization_ceiling": utilization_ceiling,
        "cards": card_states,
    }
    return cards, state, skipped
