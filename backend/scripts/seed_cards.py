"""Seed five real card products and map them to the synced Nessie accounts.

VectorMint is deliberately not called. Every rate below is the issuer's own
published rate, written straight into `CardProduct.cached_reward_json` in the
shape `app/scoring/rewards.normalize_reward_json` already reads, so the wallet
is self-contained in the database and the demo does not depend on a third-party
catalog being up.

Two things this script owns that no API publishes:

- `credit_limit`. Nessie has no such field, so it is hand-entered here. An
  account without one is disqualified by the engine, never guessed.
- `point_value`. Not seeded at all, so every card scores at the 1.0 default --
  a point redeemed for cash. Transfer-partner and travel-portal valuations are
  higher, but they depend on how the holder redeems, so the conservative floor
  is the honest number to rank on.

Idempotent: re-running updates the existing rows rather than duplicating them.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal  # noqa: E402
from app.models import CardProduct, LinkedAccount  # noqa: E402


def rule(category, rate):
    """One reward rule, with its unit stated the way VectorMint states it."""
    return {"category_id": category, "rate": rate, "unit": "percent"}


# The five cards. `match` is the substring used to find the Nessie account this
# product belongs to -- Nessie's account nicknames are free text, so the tie
# between a synced account and a real card product is made by name here.
CARDS = [
    {
        "vectormint_card_id": "chase-sapphire-preferred",
        "display_name": "Chase Sapphire Preferred",
        "issuer": "Chase",
        "match": "sapphire",
        "credit_limit": 15000.0,
        "rewards": {
            "official_name": "Chase Sapphire Preferred",
            "annual_fee": 95,
            "reward_rules": [
                rule("travel", 5),
                rule("dining", 3),
                rule("streaming", 3),
                rule("groceries", 3),
                rule("other", 1),
            ],
        },
    },
    {
        "vectormint_card_id": "capital-one-venture",
        "display_name": "Capital One Venture Rewards",
        "issuer": "Capital One",
        "match": "capital one venture",
        "credit_limit": 12000.0,
        "rewards": {
            "official_name": "Capital One Venture Rewards",
            "annual_fee": 95,
            "reward_rules": [
                rule("travel", 5),
                rule("other", 2),
            ],
        },
    },
    {
        "vectormint_card_id": "bofa-customized-cash",
        "display_name": "Bank of America Customized Cash Rewards",
        "issuer": "Bank of America",
        "match": "bank of america",
        "credit_limit": 5000.0,
        # The 3% category is the holder's own choice; dining is the one picked
        # for this wallet.
        "rewards": {
            "official_name": "Bank of America Customized Cash Rewards",
            "annual_fee": 0,
            "reward_rules": [
                rule("dining", 3),
                rule("groceries", 2),
                rule("other", 1),
            ],
        },
    },
    {
        "vectormint_card_id": "chase-freedom-unlimited",
        "display_name": "Chase Freedom Unlimited",
        "issuer": "Chase",
        "match": "freedom",
        "credit_limit": 8000.0,
        "rewards": {
            "official_name": "Chase Freedom Unlimited",
            "annual_fee": 0,
            "reward_rules": [
                rule("travel", 5),
                rule("dining", 3),
                rule("drugstores", 3),
                rule("other", 1.5),
            ],
        },
    },
    {
        "vectormint_card_id": "amex-blue-cash-preferred",
        "display_name": "Amex Blue Cash Preferred",
        "issuer": "American Express",
        "match": "blue cash",
        "credit_limit": 6000.0,
        "rewards": {
            "official_name": "Amex Blue Cash Preferred",
            "annual_fee": 95,
            "reward_rules": [
                rule("groceries", 6),
                rule("streaming", 6),
                rule("gas", 3),
                rule("other", 1),
            ],
        },
    },
]


def upsert_products(db):
    """Create or refresh the five card products. Returns id -> CardProduct."""
    products = {}
    for spec in CARDS:
        product = (
            db.query(CardProduct)
            .filter_by(vectormint_card_id=spec["vectormint_card_id"])
            .one_or_none()
        )
        if product is None:
            product = CardProduct(vectormint_card_id=spec["vectormint_card_id"])
            db.add(product)
        product.display_name = spec["display_name"]
        product.issuer = spec["issuer"]
        product.cached_reward_json = spec["rewards"]
        product.cached_at = datetime.now(timezone.utc)
        products[spec["vectormint_card_id"]] = product
    db.flush()
    return products


def map_accounts(db, products):
    """Point each of the five accounts at its product and set its limit.

    Nessie's customer holds more accounts than the demo wants -- repeated test
    runs created duplicates against the live sandbox -- so the lowest-numbered
    account matching each card wins and the rest are left unmapped.
    """
    accounts = db.query(LinkedAccount).order_by(LinkedAccount.id).all()
    claimed = {}

    for spec in CARDS:
        for account in accounts:
            if account.id in claimed.values():
                continue
            name = (account.official_name or "").lower()
            if spec["match"] in name:
                account.card_product_id = products[spec["vectormint_card_id"]].id
                account.credit_limit = spec["credit_limit"]
                claimed[spec["vectormint_card_id"]] = account.id
                break

    return claimed, accounts


def main():
    db = SessionLocal()
    try:
        products = upsert_products(db)
        claimed, accounts = map_accounts(db, products)

        missing = [s["display_name"] for s in CARDS if s["vectormint_card_id"] not in claimed]
        if missing:
            print("No Nessie account matched: " + ", ".join(missing))
            print("Run POST /nessie/sync first, or check the account nicknames.")

        # Anything not one of the five is demo clutter: unmapped duplicates and
        # leftover test fixtures. Drop the rows so the wallet is the five cards.
        keep = set(claimed.values())
        removed = [a for a in accounts if a.id not in keep]
        for account in removed:
            db.delete(account)
        db.flush()

        # Card products nothing points at any more (the old "Test" fixtures).
        for product in db.query(CardProduct).all():
            if product.vectormint_card_id not in products:
                db.delete(product)

        db.commit()

        print("\nSeeded %d card products, removed %d stray account(s).\n" % (len(products), len(removed)))
        for account in db.query(LinkedAccount).order_by(LinkedAccount.id).all():
            limit = account.credit_limit or 0.0
            balance = account.current_balance or 0.0
            util = (balance / limit * 100) if limit else 0.0
            print(
                "  %-42s limit $%-9s balance $%-9s %.0f%% used"
                % (
                    account.card_product.display_name if account.card_product else "?",
                    "%.0f" % limit,
                    "%.0f" % balance,
                    util,
                )
            )
    finally:
        db.close()


if __name__ == "__main__":
    main()
