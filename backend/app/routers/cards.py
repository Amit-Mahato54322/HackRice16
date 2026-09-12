"""Card-search, card-mapping, and credit-limit routes.

Search and mapping are still M1 stubs returning the committed fixtures.

The credit-limit routes are live. Nessie's account object carries no credit
limit, so the user enters one per card; without it the engine cannot compute
utilization and disqualifies the card outright. See app/scoring/limits.py.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.mock import load_mock
from app.scoring import limits

router = APIRouter(prefix="/cards", tags=["cards"])


class CreditLimitRequest(BaseModel):
    limit: float = Field(..., gt=0, examples=[5000.0])


@router.get("/search")
def search_cards(q: str = ""):
    return load_mock("cards_search.json")


@router.post("/map")
def map_card():
    return load_mock("cards_map.json")


@router.get("/limits")
def get_limits():
    """Every credit limit entered so far, keyed by card."""
    return {"limits": limits.all_limits()}


@router.put("/{card_key}/limit")
def set_limit(card_key: str, request: CreditLimitRequest):
    """Enter the credit limit for one card.

    Manual by necessity: no API in the stack publishes it. The user reads it
    off their statement.
    """
    value = limits.set_limit(card_key, request.limit)
    if value is None:
        raise HTTPException(status_code=400, detail="Credit limit must be positive")
    return {"card": card_key, "limit": value}


@router.delete("/{card_key}/limit")
def clear_limit(card_key: str):
    """Forget an entered limit. The card is then excluded from scoring."""
    limits.set_limit(card_key, None)
    return {"card": card_key, "limit": None}
