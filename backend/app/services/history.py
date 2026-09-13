"""Persist and fetch Recommendation rows."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.recommendation import Recommendation


def record(
    db: Session,
    *,
    user_id: int,
    merchant: str | None,
    category: str,
    amount: float,
    chosen: dict,
    summary: dict,
    created_at: datetime | None = None,
) -> Recommendation:
    """Save one decision. `chosen` = winning card, `summary` = savings.summary()."""
    breakdown = chosen.get("breakdown", {})
    row = Recommendation(
        user_id=user_id,
        merchant=merchant,
        category=category,
        amount=amount,
        chosen_card_key=str(chosen["card"]),
        chosen_card_name=chosen["card_name"],
        chosen_value=round(chosen["score"], 2),
        chosen_reward=round(breakdown.get("reward", chosen.get("estimated_value", 0.0)), 2),
        chosen_risk=round(breakdown.get("risk", 0.0), 2),
        next_best_card_name=summary.get("next_best_card_name"),
        next_best_value=summary.get("next_best_value"),
        saved=summary.get("saved", 0.0),
        extra_cash=summary.get("extra_cash", 0.0),
    )
    if created_at is not None:
        row.created_at = created_at
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_for_user(db: Session, user_id: int) -> list[Recommendation]:
    """All recorded decisions for a user, oldest first (portfolio order)."""
    return (
        db.query(Recommendation)
        .filter_by(user_id=user_id)
        .order_by(Recommendation.created_at.asc(), Recommendation.id.asc())
        .all()
    )


def clear_for_user(db: Session, user_id: int) -> int:
    """Delete a user's history. Returns count."""
    n = db.query(Recommendation).filter_by(user_id=user_id).delete()
    db.commit()
    return n
