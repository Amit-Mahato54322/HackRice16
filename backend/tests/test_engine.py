"""Scoring engine tests. Plain asserts, no pytest fixtures.

Run: python backend/tests/test_engine.py   (from the repo root)

Each test builds the accounts it needs. There is no shared seeded wallet --
the engine's only input is LinkedAccount rows, so the tests construct those
directly and go through the same adapter the route does.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from app.scoring import adapter, engine, limits, rewards  # noqa: E402


# --- stand-ins for the SQLAlchemy rows ---------------------------------------


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


def account(id, card_key, balance, credit_limit, name=None, cached=None):
    """One linked account mapped to a card in the catalog."""
    product = FakeProduct(card_key, name or card_key, cached)
    return FakeAccount(id, credit_limit, product, balance)


def wallet(*accounts, ceiling=None):
    """(cards, state) for the given accounts. Skipped rows are dropped."""
    cards, state, _ = adapter.build_wallet(
        list(accounts), utilization_ceiling=ceiling
    )
    return cards, state


def find(result, card_id):
    return next(c for c in result["all_cards"] if c["card"] == card_id)


def ranking(result):
    return [(c["card"], round(c["score"], 3)) for c in result["all_cards"]]


# --- reward ----------------------------------------------------------------


def test_bonus_category_beats_flat():
    """$80 of groceries goes to the 6% card over the 2% flat card."""
    cards, state = wallet(
        account(1, "amex_bcp", 1240.0, 5000.0),
        account(2, "citi_dc", 900.0, 9000.0),
    )
    result = engine.rank(state, "groceries", 80.0, cards)
    assert result["all_cards"][0]["card"] == "1", ranking(result)
    assert abs(find(result, "1")["breakdown"]["reward"] - 4.80) < 1e-9


def test_point_value_is_applied():
    """3x at 1.5 cents per point is 4.5%, not 3%."""
    cards, state = wallet(account(1, "chase_sapphire_reserve", 1800.0, 20000.0))
    result = engine.rank(state, "dining", 100.0, cards)
    assert abs(find(result, "1")["breakdown"]["reward"] - 4.50) < 1e-9


def test_uncategorized_purchase_uses_base_rate():
    """An unrecognized category scores every card at its base rate."""
    cards, state = wallet(account(1, "citi_dc", 900.0, 9000.0))
    result = engine.rank(state, "other", 100.0, cards)
    card = find(result, "1")
    assert card["detail"]["is_bonus_category"] is False
    assert abs(card["breakdown"]["reward"] - 2.00) < 1e-9


# --- the utilization ceiling -----------------------------------------------


def test_ceiling_refuses_the_best_paying_card():
    """The engine hands back a 2% card instead of a 5% one.

    Freedom Flex pays 5% on groceries and sits at 68% utilization; a $400
    charge takes it to 81%. With the user's ceiling at 70% it is refused
    whatever it pays, and the flat 2% card wins. Every number here is either
    measured or set by the user -- nothing is estimated.
    """
    accounts = [
        account(1, "freedom_flex", 2040.0, 3000.0),
        account(2, "citi_dc", 900.0, 9000.0),
    ]
    cards, capped = wallet(*accounts, ceiling=0.70)
    result = engine.rank(capped, "groceries", 400.0, cards)

    reasons = {d["card"]: d["reason"] for d in result["disqualified"]}
    assert "1" in reasons, result["disqualified"]
    assert "70%" in reasons["1"], reasons["1"]
    assert result["all_cards"][0]["card"] == "2", ranking(result)

    # Without a ceiling the same card is eligible and out-earns the winner.
    _, uncapped = wallet(*accounts)
    open_result = engine.rank(uncapped, "groceries", 400.0, cards)
    assert open_result["all_cards"][0]["card"] == "1", ranking(open_result)


def test_no_ceiling_refuses_nothing():
    """Omitting the ceiling leaves only the hard decline limit in play."""
    cards, state = wallet(
        account(1, "freedom_flex", 2040.0, 3000.0),
        account(2, "citi_dc", 900.0, 9000.0),
    )
    result = engine.rank(state, "groceries", 400.0, cards)
    assert result["disqualified"] == []


def test_stricter_ceiling_refuses_more():
    cards, loose = wallet(
        account(1, "amex_bcp", 1240.0, 5000.0),
        account(2, "citi_dc", 900.0, 9000.0),
        ceiling=0.90,
    )
    _, tight = wallet(
        account(1, "amex_bcp", 1240.0, 5000.0),
        account(2, "citi_dc", 900.0, 9000.0),
        ceiling=0.20,
    )
    loose_out = {
        d["card"] for d in engine.rank(loose, "groceries", 400.0, cards)["disqualified"]
    }
    tight_out = {
        d["card"] for d in engine.rank(tight, "groceries", 400.0, cards)["disqualified"]
    }
    assert loose_out < tight_out, (loose_out, tight_out)


def test_decline_limit_applies_without_a_ceiling():
    """$2,040 + $900 against a $3,000 limit is past 95% and would be declined."""
    cards, state = wallet(account(1, "freedom_flex", 2040.0, 3000.0))
    result = engine.rank(state, "groceries", 900.0, cards)
    assert result["all_cards"] == []
    assert "95%" in result["disqualified"][0]["reason"]


# --- user-entered credit limits --------------------------------------------


def test_entered_limit_overrides_the_synced_row():
    """A limit the user enters replaces what the account row carried."""
    limits.clear()
    try:
        limits.set_limit("1", 2000.0)
        cards, state = wallet(account(1, "amex_bcp", 1240.0, 5000.0))
        limits.apply(state)
        assert state["cards"]["1"]["limit"] == 2000.0
        # $1,240 + $400 is 82% of $2,000, not 33% of the row's $5,000.
        result = engine.rank(state, "groceries", 400.0, cards)
        assert abs(find(result, "1")["utilization"] - 0.82) < 1e-9
    finally:
        limits.clear()


def test_missing_limit_disqualifies_rather_than_guessing():
    """No limit from any source means excluded, never defaulted.

    Nessie has no credit_limit field, so this is the state of any account
    seed_nessie.py has not written a limit for.
    """
    cards, state = wallet(account(1, "amex_bcp", 1240.0, None))
    limits.apply(state)
    result = engine.rank(state, "groceries", 100.0, cards)
    assert result["disqualified"][0]["reason"] == "no credit limit on record"


def test_clearing_a_limit_removes_it():
    limits.clear()
    limits.set_limit("2", 9000.0)
    assert limits.get_limit("2") == 9000.0
    limits.set_limit("2", None)
    assert limits.get_limit("2") is None


# --- adapter ---------------------------------------------------------------


def test_adapter_skips_unmapped_account():
    """An account synced but not mapped to a card product is surfaced."""
    cards, state, skipped = adapter.build_wallet([FakeAccount(1, 5000.0)])
    assert cards == {} and state["cards"] == {}
    assert skipped[0]["reason"].startswith("not configured")


def test_adapter_skips_unknown_card_product():
    """Mapped to a product the catalog has no rates for."""
    cards, _, skipped = adapter.build_wallet(
        [account(1, "not_in_catalog", 0.0, 5000.0)]
    )
    assert cards == {}
    assert skipped[0]["reason"] == "no reward data for this card product"


def test_adapter_uses_the_accounts_own_name():
    cards, _, _ = adapter.build_wallet(
        [account(1, "amex_bcp", 0.0, 5000.0, name="Alok's Amex")]
    )
    assert cards["1"]["name"] == "Alok's Amex"


# --- VectorMint normalization ----------------------------------------------


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
    assert card == fallback


def test_cached_payload_beats_the_catalog():
    """VectorMint data wins over the local fallback when present."""
    cards, _, _ = adapter.build_wallet(
        [
            account(
                1,
                "citi_dc",
                0.0,
                9000.0,
                cached={"reward_rules": [{"category_id": "travel", "rate": 5,
                                          "unit": "percent"}]},
            )
        ]
    )
    assert cards["1"]["rates"] == {"travel": 0.05}


def test_uncached_product_falls_back_to_catalog():
    """A mapped card with no VectorMint payload still scores."""
    catalog = rewards.load_catalog()
    cards, _, skipped = adapter.build_wallet([account(1, "amex_bcp", 0.0, 5000.0)])
    assert skipped == []
    assert cards["1"]["rates"]["groceries"] == catalog["amex_bcp"]["rates"]["groceries"]


def test_catalog_lookup():
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
