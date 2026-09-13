"""Savings module tests. Plain asserts, no pytest fixtures.

Run: python backend/tests/test_savings.py   (from the repo root)

Covers the pure savings math layered on top of the engine: per-card
utilization, priority ordering, below-optimal gaps, and the vs-average
"saved" headline.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from app.scoring import adapter, engine, savings  # noqa: E402


def _result(category="groceries", amount=100.0):
    cards, state = adapter.demo_wallet()
    return savings, state, engine.rank(state, category, amount, cards), amount


# --- utilization -----------------------------------------------------------


def test_utilization_current_and_projected():
    u = savings.utilization({"balance": 1240.0, "limit": 5000.0}, 400.0)
    assert u["current_pct"] == 24.8, u
    assert u["projected_pct"] == 32.8, u


def test_utilization_no_limit_is_none():
    u = savings.utilization({"balance": 500.0, "limit": 0}, 100.0)
    assert u["current_pct"] is None and u["projected_pct"] is None, u


# --- annotate --------------------------------------------------------------


def test_annotate_assigns_sequential_priority():
    s, state, result, amount = _result()
    ann = s.annotate(result, state, amount)
    assert [c["priority"] for c in ann] == list(range(1, len(ann) + 1)), ann


def test_annotate_marks_and_measures_the_winner():
    s, state, result, amount = _result()
    ann = s.annotate(result, state, amount)
    assert ann[0]["is_best"] is True
    assert ann[0]["below_optimal"] == 0.0, ann[0]
    # below_optimal is exactly how far each card trails the top score.
    best = ann[0]["score"]
    for c in ann:
        assert c["below_optimal"] == round(best - c["score"], 2), c


def test_annotate_below_optimal_never_decreases():
    """Cards are ranked best-first, so the gap to the winner grows monotonically."""
    s, state, result, amount = _result()
    gaps = [c["below_optimal"] for c in s.annotate(result, state, amount)]
    assert gaps == sorted(gaps), gaps


def test_annotate_empty_result():
    assert savings.annotate({"all_cards": []}, {"cards": {}}, 100.0) == []


# --- summary (the vs-average headline) -------------------------------------


def test_summary_saved_is_optimal_minus_average():
    s, state, result, amount = _result()
    summ = s.summary(result)
    scores = [c["score"] for c in result["all_cards"]]
    assert summ["best_value"] == round(max(scores), 2), summ
    assert summ["average_value"] == round(sum(scores) / len(scores), 2), summ
    assert summ["saved"] == round(max(scores) - sum(scores) / len(scores), 2), summ
    assert summ["eligible_count"] == len(scores)


def test_summary_saved_is_non_negative():
    """The best card can never be below the average of all cards."""
    s, state, result, amount = _result("travel", 300.0)
    assert s.summary(result)["saved"] >= 0.0


def test_summary_empty_result_is_none():
    assert savings.summary({"all_cards": []}) is None


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
