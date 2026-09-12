"""Recommend route.

M7: `/recommend` is wired to the real scoring engine (`app/scoring/`) instead
of the M1 mock. It builds the caller's wallet from their real `linked_accounts`
(via `adapter.build_wallet`), overlays any user-entered credit limits, and
ranks every eligible card with `engine.rank`. If nothing is mapped to a real
card product yet (card-mapping is still M4, not done), it falls back to
`adapter.demo_wallet()` so `/recommend` still runs on real engine logic
instead of returning canned mock data.

M8: the `voice` field calls ElevenLabs with the top card's real `why` string
and returns audio, shaped as `{ transcript, audio: { url, mimeType } }` to
match mobile-app's VoiceOutput contract (mobile-app/src/services/contracts.ts)
directly. Falls back to a placeholder if ELEVENLABS_API_KEY isn't set, or if
the call fails, so /recommend never hard-depends on a working vendor call.
"""

import logging
import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from app.config import ELEVENLABS_API_KEY
from app.db import get_db
from app.models.linked_account import LinkedAccount
from app.scoring import adapter, engine, limits
from app.scoring.categorize import categorize
from app.services.elevenlabs import synthesize_speech
from app.static_files import save_audio

logger = logging.getLogger(__name__)

router = APIRouter(tags=["recommend"])

DEMO_USER_ID = 1  # replaced by JWT auth in M2 (deferred, see docs/PLAN.md)

FALLBACK_AUDIO = {"url": "/mock/recommend-audio-placeholder.mp3", "mimeType": "audio/mpeg"}


class RecommendRequest(BaseModel):
    merchant: str = ""
    amount: float = Field(..., gt=0)
    category: str | None = None  # inferred from merchant when omitted


def _load_wallet(db: Session):
    """The caller's real wallet, or the seeded demo wallet if nothing's mapped yet."""
    accounts = (
        db.query(LinkedAccount)
        .options(joinedload(LinkedAccount.card_product))
        .filter_by(user_id=DEMO_USER_ID)
        .all()
    )
    cards, state, skipped = adapter.build_wallet(accounts)
    if cards:
        return cards, state, skipped
    # No accounts mapped to a real card product yet (M4) — run on the demo
    # wallet so the engine still produces a real, computed ranking.
    cards, state = adapter.demo_wallet()
    return cards, state, []


def _build_voice(transcript: str) -> dict:
    if not ELEVENLABS_API_KEY:
        return {"transcript": transcript, "audio": FALLBACK_AUDIO}

    try:
        audio_bytes = synthesize_speech(transcript)
        url = save_audio(f"{uuid.uuid4()}.mp3", audio_bytes)
        return {"transcript": transcript, "audio": {"url": url, "mimeType": "audio/mpeg"}}
    except Exception:
        logger.exception("ElevenLabs synthesis failed, falling back to placeholder audio")
        return {"transcript": transcript, "audio": FALLBACK_AUDIO}


def _card_out(scored: dict) -> dict:
    return {
        "card_id": scored["card"],
        "display_name": scored["card_name"],
        "reward_rate": scored["reward_rate"],
        "estimated_value": scored["estimated_value"],
        "score": scored["score"],
        "breakdown": scored["breakdown"],
        "why": scored["why"],
    }


@router.post("/recommend")
def recommend(request: RecommendRequest, db: Session = Depends(get_db)):
    category = request.category or categorize(request.merchant)

    cards, state, skipped = _load_wallet(db)
    limits.apply(state)
    result = engine.rank(state, category, request.amount, cards)

    all_cards = result["all_cards"]
    top = all_cards[0] if all_cards else None
    transcript = (
        f"Use {top['card_name']}. {top['why']}."
        if top
        else "None of your cards can cover this purchase right now."
    )

    return {
        "merchant": request.merchant,
        "amount": request.amount,
        "category": category,
        "recommendation": _card_out(top) if top else None,
        "ranked": [_card_out(c) for c in all_cards[1:]],
        "disqualified": result["disqualified"] + skipped,
        "voice": _build_voice(transcript),
    }
