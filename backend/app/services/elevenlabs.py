"""ElevenLabs text-to-speech client.

Thin wrapper around the ElevenLabs TTS REST API. The backend owns the vendor
credentials — the client never sees an ElevenLabs API key (see
mobile-app/ARCHITECTURE.md, "Voice / ElevenLabs").
"""

import httpx

from app.config import ELEVENLABS_API_KEY, ELEVENLABS_MODEL_ID, ELEVENLABS_VOICE_ID

TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"


def synthesize_speech(text: str) -> bytes:
    """Calls ElevenLabs TTS and returns raw MP3 bytes for the given text."""
    if not ELEVENLABS_API_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY is not set")

    response = httpx.post(
        TTS_URL.format(voice_id=ELEVENLABS_VOICE_ID),
        headers={
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
        json={"text": text, "model_id": ELEVENLABS_MODEL_ID},
        timeout=30.0,
    )
    response.raise_for_status()
    return response.content
