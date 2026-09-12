"""Bridge between the team's SQLAlchemy rows and the pure scoring engine.

The engine takes plain dicts and knows nothing about the database, Nessie, or
VectorMint. Everything that translates between them lives here, so the engine
stays unit-testable with no server, no DB, and no network.
"""

from datetime import date, timedelta

from app.scoring import rewards

# Projected remaining spend per category over the cap period. Shadow pricing
# needs a forecast -- without one, cap headroom has no scarcity and the whole
# term collapses to zero. M10's Nessie purchase-history aggregation replaces
# these constants with real per-customer figures; until then they are the
# documented demo profile.
DEFAULT_SPEND_PROFILE = {
    "groceries": 4200.0,
    "dining": 3000.0,
    "gas": 1500.0,
    "drugstores": 600.0,
    "travel": 2500.0,
    "streaming": 300.0,
    "other": 6000.0,
}

DEFAULT_DOLLARS_PER_FICO_POINT = 2.0
# "Buying a house in 12 months" -- the engine will give up cash back to protect
# the score at this exchange rate.
PROTECTION_MODE_DOLLARS_PER_FICO_POINT = 50.0

# The user's starting FICO. Utilization damage scales with it -- the same
# maxed-out wallet costs a 790 profile roughly three times what it costs a 600
# profile -- so this is a real input, not a cosmetic field.
DEFAULT_BASELINE_SCORE = 740.0


def spend_profile_from_purchases(purchases):
    """Aggregate Nessie purchase history into a forward spend forecast.

    Nessie's history is short, so this extrapolates observed spend rather than
    pretending to forecast. Falls back to the demo profile when history is too
    thin to be meaningful.
    """
    if not purchases:
        return dict(DEFAULT_SPEND_PROFILE)

    totals = {}
    for purchase in purchases:
        category = purchase.get("category") or "other"
        totals[category] = totals.get(category, 0.0) + float(purchase.get("amount", 0.0))

    if not totals:
        return dict(DEFAULT_SPEND_PROFILE)

    profile = dict(DEFAULT_SPEND_PROFILE)
    profile.update(totals)
    return profile


def build_wallet(
    accounts,
    catalog=None,
    spend_profile=None,
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
            # Nessie has no cap-usage concept; these come from purchase history
            # aggregation once M3 lands, and from committed purchases meanwhile.
            "cap_used": dict(getattr(account, "cap_used", None) or {}),
            "sub_progress": float(getattr(account, "sub_progress", 0.0) or 0.0),
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
        "spend_profile": spend_profile or dict(DEFAULT_SPEND_PROFILE),
        "cards": card_states,
    }
    return cards, state, skipped


# --- demo wallet -----------------------------------------------------------


def demo_wallet(today=None, protection_mode=False, baseline_score=DEFAULT_BASELINE_SCORE):
    """Seeded wallet used when no accounts are linked yet.

    Deliberately rigged so the interesting cases are reachable: one card with
    $50 of grocery cap left, one rotating card whose shared 5% pot is nearly
    spent, one at 68% utilization, one with an open sign-up bonus.
    Statement dates are relative to today so the demo never rots.
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
        "spend_profile": dict(DEFAULT_SPEND_PROFILE),
        "cards": {
            "amex_bcp": {
                "linked_account_id": 1,
                "balance": 1240.00,
                "limit": 5000.00,
                "cap_used": {"groceries": 5950.00},
                "sub_progress": 0.0,
                "statement_close": close_in(16),
            },
            "citi_dc": {
                "linked_account_id": 2,
                "balance": 900.00,
                "limit": 9000.00,
                "cap_used": {},
                "sub_progress": 0.0,
                "statement_close": close_in(3),
            },
            "freedom_flex": {
                "linked_account_id": 3,
                "balance": 2040.00,
                "limit": 3000.00,
                "cap_used": {"rotating": 300.00},
                "sub_progress": 0.0,
                "statement_close": close_in(9),
            },
            "chase_sapphire_reserve": {
                "linked_account_id": 4,
                "balance": 1800.00,
                "limit": 20000.00,
                "cap_used": {},
                "sub_progress": 0.0,
                "statement_close": close_in(25),
            },
            "venture_x": {
                "linked_account_id": 5,
                "balance": 800.00,
                "limit": 15000.00,
                "cap_used": {},
                # Bonus already earned. An *open* sign-up bonus is worth ~19
                # cents per dollar, which correctly beats every other term on
                # every purchase -- true, but it makes one card win every query
                # and hides the rest of the engine. Set this to 800.0 to demo
                # sign-up-bonus dominance as its own beat.
                "sub_progress": 4000.00,
                "statement_close": close_in(12),
            },
        },
    }
    return rewards.load_catalog(), state
