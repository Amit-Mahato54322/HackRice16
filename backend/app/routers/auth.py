"""Auth routes.

M1 stub — returns the committed mock fixture. Real seeded-user verification
and JWT issuance land in M2 (see docs/PLAN.md).
"""

from fastapi import APIRouter

from app.mock import load_mock

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login():
    return load_mock("login.json")
