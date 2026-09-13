
"""VectorMint card-search and card-mapping routes (M4).

/cards/search proxies the VectorMint catalog (or the built-in fallback).
/cards/map links a linked_account to a card_product and caches the reward
JSON at this moment — never re-fetched per recommendation (docs/PLAN.md §5).
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.card_product import CardProduct
from app.models.linked_account import LinkedAccount
from app.schemas.cards import CardSearchResult, MapCardRequest, MapCardResponse
from app.services import vectormint

router = APIRouter(prefix="/cards", tags=["cards"])


@router.get("/search", response_model=list[CardSearchResult])
def search_cards(q: str = ""):
    return vectormint.search_cards(q)


@router.post("/map", response_model=MapCardResponse)
def map_card(body: MapCardRequest, db: Session = Depends(get_db)):
    account = db.query(LinkedAccount).filter_by(id=body.linked_account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="linked_account not found")

    card_data = vectormint.get_card(body.vectormint_card_id)
    if not card_data:
        raise HTTPException(status_code=404, detail="card not found in VectorMint catalog")

    # Upsert the card product, caching reward data now (not per recommendation)
    product = (
        db.query(CardProduct)
        .filter_by(vectormint_card_id=body.vectormint_card_id)
        .first()
    )
    if not product:
        product = CardProduct(
            vectormint_card_id=card_data["vectormint_card_id"],
            display_name=card_data["display_name"],
            issuer=card_data["issuer"],
            art_url=card_data.get("art_url"),
            cached_reward_json=card_data["rewards"],
            cached_at=datetime.now(timezone.utc),
        )
        db.add(product)
        db.flush()

    account.card_product_id = product.id
    db.commit()

    return MapCardResponse(
        linked_account_id=account.id,
        card_product_id=product.id,
        display_name=product.display_name,
        issuer=product.issuer,
    )
