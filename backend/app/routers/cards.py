"""VectorMint card-search and card-mapping routes.

M1 stub — returns the committed mock fixtures. Real VectorMint catalog search
and reward-data caching land in M4 (see docs/PLAN.md).
"""

from fastapi import APIRouter

from app.mock import load_mock

router = APIRouter(prefix="/cards", tags=["cards"])


@router.get("/search")
def search_cards(q: str = ""):
    return load_mock("cards_search.json")


@router.post("/map")
def map_card():
    return load_mock("cards_map.json")
