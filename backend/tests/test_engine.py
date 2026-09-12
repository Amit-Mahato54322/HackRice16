"""Scoring engine tests. Plain asserts, no pytest fixtures.

Run: python backend/tests/test_engine.py   (from the repo root)

These cases are the demo. They must stay green while coefficients get tuned.
"""

import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from app.scoring import adapter, engine, rewards  # noqa: E402


def wallet(**kwargs):
    return adapter.demo_wallet(**kwargs)


def find(result, card_id):
    return next(c for c in result["all_cards"] if c["card"] == card_id)


def ranking(result):
    return [(c["card"], round(c["score"], 3)) for c in result["all_cards"]]


# --- reward ----------------------------------------------------------------


def test_bonus_category_beats_flat():
    """$80 of groceries goes to the 6% card over the 2% flat card."""
    cards, state = wallet()
    result = engine.rank(state, "groceries", 80.0, cards)
    assert result["all_cards"][0]["card"] == "amex_bcp", ranking(result)
    assert abs(find(result, "amex_bcp")["breakdown"]["reward"] - 4.80) < 1e-9


def test_point_value_is_applied():
    """3x at 1.5 cents per point is 4.5%, not 3%."""
    cards, state = wallet()
    result = engine.rank(state, "dining", 100.0, cards)
    csr = find(result, "chase_sapphire_reserve")
    assert abs(csr["breakdown"]["reward"] - 4.50) < 1e-9, csr["breakdown"]


def test_uncategorized_purchase_uses_base_rate():
    """An unrecognized category scores every card at its base rate."""
    cards, state = wallet()
    result = engine.rank(state, "other", 100.0, cards)
    citi = find(result, "citi_dc")
    assert citi["detail"]["is_bonus_category"] is False
    assert abs(citi["breakdown"]["reward"] - 2.00) < 1e-9


# --- risk and disqualifiers ------------------------------------------------


def test_utilization_blocks():
    """The card at 68% utilization is not recommended for a large purchase."""
    cards, state = wallet()
    result = engine.rank(state, "groceries", 900.0, cards)

    # $2,040 + $900 = $2,940 against a $3,000 limit -- past 95%.
    assert "freedom_flex" not in [c["card"] for c in result["all_cards"]], ranking(result)
    reasons = {d["card"]: d["reason"] for d in result["disqualified"]}
    assert "freedom_flex" in reasons, result["disqualified"]
    assert "95%" in reasons["freedom_flex"]


def test_below_first_threshold_is_free():
    """Moving 24.8% -> 32.8% utilization costs nothing, and should not.

    The first per-card step is (0.289, 0): FICO does not start penalizing until
    well above 30%, whatever the folk rule says. Crossing 28.9% moves you onto
    the table without yet costing a point.
    """
    cards, state = wallet()
    result = engine.rank(state, "groceries", 400.0, cards)
    assert find(result, "amex_bcp")["breakdown"]["risk"] == 0.0


def test_risk_penalty_is_priced_not_flagged():
    """Crossing a real FICO step costs dollars, not a boolean flag."""
    cards, state = wallet()
    # Freedom Flex sits at 68%; +$400 pushes it past the 68.9% step.
    result = engine.rank(state, "groceries", 400.0, cards)
    flex = find(result, "freedom_flex")
    assert flex["breakdown"]["risk"] < 0, flex["breakdown"]
    # 15 - 8 = 7 points at the default $2/point, no statement discount.
    assert abs(flex["breakdown"]["risk"] + 14.0) < 1e-9, flex["breakdown"]


def test_risk_outweighs_reward():
    """The engine declines the best rate when score damage exceeds it.

    Freedom Flex pays 5% on groceries and Citi Double Cash pays 2% flat, so a
    rate lookup takes Freedom every time. It loses anyway: pushing past 68.9%
    utilization costs more in FICO damage than the extra cash back is worth.
    No rewards app makes this trade.
    """
    cards, state = wallet()
    result = engine.rank(state, "groceries", 400.0, cards)
    flex = find(result, "freedom_flex")
    citi = find(result, "citi_dc")

    assert flex["reward_rate"] > citi["reward_rate"], (flex, citi)
    assert flex["breakdown"]["reward"] > citi["breakdown"]["reward"]
    # 2.5x the rate, and still the worse choice.
    assert flex["score"] < citi["score"], ranking(result)


