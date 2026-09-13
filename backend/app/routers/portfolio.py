"""Savings portfolio route."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.portfolio import PortfolioResponse
from app.services import history, portfolio

router = APIRouter(tags=["portfolio"])

DEMO_USER_ID = 1  # replaced by JWT auth in M2 (deferred, see docs/PLAN.md)


@router.get("/portfolio", response_model=PortfolioResponse)
def get_portfolio(db: Session = Depends(get_db)):
    """Savings totals, per-category, timeline, and recent activity."""
    rows = history.list_for_user(db, DEMO_USER_ID)
    return portfolio.summarize(rows)
