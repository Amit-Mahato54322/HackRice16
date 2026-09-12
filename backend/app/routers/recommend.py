"""Recommend route.

M1 stub — returns the committed mock fixture. The real pipeline (Gemini
extraction, scoring engine, ElevenLabs audio) is wired in across M6-M8
(see docs/PLAN.md).
"""

from fastapi import APIRouter

from app.mock import load_mock

router = APIRouter(tags=["recommend"])


@router.post("/recommend")
def recommend():
    return load_mock("recommend.json")
