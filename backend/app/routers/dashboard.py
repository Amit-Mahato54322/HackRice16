"""Dashboard route.

M1 stub — returns the committed mock fixture. Real Nessie-backed account data
lands in M3 (see docs/PLAN.md).
"""

from fastapi import APIRouter

from app.mock import load_mock

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
def get_dashboard():
    return load_mock("dashboard.json")
