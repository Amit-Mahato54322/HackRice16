"""Loads committed backend/mock/*.json fixtures for M1 stub route handlers.

Serving the fixture file directly (rather than hand-typing an equivalent dict
in each route) guarantees the live stub response and the frontend's mock data
never drift apart — see docs/PLAN.md M1.
"""

import json
from pathlib import Path

MOCK_DIR = Path(__file__).resolve().parent.parent / "mock"


def load_mock(filename: str):
    with open(MOCK_DIR / filename) as f:
        return json.load(f)
