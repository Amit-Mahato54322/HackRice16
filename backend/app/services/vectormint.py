"""VectorMint catalog client.

If VECTORMINT_API_KEY is set, calls the live API (endpoint shapes to be
confirmed against their docs — see docs/PLAN.md §9). If not, falls back to
a built-in catalog so /cards/search and /cards/map work end-to-end today.
The fallback also de-risks the live demo if VectorMint is unreachable.

Reward rates are dollar-value multipliers per dollar spent
(e.g. 0.04 = 4% back equivalent). "base" is the fallback rate for any
category not listed (see scoring formula, docs/PLAN.md §7).
"""

import httpx

from app.config import VECTORMINT_API_KEY

VECTORMINT_BASE = "https://api.vectormint.com/v1"

FALLBACK_CATALOG = [
    {
        "vectormint_card_id": "fallback-chase-sapphire-preferred",
        "display_name": "Chase Sapphire Preferred",
        "issuer": "Chase",
        "art_url": None,
        "rewards": {"base": 0.01, "dining": 0.03, "travel": 0.02, "groceries": 0.03, "streaming": 0.03},
    },
    {
        "vectormint_card_id": "fallback-capital-one-venture",
        "display_name": "Capital One Venture Rewards",
        "issuer": "Capital One",
        "art_url": None,
        "rewards": {"base": 0.02, "travel": 0.05},
    },
    {
        "vectormint_card_id": "fallback-bofa-customized-cash",
        "display_name": "Bank of America Customized Cash Rewards",
        "issuer": "Bank of America",
        "art_url": None,
        "rewards": {"base": 0.01, "gas": 0.03, "online_shopping": 0.03, "groceries": 0.02},
    },
    {
        "vectormint_card_id": "fallback-amex-gold",
        "display_name": "American Express Gold",
        "issuer": "American Express",
        "art_url": None,
        "rewards": {"base": 0.01, "dining": 0.04, "groceries": 0.04},
    },
    {
        "vectormint_card_id": "fallback-citi-double-cash",
        "display_name": "Citi Double Cash",
        "issuer": "Citi",
        "art_url": None,
        "rewards": {"base": 0.02},
    },
    {
        "vectormint_card_id": "fallback-discover-it",
        "display_name": "Discover it Cash Back",
        "issuer": "Discover",
        "art_url": None,
        "rewards": {"base": 0.01, "rotating": 0.05},
    },
    {
        "vectormint_card_id": "fallback-amazon-prime-visa",
        "display_name": "Amazon Prime Rewards Visa",
        "issuer": "Chase",
        "art_url": None,
        "rewards": {"base": 0.01, "online_shopping": 0.05, "groceries": 0.02, "gas": 0.02, "dining": 0.02},
    },
    {
        "vectormint_card_id": "fallback-wells-fargo-active-cash",
        "display_name": "Wells Fargo Active Cash",
        "issuer": "Wells Fargo",
        "art_url": None,
        "rewards": {"base": 0.02},
    },
]


def _live() -> bool:
    return bool(VECTORMINT_API_KEY)


def search_cards(q: str) -> list[dict]:
    """Search the catalog by card name or issuer."""
    if _live():
        res = httpx.get(
            f"{VECTORMINT_BASE}/cards",
            params={"q": q},
            headers={"Authorization": f"Bearer {VECTORMINT_API_KEY}"},
        )
        res.raise_for_status()
        return res.json()

    q_lower = q.lower()
    return [
        c for c in FALLBACK_CATALOG
        if q_lower in c["display_name"].lower() or q_lower in c["issuer"].lower()
    ]


def get_card(vectormint_card_id: str) -> dict | None:
    """Fetch one card with full reward data (cached into card_products on map)."""
    if _live():
        res = httpx.get(
            f"{VECTORMINT_BASE}/cards/{vectormint_card_id}",
            headers={"Authorization": f"Bearer {VECTORMINT_API_KEY}"},
        )
        res.raise_for_status()
        return res.json()

    return next(
        (c for c in FALLBACK_CATALOG if c["vectormint_card_id"] == vectormint_card_id),
        None,
    )
