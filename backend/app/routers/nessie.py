"""Nessie account-sync and merchant-catalog proxy routes.

These aren't part of the M1 frozen mock contract — the mobile app never
calls them directly (they back /dashboard and /recommend internally, see
docs/PLAN.md §5) — so they stub as "not implemented yet" rather than
returning a fixture. Real Nessie integration lands in M3 (see docs/PLAN.md).
"""

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/nessie", tags=["nessie"])


@router.post("/sync")
def sync_accounts():
    raise HTTPException(status_code=501, detail="Not implemented yet — see docs/PLAN.md M3")


@router.get("/merchants")
def search_merchants(q: str = ""):
    raise HTTPException(status_code=501, detail="Not implemented yet — see docs/PLAN.md M3")
