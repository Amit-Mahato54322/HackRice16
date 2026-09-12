from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db import Base


class LinkedAccount(Base):
    """A Nessie-synced credit account, optionally mapped to a real CardProduct.

    card_product_id = null means "synced but not yet mapped to a real card" —
    excluded from scoring, shown on the dashboard as "not configured"
    (see docs/PLAN.md §4).

    credit_limit is seeded once by scripts/seed_nessie.py — Nessie does not
    store this field (confirmed by API test). current_balance is synced live
    from Nessie on every POST /nessie/sync call.
    """

    __tablename__ = "linked_accounts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    nessie_account_id = Column(String, unique=True, nullable=False)
    nessie_customer_id = Column(String, nullable=False)
    official_name = Column(String, nullable=True)
    mask = Column(String, nullable=True)
    credit_limit = Column(Float, nullable=True)
    current_balance = Column(Float, nullable=True)
    last_synced_at = Column(DateTime, nullable=True)
    card_product_id = Column(Integer, ForeignKey("card_products.id"), nullable=True)

    card_product = relationship("CardProduct", backref="linked_accounts")
