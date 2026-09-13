"""Connectivity smoke test for CreditPick's three external dependencies:
Postgres, Capital One Nessie, and VectorMint.

Answers one question per service: "is it reachable and returning real data
right now?" — the things that silently break a live demo. This does NOT test
app logic (scoring, routes); see tests/ for those.

Run from backend/:
    python run_tests.py

Exit code 0 = all green, 1 = at least one failure.
"""

import sys
import os
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows cp1252
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS, FAIL = "PASS", "FAIL"
results = []


def check(name):
    """Decorator: run a check, time it, capture PASS/FAIL + detail line."""
    def wrap(fn):
        print(f"\n>> {name}")
        t0 = time.time()
        try:
            detail = fn()
            status = PASS
        except Exception as e:
            detail = f"{type(e).__name__}: {e}"
            status = FAIL
        ms = int((time.time() - t0) * 1000)
        print(f"   [{status}] {detail}  ({ms} ms)")
        results.append((name, status, detail))
        return fn
    return wrap


# ── 1. Postgres ────────────────────────────────────────────────────────
@check("Postgres — connection + linked_accounts")
def _postgres():
    from app.config import DATABASE_URL
    from app.db import SessionLocal
    from app.models.linked_account import LinkedAccount

    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL not set in .env")

    db = SessionLocal()
    try:
        rows = db.query(LinkedAccount).all()
        names = ", ".join(a.official_name for a in rows) or "(none)"
        return f"connected; {len(rows)} linked_accounts: {names}"
    finally:
        db.close()


# ── 2. Nessie ──────────────────────────────────────────────────────────
@check("Nessie — customer credit accounts")
def _nessie():
    from app.config import NESSIE_API_KEY, NESSIE_CUSTOMER_ID
    from app.services import nessie

    if not NESSIE_API_KEY:
        raise RuntimeError("NESSIE_API_KEY not set in .env")
    if not NESSIE_CUSTOMER_ID:
        raise RuntimeError("NESSIE_CUSTOMER_ID not set in .env")

    accounts = nessie.get_customer_accounts(NESSIE_CUSTOMER_ID)
    if not accounts:
        raise RuntimeError("reachable but returned 0 credit accounts")
    sample = accounts[0]
    return (
        f"{len(accounts)} credit accounts; "
        f"e.g. '{sample.get('nickname')}' balance=${sample.get('balance')}"
    )


# ── 3. VectorMint ──────────────────────────────────────────────────────
@check("VectorMint — live catalog + reward rules")
def _vectormint():
    from app.config import VECTORMINT_API_KEY
    from app.services import vectormint

    if not VECTORMINT_API_KEY:
        raise RuntimeError("VECTORMINT_API_KEY not set in .env")

    hits = vectormint.search_cards("sapphire")
    if not hits:
        raise RuntimeError("reachable but search returned 0 cards")
    card = vectormint.get_card(hits[0]["vectormint_card_id"])
    rewards = card.get("rewards") or {}
    if not rewards:
        raise RuntimeError(f"'{card['display_name']}' returned no reward rates")
    best = max(rewards.items(), key=lambda kv: kv[1])
    return (
        f"'{card['display_name']}' with {len(rewards)} rates; "
        f"best {best[0]}={best[1]:.2%}"
    )


if __name__ == "__main__":
    print("=" * 62)
    print("  CreditPick dependency smoke test")
    print("=" * 62)

    # decorators above already ran the checks on import order
    print("\n" + "=" * 62)
    print("  SUMMARY")
    print("=" * 62)
    for name, status, _ in results:
        print(f"  [{status}]  {name}")

    failed = [r for r in results if r[1] == FAIL]
    print()
    if failed:
        print(f"{len(failed)} of {len(results)} checks FAILED.")
        sys.exit(1)
    print(f"All {len(results)} checks passed. Demo dependencies are live.")
    sys.exit(0)
