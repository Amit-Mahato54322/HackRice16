"""Local static storage for generated ElevenLabs speech clips.

Files written here are served back to the client at AUDIO_URL_PREFIX by the
StaticFiles mount in main.py — see docs/PLAN.md M8 and
mobile-app/src/services/contracts.ts (VoiceOutput.audio.url).
"""

from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
AUDIO_DIR = STATIC_DIR / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

AUDIO_URL_PREFIX = "/static/audio"


def save_audio(filename: str, data: bytes) -> str:
    """Writes an audio clip to disk and returns its public URL."""
    (AUDIO_DIR / filename).write_bytes(data)
    return f"{AUDIO_URL_PREFIX}/{filename}"
