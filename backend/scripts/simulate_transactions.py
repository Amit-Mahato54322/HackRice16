"""Simulate a long-run spending history so the savings portfolio has data.

Replays 35 purchases across ~2 months for the demo user. Each purchase is
routed through the real scoring engine against an *evolving* copy of the
wallet — balances grow as cards get used, so utilization (and the engine's
risk-aware routing) changes over time, exactly as it would in real life.

For every purchase it records: which card won, the cash back it earned, and
how much that beat the next-best card by (the per-purchase saving). Summed,
that is "how much CreditPick saved you." The account balances in Postgres are
NOT mutated — only the in-memory sim copy grows, and only Recommendation rows
are persisted, so /dashboard stays truthful.

Run from backend/:
    python scripts/simulate_transactions.py
"""

import sys
import os
import copy
from datetime import datetime, timedelta, timezone

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import SessionLocal, create_tables
from app.models.linked_account import LinkedAccount
from app.scoring import adapter, engine, limits, savings
from app.scoring.categorize import categorize
from app.services import history, portfolio

DEMO_USER_ID = 1

# (merchant, amount) — categorize() derives the category from the merchant.
# A realistic spread: weekly groceries/gas, frequent dining, a few big travel
# and electronics hits, streaming subscriptions.
TRANSACTIONS = [
    ("HEB", 84.20), ("Shell", 41.00), ("Chipotle", 12.75), ("Netflix", 15.49),
    ("Whole Foods", 112.30), ("Starbucks", 6.40), ("United", 420.00),
    ("Whataburger", 18.90), ("Kroger", 76.55), ("Exxon", 52.10),
    ("Spotify", 11.99), ("Best Buy", 349.99), ("Torchys", 24.30),
    ("Randalls", 63.40), ("Chevron", 47.80), ("Marriott", 268.00),
    ("CVS", 32.15), ("HEB", 91.05), ("Chipotle", 14.25), ("Delta", 512.00),
    ("Trader Joes", 58.70), ("Starbucks", 7.10), ("Buc-ee", 39.60),
    ("Apple Store", 129.00), ("Whataburger", 21.40), ("Netflix", 15.49),
    ("HEB", 102.75), ("Shell", 44.25), ("Hilton", 198.00), ("Walgreens", 19.85),
    ("Chipotle", 13.50), ("Kroger", 88.20), ("Spotify", 11.99),
    ("Exxon", 49.30), ("Amazon", 74.99),
]


def load_wallet(db):
    """Real wallet for the demo user, or the seeded demo wallet as fallback."""
    accounts = (
        db.query(LinkedAccount)
        .filter_by(user_id=DEMO_USER_ID)
        .all()
    )
    cards, state, _ = adapter.build_wallet(accounts)
    if cards:
        return cards, state, "real linked accounts"
    cards, state = adapter.demo_wallet()
    return cards, state, "seeded demo wallet"


def main():
    create_tables()
    db = SessionLocal()
    try:
        cards, state, source = load_wallet(db)
        state = copy.deepcopy(state)  # never mutate anything shared
        limits.apply(state)
        print(f"Wallet source: {source}  ({len(cards)} cards)\n")

        removed = history.clear_for_user(db, DEMO_USER_ID)
        if removed:
            print(f"Cleared {removed} prior recommendation rows.\n")

        start = datetime.now(timezone.utc) - timedelta(days=len(TRANSACTIONS) * 2)
        recorded = 0

        print(f"{'date':<11}{'merchant':<14}{'amount':>8}  {'category':<13}{'winner':<26}{'saved':>7}")
        print("-" * 84)

        for i, (merchant, amount) in enumerate(TRANSACTIONS):
            category = categorize(merchant)
            result = engine.rank(state, category, amount, cards)
            summary = savings.summary(result)
            if not summary:
                print(f"  (skipped {merchant} ${amount} — no eligible card)")
                continue

            top = result["all_cards"][0]
            when = start + timedelta(days=i * 2, hours=(i * 7) % 24)
            history.record(
                db,
                user_id=DEMO_USER_ID,
                merchant=merchant,
                category=category,
                amount=amount,
                chosen=top,
                summary=summary,
                created_at=when,
            )
            recorded += 1

            # Charge the winning card so utilization evolves over the run.
            state["cards"][top["card"]]["balance"] += amount

            print(f"{when:%Y-%m-%d} {merchant:<14}{amount:>8.2f}  {category:<13}"
                  f"{top['card_name'][:24]:<26}{summary['saved_vs_next_best']:>7.2f}")

        print(f"\nRecorded {recorded} transactions.\n")

        rows = history.list_for_user(db, DEMO_USER_ID)
        p = portfolio.summarize(rows)
        print("=" * 60)
        print("  PORTFOLIO SUMMARY  (what CreditPick saved this user)")
        print("=" * 60)
        print(f"  transactions      : {p['transaction_count']}")
        print(f"  total spent       : ${p['total_spent']:,.2f}")
        print(f"  total cash back   : ${p['total_cashback']:,.2f}")
        print(f"  total SAVED       : ${p['total_saved']:,.2f}   (vs an average card pick each time)")
        print(f"  avg saved / txn   : ${p['avg_saved_per_txn']:,.2f}")
        print(f"\n  saved by category:")
        for c in p["by_category"]:
            print(f"    {c['category']:<15} {c['count']:>2} txns   saved ${c['saved']:,.2f}")
        print(f"\n  cumulative saved reached ${p['timeline'][-1]['cumulative_saved']:,.2f} "
              f"by {p['timeline'][-1]['date'][:10]}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
