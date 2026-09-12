"""Scoring engine tests. Plain asserts, no pytest fixtures.

Run: python backend/tests/test_engine.py   (from the repo root)

These cases are the demo. They must stay green while coefficients get tuned.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from app.scoring import adapter, engine, limits, rewards  # noqa: E402


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


# --- disqualifiers ---------------------------------------------------------


def test_ceiling_refuses_the_best_paying_card():
    """The engine hands back a 2% card instead of a 5% one.

    Freedom Flex pays 5% on groceries and sits at 68% utilization; a $400
    charge takes it to 81%. With the user's ceiling at 70% it is refused
    whatever it pays, and the flat 2% card wins. This is the whole point of
    the constraint -- and every number in it is either measured or set by the
    user, with nothing estimated.
    """
    cards, state = wallet(utilization_ceiling=0.70)
    result = engine.rank(state, "groceries", 400.0, cards)

    reasons = {d["card"]: d["reason"] for d in result["disqualified"]}
    assert "freedom_flex" in reasons, result["disqualified"]
    assert "70%" in reasons["freedom_flex"], reasons["freedom_flex"]

    # Without a ceiling the same card is eligible and out-earns the winner.
    _, open_state = wallet()
    open_result = engine.rank(open_state, "groceries", 400.0, cards)
    assert find(open_result, "freedom_flex")["score"] > find(
        open_result, "citi_dc"
    )["score"]


def test_no_ceiling_refuses_nothing():
    """Omitting the ceiling leaves only the hard decline limit in play."""
    cards, state = wallet()
    result = engine.rank(state, "groceries", 400.0, cards)
    assert result["disqualified"] == []


def test_ceiling_is_the_users_number():
    """A stricter ceiling refuses strictly more cards."""
    cards, loose = wallet(utilization_ceiling=0.90)
    _, tight = wallet(utilization_ceiling=0.20)
    loose_out = {d["card"] for d in engine.rank(loose, "groceries", 400.0, cards)["disqualified"]}
    tight_out = {d["card"] for d in engine.rank(tight, "groceries", 400.0, cards)["disqualified"]}
    assert loose_out < tight_out, (loose_out, tight_out)


def test_utilization_blocks():
    """The card at 68% utilization is not recommended for a large purchase."""
    cards, state = wallet()
    result = engine.rank(state, "groceries", 900.0, cards)

    # $2,040 + $900 = $2,940 against a $3,000 limit -- past 95%.
    assert "freedom_flex" not in [c["card"] for c in result["all_cards"]], ranking(result)
    reasons = {d["card"]: d["reason"] for d in result["disqualified"]}
    assert "freedom_flex" in reasons, result["disqualified"]
    assert "95%" in reasons["freedom_flex"]


# --- user-entered credit limits --------------------------------------------


def test_entered_limit_overrides_seed():
    """A limit the user enters replaces whatever the wallet carried."""
    limits.clear()
    try:
        limits.set_limit("amex_bcp", 2000.0)
        cards, state = wallet()
        limits.apply(state)
        assert state["cards"]["amex_bcp"]["limit"] == 2000.0
        # The entered limit is what utilization is measured against:
        # $1,240 + $400 is 82% of $2,000, not 33% of the seeded $5,000.
        result = engine.rank(state, "groceries", 400.0, cards)
        assert abs(find(result, "amex_bcp")["utilization"] - 0.82) < 1e-9
    finally:
        limits.clear()


def test_missing_limit_disqualifies_rather_than_guessing():
    """No entered limit and none synced means excluded, never defaulted."""
    cards, state = wallet()
    state["cards"]["amex_bcp"]["limit"] = None
    limits.apply(state)
    result = engine.rank(state, "groceries", 100.0, cards)
    reasons = {d["card"]: d["reason"] for d in result["disqualified"]}
    assert reasons["amex_bcp"] == "no credit limit on record"


def test_clearing_a_limit_removes_it():
    limits.clear()
    limits.set_limit("citi_dc", 9000.0)
    assert limits.get_limit("citi_dc") == 9000.0
    limits.set_limit("citi_dc", None)
    assert limits.get_limit("citi_dc") is None


# --- adapter ---------------------------------------------------------------


class FakeProduct:
    def __init__(self, vectormint_card_id, display_name, cached_reward_json=None):
        self.vectormint_card_id = vectormint_card_id
        self.display_name = display_name
        self.cached_reward_json = cached_reward_json


class FakeAccount:
    def __init__(self, id, credit_limit, card_product=None, balance=0.0):
        self.id = id
        self.official_name = "Account %d" % id
        self.credit_limit = credit_limit
        self.current_balance = balance
        self.card_product = card_product
        self.card_product_id = getattr(card_product, "vectormint_card_id", None)


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


def test_vectormint_points_per_dollar():
    """{"rate": 3, "unit": "points_per_dollar"} is 3x, not 300%."""
    fallback = rewards.load_catalog()["chase_sapphire_reserve"]
    card = rewards.normalize_reward_json(
        {
            "reward_rules": [
                {"category_id": "dining", "rate": 3, "unit": "points_per_dollar"},
                {"category_id": "other", "rate": 1, "unit": "points_per_dollar"},
            ]
        },
        fallback,
    )
    assert card["rates"]["dining"] == 0.03, card["rates"]
    assert card["base_rate"] == 0.01, card
    # point_value is not VectorMint's to publish -- it stays local.
    assert card["point_value"] == 1.5
    # 3x at 1.5 cents a point is 4.5%.
    assert abs(engine.effective_rate(card, "dining") - 0.045) < 1e-9


def test_vectormint_percent_unit():
    """A percent-unit rule normalizes the same way."""
    fallback = rewards.load_catalog()["amex_bcp"]
    card = rewards.normalize_reward_json(
        {"reward_rules": [{"category_id": "groceries", "rate": 6, "unit": "percent"}]},
        fallback,
    )
    assert card["rates"]["groceries"] == 0.06, card["rates"]


def test_vectormint_implausible_rate_is_dropped():
    """A rule that normalizes above 30% means the payload was misread."""
    fallback = rewards.load_catalog()["citi_dc"]
    card = rewards.normalize_reward_json(
        {"reward_rules": [{"category_id": "dining", "rate": 4000, "unit": "percent"}]},
        fallback,
    )
    # Nothing usable survived, so the local catalog stands.
    assert card == fallback


def test_uncached_product_falls_back_to_catalog():
    """A mapped card with no VectorMint payload still scores."""
    catalog = rewards.load_catalog()
    product = FakeProduct("amex_bcp", "Amex Blue Cash Preferred")
    cards, state, skipped = adapter.build_wallet([FakeAccount(1, 5000.0, product)])
    assert skipped == []
    assert cards["1"]["rates"]["groceries"] == catalog["amex_bcp"]["rates"]["groceries"]


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
