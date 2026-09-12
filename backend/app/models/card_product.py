from sqlalchemy import Column, DateTime, Integer, JSON, String

from app.db import Base


class CardProduct(Base):
    """A real card product from the VectorMint catalog, cached at mapping time."""

    __tablename__ = "card_products"

    id = Column(Integer, primary_key=True)
    vectormint_card_id = Column(String, unique=True, nullable=False)
    display_name = Column(String, nullable=False)
    issuer = Column(String, nullable=False)
    art_url = Column(String, nullable=True)
    cached_reward_json = Column(JSON, nullable=True)
    cached_at = Column(DateTime, nullable=True)
