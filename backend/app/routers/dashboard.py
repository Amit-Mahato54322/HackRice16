from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.models.linked_account import LinkedAccount
from app.schemas.dashboard import DashboardCard, DashboardResponse

router = APIRouter(tags=["dashboard"])

DEMO_USER_ID = 1  # replaced by JWT auth in M2


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(db: Session = Depends(get_db)):
    accounts = (
        db.query(LinkedAccount)
        .options(joinedload(LinkedAccount.card_product))
        .filter_by(user_id=DEMO_USER_ID)
        .all()
    )

    cards = []
    for acct in accounts:
        limit = acct.credit_limit or 0.0
        balance = acct.current_balance or 0.0
        remaining = max(limit - balance, 0.0)
        utilization = round(balance / limit * 100, 1) if limit else 0.0

        cards.append(DashboardCard(
            id=acct.id,
            nessie_account_id=acct.nessie_account_id,
            official_name=acct.official_name or "Unknown",
            credit_limit=limit,
            current_balance=balance,
            amount_used=balance,
            amount_remaining=remaining,
            utilization_pct=utilization,
            is_configured=acct.card_product_id is not None,
            card_display_name=acct.card_product.display_name if acct.card_product else None,
            card_issuer=acct.card_product.issuer if acct.card_product else None,
            vectormint_card_id=(
                acct.card_product.vectormint_card_id if acct.card_product else None
            ),
            card_art_url=acct.card_product.art_url if acct.card_product else None,
        ))

    return DashboardResponse(cards=cards)
