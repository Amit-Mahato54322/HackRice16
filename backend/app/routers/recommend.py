"""Recommend route.

The recommendation itself (`recommendation`, `ranked`) is still the frozen
M1 mock — the real scoring engine lands in M5/M7 (see docs/PLAN.md).

M8: the `voice` field is real. It calls ElevenLabs with the recommendation's
transcript and returns audio, shaped as
`{ transcript, audio: { url, mimeType } }` to match mobile-app's
VoiceOutput contract (mobile-app/src/services/contracts.ts) directly.

Falls back to the mock's placeholder audio if ELEVENLABS_API_KEY isn't set,
or if the ElevenLabs call fails, so /recommend never hard-depends on a
working vendor call.
"""

import logging
import uuid

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.config import ELEVENLABS_API_KEY
from app.mock import load_mock
from app.services.elevenlabs import synthesize_speech
from app.static_files import save_audio

logger = logging.getLogger(__name__)

router = APIRouter(tags=["recommend"])

# Fixed 30% threshold for the dashboard's utilization flag (docs/PLAN.md §7).
# This is a *display* threshold only -- the ranking prices utilization through
# the engine's risk term rather than flagging it.
UTILIZATION_FLAG_THRESHOLD = 0.30

def _build_voice(transcript: str, mock_audio: dict) -> dict:
    if not ELEVENLABS_API_KEY:
        return {"transcript": transcript, "audio": mock_audio}

    try:
        audio_bytes = synthesize_speech(transcript)
        url = save_audio(f"{uuid.uuid4()}.mp3", audio_bytes)
        return {"transcript": transcript, "audio": {"url": url, "mimeType": "audio/mpeg"}}
    except Exception:
        logger.exception("ElevenLabs synthesis failed, falling back to mock audio")
        return {"transcript": transcript, "audio": mock_audio}


@router.post("/recommend")
def recommend():
    fixture = load_mock("recommend.json")
    voice = _build_voice(fixture["voice"]["transcript"], fixture["voice"]["audio"])

    return {
        "merchant": fixture["merchant"],
        "amount": fixture["amount"],
        "category": fixture["category"],
        "recommendation": fixture["recommendation"],
        "ranked": fixture["ranked"],
        "voice": voice,
    }
