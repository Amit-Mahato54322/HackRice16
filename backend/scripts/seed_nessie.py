"""
One-time seed script: creates a Nessie customer + 3 credit card accounts,
then writes linked_accounts rows in Postgres with hardcoded credit limits.

Nessie does not store credit_limit, so we own it here permanently.
Balance comes live from Nessie on every POST /nessie/sync call.

Run from backend/:
    python scripts/seed_nessie.py

After running, copy the printed NESSIE_CUSTOMER_ID into your .env file.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

from app.config import NESSIE_API_KEY, NESSIE_CUSTOMER_ID
from app.db import SessionLocal, Base, engine
from app.models.card_product import CardProduct
from app.services import vectormint
import app.models  # noqa: F401

Base.metadata.create_all(bind=engine)

NESSIE_BASE = "https://api.nessieisreal.com"

# Seeded cards — balance comes from Nessie, credit_limit lives in our DB only.
# vectormint_card_id maps each one to a real card product so it actually gets
# scored, instead of silently falling back to adapter.demo_wallet() (see
# adapter.build_wallet: an account with no card_product_id is skipped).
CARDS = [
    {"nickname": "Chase Sapphire Preferred",    "balance": 2500, "credit_limit": 10000, "vectormint_card_id": "chase-sapphire-preferred"},
    {"nickname": "Capital One Venture",          "balance": 5200, "credit_limit": 8000,  "vectormint_card_id": "capital-one-venture"},
    {"nickname": "Bank of America Cash Rewards", "balance": 800,  "credit_limit": 5000,  "vectormint_card_id": "bofa-customized-cash"},
]


def _map_to_card_product(db, account, vectormint_card_id: str):
    """Same upsert /cards/map does: cache the reward data, link the account."""
    if account.card_product_id:
        return
    card_data = vectormint.get_card(vectormint_card_id)
    if not card_data:
        print(f"        WARN  no VectorMint match for {vectormint_card_id} -- not scored yet")
        return
    product = (
        db.query(CardProduct).filter_by(vectormint_card_id=vectormint_card_id).first()
    )
    if not product:
        product = CardProduct(
            vectormint_card_id=card_data["vectormint_card_id"],
            display_name=card_data["display_name"],
            issuer=card_data["issuer"],
            art_url=card_data.get("art_url"),
            cached_reward_json=card_data["rewards"],
            cached_at=datetime.now(timezone.utc),
        )
        db.add(product)
        db.flush()
    account.card_product_id = product.id
    db.commit()
    print(f"        mapped -> {product.display_name} ({product.issuer})")


def nessie_post(path: str, body: dict) -> dict:
    res = httpx.post(f"{NESSIE_BASE}{path}?key={NESSIE_API_KEY}", json=body)
    res.raise_for_status()
    return res.json()


def main():
    from app.models.user import User
    from app.models.linked_account import LinkedAccount

    db = SessionLocal()

    # 1 — Demo user (no real auth in v1 — DEMO_USER_ID=1 hardcoded in all routers)
    user = db.query(User).filter_by(email="demo@creditpick.com").first()
    if not user:
        user = User(email="demo@creditpick.com", password_hash="unused")
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"Created demo user  id={user.id}  email=demo@creditpick.com")
    else:
        print(f"Demo user already exists  id={user.id}")

    # 2 — Nessie customer
    customer_id = NESSIE_CUSTOMER_ID
    if not customer_id:
        res = nessie_post("/customers", {
            "first_name": "Demo",
            "last_name": "User",
            "address": {
                "street_number": "1",
                "street_name": "Main St",
                "city": "Houston",
                "state": "TX",
                "zip": "77001",
            },
        })
        customer_id = res["objectCreated"]["_id"]
        print(f"\nCreated Nessie customer: {customer_id}")
        print(f"  >> Add to .env:  NESSIE_CUSTOMER_ID={customer_id}")
    else:
        print(f"\nUsing existing Nessie customer: {customer_id}")

    # 3 — Nessie accounts + linked_accounts rows
    print()
    for card in CARDS:
        existing = (
            db.query(LinkedAccount)
            .filter_by(nessie_customer_id=customer_id, official_name=card["nickname"])
            .first()
        )
        if existing:
            print(f"  SKIP  {card['nickname']} — already in DB (id={existing.id})")
            _map_to_card_product(db, existing, card["vectormint_card_id"])
            continue

        res = nessie_post(f"/customers/{customer_id}/accounts", {
            "nickname": card["nickname"],
            "type": "Credit Card",
            "rewards": 0,
            "balance": card["balance"],
        })
        nessie_id = res["objectCreated"]["_id"]
        acct_number = str(res["objectCreated"].get("account_number", ""))

        account = LinkedAccount(
            user_id=user.id,
            nessie_account_id=nessie_id,
            nessie_customer_id=customer_id,
            official_name=card["nickname"],
            mask=acct_number[-4:],
            credit_limit=card["credit_limit"],
            current_balance=card["balance"],
            last_synced_at=datetime.now(timezone.utc),
        )
        db.add(account)
        db.commit()

        used_pct = round(card["balance"] / card["credit_limit"] * 100, 1)
        remaining = card["credit_limit"] - card["balance"]
        print(
            f"  OK    {card['nickname']}\n"
            f"        nessie_id={nessie_id}\n"
            f"        balance=${card['balance']:,.0f}  "
            f"limit=${card['credit_limit']:,.0f}  "
            f"used={used_pct}%  "
            f"remaining=${remaining:,.0f}"
        )
        _map_to_card_product(db, account, card["vectormint_card_id"])

    # 4 — Print all data: Nessie raw + Postgres computed
    print("\n" + "=" * 60)
    print("  NESSIE RAW DATA")
    print("=" * 60)
    import json
    nessie_accounts = httpx.get(
        f"{NESSIE_BASE}/customers/{customer_id}/accounts?key={NESSIE_API_KEY}"
    ).json()
    print(json.dumps(nessie_accounts, indent=2))

    print("\n" + "=" * 60)
    print("  POSTGRES DATA (linked_accounts)")
    print("=" * 60)
    all_accounts = db.query(LinkedAccount).filter_by(user_id=user.id).all()
    print(f"{'Card':<35} {'Balance':>10} {'Limit':>10} {'Used':>8} {'Remaining':>12} {'Util%':>6}")
    print("-" * 85)
    for a in all_accounts:
        limit   = a.credit_limit or 0
        balance = a.current_balance or 0
        util    = round(balance / limit * 100, 1) if limit else 0
        print(
            f"{a.official_name:<35} "
            f"${balance:>9,.0f} "
            f"${limit:>9,.0f} "
            f"${balance:>7,.0f} "
            f"${(limit - balance):>11,.0f} "
            f"{util:>5}%"
        )

    db.close()
    print("\nSeed complete. Run POST /nessie/sync to refresh balances anytime.")


if __name__ == "__main__":
    main()
