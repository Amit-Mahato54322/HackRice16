"""Response shapes for GET /portfolio."""

from pydantic import BaseModel


class CategorySaving(BaseModel):
    category: str
    count: int
    spent: float
    cashback: float
    saved: float


class TimelinePoint(BaseModel):
    date: str | None
    merchant: str | None
    saved: float
    cumulative_saved: float


class RecentTransaction(BaseModel):
    date: str | None
    merchant: str | None
    category: str
    amount: float
    card: str
    cashback: float
    saved: float


class PortfolioResponse(BaseModel):
    transaction_count: int
    total_spent: float
    total_cashback: float
    total_saved: float
    total_extra_cash: float
    avg_saved_per_txn: float
    by_category: list[CategorySaving]
    timeline: list[TimelinePoint]
    recent: list[RecentTransaction]
