"""Environment/settings loading."""

import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://user:password@localhost:5432/smartswipe"
)

NESSIE_API_KEY = os.getenv("NESSIE_API_KEY")
NESSIE_CUSTOMER_ID = os.getenv("NESSIE_CUSTOMER_ID")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
# "Rachel" — a public default ElevenLabs voice; override once the team picks one.
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
# eleven_monolingual_v1/eleven_multilingual_v1 are deprecated (ElevenLabs will
# 400 on them) — flash_v2_5 is fast and cheap, a good fit for a live demo.
ELEVENLABS_MODEL_ID = os.getenv("ELEVENLABS_MODEL_ID", "eleven_flash_v2_5")
VECTORMINT_API_KEY = os.getenv("VECTORMINT_API_KEY")
