from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import NESSIE_CUSTOMER_ID
from app.db import get_db
from app.models.linked_account import LinkedAccount
from app.services import nessie as nessie_svc

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
    return {"synced": len(synced), "accounts": synced}


@router.get("/merchants")
def get_merchants(q: str = ""):
    """Proxy Nessie merchant catalog — used internally for category cross-reference."""
    return nessie_svc.search_merchants(q)
