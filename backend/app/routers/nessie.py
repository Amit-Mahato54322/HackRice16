import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import timeseries
from app.config import NESSIE_CUSTOMER_ID
from app.db import get_db
from app.models.linked_account import LinkedAccount
from app.services import nessie as nessie_svc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/nessie", tags=["nessie"])

DEMO_USER_ID = 1  # replaced by JWT auth in M2


@router.post("/sync")
def sync_accounts(db: Session = Depends(get_db)):
    """Fetch live balances from Nessie and upsert into linked_accounts.

    credit_limit is never touched here — it was seeded once by seed_nessie.py
    and never changes (Nessie doesn't support the field; we own it).
    """
    if not NESSIE_CUSTOMER_ID:
        raise HTTPException(status_code=500, detail="NESSIE_CUSTOMER_ID not set in .env")

    accounts = nessie_svc.get_customer_accounts(NESSIE_CUSTOMER_ID)
    synced = []

    for acct in accounts:
        nessie_id = acct["_id"]
        balance = float(acct.get("balance", 0))
        now = datetime.now(timezone.utc)

        row = db.query(LinkedAccount).filter_by(nessie_account_id=nessie_id).first()
        if row:
            row.current_balance = balance
            row.last_synced_at = now
        else:
            db.add(LinkedAccount(
                user_id=DEMO_USER_ID,
                nessie_account_id=nessie_id,
                nessie_customer_id=NESSIE_CUSTOMER_ID,
                official_name=acct.get("nickname", "Unknown"),
                mask=str(acct.get("account_number", ""))[-4:],
                credit_limit=None,
                current_balance=balance,
                last_synced_at=now,
            ))

        synced.append({"nessie_account_id": nessie_id, "balance": balance})

    db.commit()

    # Record where each card stood at this moment. Utilization is a snapshot
    # the issuer reports and then overwrites -- neither Nessie nor the issuer
    # can say later what it was, so the history exists only if we write it
    # down here. Never let this fail a sync: the balances are already saved.
    for row in db.query(LinkedAccount).filter_by(user_id=DEMO_USER_ID).all():
        try:
            timeseries.record_utilization(
                account_id=row.id,
                balance=row.current_balance or 0.0,
                credit_limit=row.credit_limit,
            )
        except Exception as exc:  # noqa: BLE001 - telemetry must not break sync
            logger.warning("utilization snapshot failed for account %s: %s", row.id, exc)

    return {"synced": len(synced), "accounts": synced}


@router.get("/merchants")
def get_merchants(q: str = ""):
    """Proxy Nessie merchant catalog — used internally for category cross-reference."""
    return nessie_svc.search_merchants(q)
