"""Portfolio aggregation tests. Plain asserts, no pytest fixtures, no DB.

Run: python backend/tests/test_portfolio.py   (from the repo root)

portfolio.summarize is pure and duck-typed, so these feed it plain namespace
objects with the Recommendation columns rather than real SQLAlchemy rows.
"""

import os
import sys
from datetime import datetime, timedelta
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from app.services import portfolio  # noqa: E402

_BASE = datetime(2026, 1, 1, 12, 0, 0)


def row(i, category, amount, saved, cashback, merchant="Store"):
    """One fake Recommendation row, timestamped in sequence."""
    return SimpleNamespace(
        created_at=_BASE + timedelta(days=i),
        merchant=merchant,
        category=category,
        amount=amount,
        chosen_card_name="Card " + category,
        chosen_reward=cashback,
        saved=saved,
        extra_cash=0.0,
    )


def sample_rows():
    return [
        row(0, "groceries", 100.0, 4.00, 6.00, "HEB"),
        row(1, "dining", 50.0, 1.00, 2.00, "Chipotle"),
        row(2, "groceries", 80.0, 3.20, 4.80, "Kroger"),
        row(3, "travel", 400.0, 10.00, 25.00, "United"),
    ]


# --- empty -----------------------------------------------------------------


def test_empty_history_is_all_zeros():
    p = portfolio.summarize([])
    assert p["transaction_count"] == 0
    assert p["total_saved"] == 0.0
    assert p["total_cashback"] == 0.0
    assert p["by_category"] == [] and p["timeline"] == [] and p["recent"] == []


# --- totals ----------------------------------------------------------------


def test_totals_sum_across_rows():
    p = portfolio.summarize(sample_rows())
    assert p["transaction_count"] == 4
    assert p["total_spent"] == 630.0
    assert p["total_cashback"] == 37.80
    assert p["total_saved"] == 18.20
    assert p["avg_saved_per_txn"] == round(18.20 / 4, 2)


# --- category rollup -------------------------------------------------------


def test_by_category_groups_and_sorts_by_saved():
    p = portfolio.summarize(sample_rows())
    cats = {c["category"]: c for c in p["by_category"]}
    assert cats["groceries"]["count"] == 2
    assert cats["groceries"]["saved"] == 7.20  # 4.00 + 3.20
    assert cats["groceries"]["cashback"] == 10.80
    # Sorted by saved desc -> travel ($10) leads.
    assert p["by_category"][0]["category"] == "travel"


# --- timeline --------------------------------------------------------------


def test_timeline_is_cumulative_in_order():
    p = portfolio.summarize(sample_rows())
    cumulative = [t["cumulative_saved"] for t in p["timeline"]]
    assert cumulative == [4.00, 5.00, 8.20, 18.20], cumulative
    assert cumulative[-1] == p["total_saved"]


# --- recent ----------------------------------------------------------------


def test_recent_is_newest_first_and_capped():
    rows = [row(i, "gas", 40.0, 0.5, 1.0) for i in range(15)]
    p = portfolio.summarize(rows, recent_limit=10)
    assert len(p["recent"]) == 10
    # Newest (highest index -> latest date) comes first.
    assert p["recent"][0]["date"] > p["recent"][-1]["date"]


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failures = []
    for test in tests:
        try:
            test()
            print("PASS  " + test.__name__)
        except AssertionError as exc:
            failures.append(test.__name__)
            print("FAIL  " + test.__name__ + "\n      " + str(exc))
    print("\n%d/%d passed" % (len(tests) - len(failures), len(tests)))
    sys.exit(1 if failures else 0)
