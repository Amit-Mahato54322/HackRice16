"""Recommend route.

Wraps the scoring engine (app/scoring/engine.py). The response keeps every
field of the committed M1 fixture with its original meaning, so screens built
against backend/mock/recommend.json keep working; the scoring detail is added
alongside. See docs/PLAN.md §7.

Gemini audio extraction (M6) and ElevenLabs audio (M8) still land later; this
route currently takes merchant and amount as JSON.
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.mock import load_mock
from app.scoring import adapter, engine, limits
from app.scoring.categorize import categorize

router = APIRouter(tags=["recommend"])

# Fixed 30% threshold for the dashboard's utilization flag (docs/PLAN.md §7).
# Display only: it colours a row. What actually excludes a card is the user's
# own ceiling, passed per request as max_utilization.
UTILIZATION_FLAG_THRESHOLD = 0.30

AUDIO_PLACEHOLDER = "/mock/recommend-audio-placeholder"


class RecommendRequest(BaseModel):
    merchant: str = Field(..., examples=["HEB"])
    amount: float = Field(..., gt=0, examples=[80.0])
    # Nessie's merchant catalog supplies this during the real pipeline; it
    # overrides the keyword map when present (docs/PLAN.md §7 edge cases).
    category: str | None = None
    # The user's own utilization tolerance, as a fraction -- 0.3 for "keep me
    # under 30%". Any card the purchase would push past it is refused, however
    # well it pays. Omitted means no ceiling beyond the hard decline limit.
    max_utilization: float | None = Field(default=None, gt=0, le=1)


def _card_payload(scored, state):
    """One ranked card, in the M1 contract's shape plus the scoring detail."""
    card_state = state["cards"][scored["card"]]
    projected = scored["utilization"] or 0.0

    return {
        # --- M1 contract fields, unchanged ---
        "linked_account_id": card_state.get("linked_account_id"),
        "display_name": scored["card_name"],
        "reward_rate": scored["reward_rate"],
        "estimated_value": round(scored["estimated_value"], 2),
        "projected_utilization": round(projected, 4),
        "utilization_flag": projected > UTILIZATION_FLAG_THRESHOLD,
        "why": scored["why"],
        # --- added: the scoring detail behind the ranking ---
        "score": round(scored["score"], 2),
        "breakdown": {k: round(v, 2) for k, v in scored["breakdown"].items()},
    }


@router.post("/recommend")
def recommend(request: RecommendRequest):
    # Until /nessie/sync lands (M3) there are no LinkedAccount rows to read, so
    # this scores the seeded demo wallet. Swapping in adapter.build_wallet(...)
    # with real rows is the only change needed here.
    cards, state = adapter.demo_wallet(utilization_ceiling=request.max_utilization)

    # Credit limits are user-entered (PUT /cards/{card}/limit) because no API
    # in the stack publishes them. Anything entered overrides the seeded value.
    limits.apply(state)

    category = request.category or categorize(request.merchant)
    result = engine.rank(state, category, request.amount, cards)

    ranked = [_card_payload(card, state) for card in result["all_cards"]]

    disqualified = [
        {
            "linked_account_id": state["cards"][d["card"]].get("linked_account_id"),
            "display_name": d["card_name"],
            "reason": d["reason"],
        }
        for d in result["disqualified"]
    ]

    if not ranked:
        # Nothing usable -- say so plainly rather than failing silently
        # (docs/PLAN.md §7 edge cases). The fixture keeps the shape stable.
        payload = load_mock("recommend.json")
        payload.update(
            {
                "merchant": request.merchant,
                "amount": request.amount,
                "category": category,
                "recommendation": None,
                "ranked": [],
                "disqualified": disqualified,
            }
        )
        return payload

    return {
        "merchant": request.merchant,
        "amount": request.amount,
        "category": category,
        "recommendation": ranked[0],
        "runner_up": ranked[1] if len(ranked) > 1 else None,
        "ranked": ranked,
        "disqualified": disqualified,
        "audio_url": AUDIO_PLACEHOLDER,
    }
