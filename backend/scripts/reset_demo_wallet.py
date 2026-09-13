"""Reset the demo user to a clean, diverse, fully-configured wallet.

A realistic user carries more than three cards, so this seeds six distinct
real products. It also fixes the duplicate-account mess: it deletes every
Nessie account on the demo customer first, so `GET /customers/{id}/accounts`
(what POST /nessie/sync reads) returns exactly this set afterwards — no
orphan rows creep back on the next sync.

For each card: create a Nessie account (balance lives in Nessie, synced
live), pull the card's real reward rates from VectorMint, cache them on a
CardProduct, and link the two. Nothing is hand-invented except the credit
limits, which no API publishes (see CLAUDE.md).

Run from backend/:
    python scripts/reset_demo_wallet.py
"""

import sys
import os
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx

from app.config import NESSIE_API_KEY, NESSIE_CUSTOMER_ID
from app.db import SessionLocal, create_tables
from app.models.card_product import CardProduct
from app.models.linked_account import LinkedAccount
from app.models.recommendation import Recommendation
from app.models.user import User
from app.services import vectormint

NESSIE_BASE = "https://api.nessieisreal.com"
DEMO_USER_ID = 1

# nickname, VectorMint card id, credit limit (hand-entered), Nessie balance.
# Balances chosen for a rich demo: two low-utilization cards, two mid, two
# high (one near the 68.9% FICO step) so risk-aware routing has real work.
WALLET = [
    {"nickname": "Chase Sapphire Preferred", "vm": "chase-sapphire-preferred", "limit": 10000, "balance": 2500},
    {"nickname": "Capital One Venture",       "vm": "capital-one-venture",      "limit": 8000,  "balance": 5200},
    {"nickname": "Bank of America Customized Cash", "vm": "bofa-customized-cash", "limit": 5000, "balance": 800},
    {"nickname": "American Express Gold",      "vm": "amex-gold",                "limit": 12000, "balance": 1500},
    {"nickname": "Blue Cash Preferred",        "vm": "amex-blue-cash-preferred", "limit": 6000,  "balance": 3200},
    {"nickname": "Chase Freedom Unlimited",    "vm": "chase-freedom-unlimited",  "limit": 7000,  "balance": 4800},
]


def nessie(method, path, body=None):
    url = f"{NESSIE_BASE}{path}?key={NESSIE_API_KEY}"
    res = httpx.request(method, url, json=body, timeout=30)
    res.raise_for_status()
    return res.json() if res.content else {}


def resolve_card(vm_id):
    """Real VectorMint card, by id then by name search. None if truly absent."""
    card = vectormint.get_card(vm_id)
    if card:
        return card
    hits = vectormint.search_cards(vm_id.replace("-", " "))
    return vectormint.get_card(hits[0]["vectormint_card_id"]) if hits else None


def main():
    if not NESSIE_API_KEY or not NESSIE_CUSTOMER_ID:
        sys.exit("NESSIE_API_KEY / NESSIE_CUSTOMER_ID must be set in .env")

    create_tables()
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(id=DEMO_USER_ID).first()
        if not user:
            user = User(email="demo@creditpick.com", password_hash="unused")
            db.add(user)
            db.commit()
            db.refresh(user)

        # 1 — wipe local rows for a clean slate
        n_recs = db.query(Recommendation).filter_by(user_id=DEMO_USER_ID).delete()
        n_accts = db.query(LinkedAccount).filter_by(user_id=DEMO_USER_ID).delete()
        db.commit()
        print(f"Cleared {n_accts} linked accounts and {n_recs} recommendations.\n")

        # 2 — wipe the Nessie customer's accounts so sync won't resurrect them
        existing = nessie("GET", f"/customers/{NESSIE_CUSTOMER_ID}/accounts")
        for acct in existing:
            nessie("DELETE", f"/accounts/{acct['_id']}")
        print(f"Deleted {len(existing)} Nessie accounts (clean cloud state).\n")

        # 3 — build the fresh diverse wallet
        print(f"{'card':<32}{'util':>7}{'limit':>9}  rewards")
        print("-" * 78)
        for spec in WALLET:
            card = resolve_card(spec["vm"])
            if not card:
                print(f"  SKIP {spec['nickname']} — not found in VectorMint")
                continue

            created = nessie("POST", f"/customers/{NESSIE_CUSTOMER_ID}/accounts", {
                "nickname": spec["nickname"],
                "type": "Credit Card",
                "rewards": 0,
                "balance": spec["balance"],
            })["objectCreated"]

            product = (
                db.query(CardProduct)
                .filter_by(vectormint_card_id=card["vectormint_card_id"])
                .first()
            )
            if not product:
                product = CardProduct(vectormint_card_id=card["vectormint_card_id"])
                db.add(product)
            product.display_name = card["display_name"]
            product.issuer = card["issuer"]
            product.cached_reward_json = card["rewards"]
            product.cached_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(product)

            db.add(LinkedAccount(
                user_id=DEMO_USER_ID,
                nessie_account_id=created["_id"],
                nessie_customer_id=NESSIE_CUSTOMER_ID,
                official_name=spec["nickname"],
                mask=str(created.get("account_number", ""))[-4:],
                credit_limit=spec["limit"],
                current_balance=spec["balance"],
                last_synced_at=datetime.now(timezone.utc),
                card_product_id=product.id,
            ))
            db.commit()

            util = round(spec["balance"] / spec["limit"] * 100, 1)
            print(f"  {spec['nickname']:<30}{util:>6}%{spec['limit']:>9}  {card['rewards']}")

        print(f"\nDone. Demo user now has "
              f"{db.query(LinkedAccount).filter_by(user_id=DEMO_USER_ID).count()} "
              f"fully-configured cards.")
        print("Re-run scripts/simulate_transactions.py to rebuild the savings portfolio.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
