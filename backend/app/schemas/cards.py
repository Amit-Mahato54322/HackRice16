from typing import Optional

from pydantic import BaseModel


class CardSearchResult(BaseModel):
    vectormint_card_id: str
    display_name: str
    issuer: str
    art_url: Optional[str] = None


class MapCardRequest(BaseModel):
    linked_account_id: int
    vectormint_card_id: str


class MapCardResponse(BaseModel):
    linked_account_id: int
    card_product_id: int
    display_name: str
    issuer: str
    is_configured: bool = True
