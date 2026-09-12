"""Recommend route.

Wraps the scoring engine (app/scoring/engine.py). The response keeps every
field of the committed M1 fixture with its original meaning, so screens built
against backend/mock/recommend.json keep working; the scoring detail is added
alongside. See docs/PLAN.md §7.

Gemini audio extraction (M6) and ElevenLabs audio (M8) still land later; this
route currently takes merchant and amount as JSON.
"""

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from app import timeseries
from app.db import get_db
from app.models.linked_account import LinkedAccount
from app.scoring import adapter, engine, limits
from app.scoring.categorize import categorize

logger = logging.getLogger(__name__)

router = APIRouter(tags=["recommend"])

DEMO_USER_ID = 1  # replaced by JWT auth in M2

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
def recommend(request: RecommendRequest, db: Session = Depends(get_db)):
    accounts = (
        db.query(LinkedAccount)
        .options(joinedload(LinkedAccount.card_product))
        .filter_by(user_id=DEMO_USER_ID)
        .all()
    )
    cards, state, skipped = adapter.build_wallet(
        accounts, utilization_ceiling=request.max_utilization
    )

    # Credit limits are user-entered (PUT /cards/{card}/limit) because no API
    # in the stack publishes them; seed_nessie.py sets an initial value.
    limits.apply(state)

    category = request.category or categorize(request.merchant)
    result = engine.rank(state, category, request.amount, cards)

    ranked = [_card_payload(card, state) for card in result["all_cards"]]

    # Accounts the engine could not score at all -- not mapped to a card
    # product, or no reward data for the one they are mapped to -- are listed
    # alongside the ones it scored and refused, so nothing vanishes silently.
    disqualified = skipped + [
        {
            "linked_account_id": state["cards"][d["card"]].get("linked_account_id"),
            "display_name": d["card_name"],
            "reason": d["reason"],
        }
        for d in result["disqualified"]
    ]

    # Log what was answered and the inputs behind it, so a recommendation
    # someone questions later can be reconstructed exactly. Never let this
    # fail the request -- the user still needs their answer.
    chosen = ranked[0] if ranked else None
    try:
        timeseries.record_recommendation(
            user_id=DEMO_USER_ID,
            merchant=request.merchant,
            category=category,
            amount=request.amount,
            chosen_account_id=chosen["linked_account_id"] if chosen else None,
            reward_rate=chosen["reward_rate"] if chosen else None,
            score=chosen["score"] if chosen else None,
            utilization=chosen["projected_utilization"] if chosen else None,
            ceiling=request.max_utilization,
        )
    except Exception as exc:  # noqa: BLE001 - telemetry must not break the route
        logger.warning("recommendation not logged: %s", exc)

    return {
        "merchant": request.merchant,
        "amount": request.amount,
        "category": category,
        "recommendation": chosen,
        "runner_up": ranked[1] if len(ranked) > 1 else None,
        "ranked": ranked,
        "disqualified": disqualified,
        "audio_url": AUDIO_PLACEHOLDER,
    }