def test_risk_scales_with_baseline_score():
    """The same purchase costs a high scorer more than a low scorer."""
    cards, low = wallet(baseline_score=600)
    _, high = wallet(baseline_score=790)
    low_risk = find(engine.rank(low, "groceries", 400.0, cards), "freedom_flex")
    high_risk = find(engine.rank(high, "groceries", 400.0, cards), "freedom_flex")
    assert high_risk["breakdown"]["risk"] < low_risk["breakdown"]["risk"]


def test_mortgage_mode():
    """Protection mode gives up the best rewards to protect the score."""
    cards, default_state = wallet()
    _, protected_state = wallet(protection_mode=True)

    default_result = engine.rank(default_state, "groceries", 400.0, cards)
    protected_result = engine.rank(protected_state, "groceries", 400.0, cards)

    # Amex pays 6% and wins outright by default...
    assert default_result["all_cards"][0]["card"] == "amex_bcp", ranking(default_result)

    # ...but $1,240 + $400 on a $5,000 limit is 32.8%, so protecting the score
    # refuses it and settles for a worse-paying card.
    assert protected_result["all_cards"][0]["card"] != "amex_bcp", ranking(
        protected_result
    )
    assert "amex_bcp" in [d["card"] for d in protected_result["disqualified"]]
    assert (
        protected_result["all_cards"][0]["score"]
        < default_result["all_cards"][0]["score"]
    )


def test_statement_timing_discounts_risk():
    """A card closing well in the future can be paid down before it reports."""
    cards, state = wallet()
    # Freedom Flex closes in 9 days, so its penalty lands in full.
    soon_risk = find(engine.rank(state, "groceries", 400.0, cards), "freedom_flex")[
        "breakdown"
    ]["risk"]

    cards, far_state = wallet()
    far_state["cards"]["freedom_flex"]["statement_close"] = (
        date.today() + timedelta(days=30)
    ).isoformat()
    far_risk = find(engine.rank(far_state, "groceries", 400.0, cards), "freedom_flex")[
        "breakdown"
    ]["risk"]

    assert far_risk > soon_risk, (far_risk, soon_risk)
    assert abs(far_risk - soon_risk * engine.STATEMENT_FAR_DISCOUNT) < 1e-9


# --- adapter ---------------------------------------------------------------


class FakeProduct:
    def __init__(self, vectormint_card_id, display_name):
        self.vectormint_card_id = vectormint_card_id
        self.display_name = display_name


class FakeAccount:
    def __init__(self, id, credit_limit, card_product=None, balance=0.0):
        self.id = id
        self.official_name = "Account %d" % id
        self.credit_limit = credit_limit
        self.current_balance = balance
        self.card_product = card_product
        self.card_product_id = getattr(card_product, "vectormint_card_id", None)
        self.statement_close = None


def test_adapter_skips_unmapped_account():
    accounts = [FakeAccount(1, 5000.0, card_product=None)]
    cards, state, skipped = adapter.build_wallet(accounts)
    assert cards == {} and state["cards"] == {}
    assert skipped[0]["reason"].startswith("not configured")


def test_adapter_survives_missing_credit_limit():
    """A null credit limit must not divide by zero -- it disqualifies.

    Nessie has no credit_limit field, so this is the normal state of a synced
    account until a limit is set locally.
    """
    product = FakeProduct("citi_dc", "Citi Double Cash")
    accounts = [FakeAccount(1, None, card_product=product, balance=100.0)]
    cards, state, _ = adapter.build_wallet(accounts)
    result = engine.rank(state, "groceries", 50.0, cards)
    assert result["all_cards"] == []
    assert result["disqualified"][0]["reason"] == "no credit limit on record"


def test_unknown_card_product_is_skipped():
    """An account mapped to a card the catalog has no rates for is surfaced."""
    product = FakeProduct("not_in_catalog", "Mystery Card")
    accounts = [FakeAccount(1, 5000.0, card_product=product)]
    cards, state, skipped = adapter.build_wallet(accounts)
    assert cards == {}
    assert skipped[0]["reason"] == "no reward data for this card product"


def test_catalog_supplies_rates():
    """Rates come from card_db.json, keyed by card product id."""
    catalog = rewards.load_catalog()
    assert catalog["amex_bcp"]["rates"]["groceries"] == 0.06
    assert rewards.lookup(catalog, "nope") is None


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
