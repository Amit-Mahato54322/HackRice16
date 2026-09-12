"""VectorMint API client (https://www.vectormint.app/docs).

Real API only — VECTORMINT_API_KEY required in .env.

Normalization notes:
- VectorMint expresses rates as multipliers in a reward currency
  (e.g. Venture travel = 5x capital-one-miles). We convert to an effective
  decimal rate: rate x currency estimated_point_value_usd
  (5 x $0.01 = 0.05 = 5% back), which is what the scoring engine consumes.
- Their category ids use dashes (online-shopping); we normalize to
  underscores. "general-purchases" becomes our "base" rate.
- The GET /cards/{id} detail endpoint 400s ("Card ID parameter is required")
  as of 2026-09-12, so we cache the full card list (which embeds
  reward_rules) and resolve single cards locally. Also quota-friendly:
  ~3 requests total per process for the whole 212-card catalog.
"""

import httpx

from app.config import VECTORMINT_API_KEY

VECTORMINT_BASE = "https://api.vectormint.app/v1"

# Module-level caches — populated once per process
_cards_by_id: dict[str, dict] | None = None
_currency_values: dict[str, float] | None = None


def _headers() -> dict:
    if not VECTORMINT_API_KEY:
        raise RuntimeError("VECTORMINT_API_KEY is not set in .env")
    return {"Authorization": f"Bearer {VECTORMINT_API_KEY}"}


def _get(path: str, params: dict | None = None) -> dict:
    res = httpx.get(f"{VECTORMINT_BASE}{path}", params=params, headers=_headers(), timeout=20)
    res.raise_for_status()
    return res.json()


def _load_currencies() -> dict[str, float]:
    global _currency_values
    if _currency_values is None:
        data = _get("/reward-currencies")["data"]
        _currency_values = {
            c["id"]: c.get("estimated_point_value_usd") or 0.01 for c in data
        }
    return _currency_values


def _load_catalog() -> dict[str, dict]:
    global _cards_by_id
    if _cards_by_id is None:
        _cards_by_id = {}
        page = 1
        while True:
            body = _get("/cards", params={"page": page, "limit": 100})
            for card in body["data"]:
                _cards_by_id[card["id"]] = card
            if page * 100 >= body["meta"]["total"]:
                break
            page += 1
    return _cards_by_id


def _normalize_category(category_id: str) -> str:
    if category_id == "general-purchases":
        return "base"
    return category_id.replace("-", "_")


def _normalize_card(card: dict) -> dict:
    """VectorMint card -> our internal shape with effective decimal rates."""
    currencies = _load_currencies()
    rewards: dict[str, float] = {}
    for rule in card.get("reward_rules", []):
        category = _normalize_category(rule["category_id"])
        point_value = currencies.get(rule["reward_currency_id"], 0.01)
        effective_rate = round(rule["rate"] * point_value, 4)
        # Keep the best rate if multiple rules hit the same category
        if effective_rate > rewards.get(category, 0.0):
            rewards[category] = effective_rate

    return {
        "vectormint_card_id": card["id"],
        "display_name": card["name"],
        "issuer": card["issuer_id"].replace("-", " ").title(),
        "art_url": None,
        "annual_fee": card.get("annual_fee"),
        "rewards": rewards,
        # VectorMint has no merchant-level offer endpoint in the catalog data;
        # merchant offers were a fallback-era concept. Scoring uses
        # category rates + base until a real offer source exists.
        "merchant_offers": {},
    }


def search_cards(q: str) -> list[dict]:
    """Relevance-ranked search. Empty q returns the full catalog."""
    if not q:
        return [_normalize_card(c) for c in _load_catalog().values()]

    body = _get("/cards/search", params={"q": q})
    catalog = _load_catalog()
    results = []
    for hit in body["data"]:
        # Search results are summaries without reward_rules — resolve
        # each hit against the cached full catalog.
        full = catalog.get(hit["id"])
        if full:
            results.append(_normalize_card(full))
    return results


def get_card(vectormint_card_id: str) -> dict | None:
    card = _load_catalog().get(vectormint_card_id)
    return _normalize_card(card) if card else None
