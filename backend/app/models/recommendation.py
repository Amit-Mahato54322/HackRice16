from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String

from app.db import Base


class Recommendation(Base):
    """One recorded purchase decision. saved = chosen_value - average_value."""

    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    merchant = Column(String, nullable=True)
    category = Column(String, nullable=False)
    amount = Column(Float, nullable=False)

    chosen_card_key = Column(String, nullable=False)   # engine card id
    chosen_card_name = Column(String, nullable=False)
    chosen_value = Column(Float, nullable=False)        # net score (reward - risk)
    chosen_reward = Column(Float, nullable=False)       # cash back dollars only
    chosen_risk = Column(Float, nullable=False)         # utilization risk dollars

    next_best_card_name = Column(String, nullable=True)
    next_best_value = Column(Float, nullable=True)

    saved = Column(Float, nullable=False, default=0.0)       # vs next best
    extra_cash = Column(Float, nullable=False, default=0.0)  # vs next best, cash only
