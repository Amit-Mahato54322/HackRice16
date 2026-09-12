from pydantic import BaseModel
from typing import Optional


class DashboardCard(BaseModel):
    id: int
    nessie_account_id: str
    official_name: str
    credit_limit: float
    current_balance: float
    amount_used: float
    amount_remaining: float
    utilization_pct: float
    is_configured: bool
    card_display_name: Optional[str] = None
    card_issuer: Optional[str] = None
    # Identify the product so the client can pick its artwork and colours.
    vectormint_card_id: Optional[str] = None
    card_art_url: Optional[str] = None

    class Config:
        from_attributes = True


class DashboardResponse(BaseModel):
    cards: list[DashboardCard]
