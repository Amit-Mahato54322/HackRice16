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


# --- reward term -----------------------------------------------------------


def test_cap_split():
    """$300 groceries with $50 of 6% headroom splits 50@6% + 250@1%."""
    cards, state = wallet()
    detail = engine.reward_term(
        cards["amex_bcp"], state["cards"]["amex_bcp"], 300.0, "groceries"
    )
    assert detail["bonus_part"] == 50.0, detail
    assert detail["base_part"] == 250.0, detail
    expected = 50.0 * 0.06 + 250.0 * 0.01
    assert abs(detail["reward"] - expected) < 1e-9, (detail["reward"], expected)


# --- shadow pricing --------------------------------------------------------


def test_shared_cap_headroom_is_priced():
    """Freedom Flex's shared rotating pot is scarce, so headroom has a price."""
    cards, state = wallet()
    prices = engine.shadow_prices(cards, state)
    # 5% groceries vs. the best alternative once Amex's $50 is spread across
    # $4,200 of projected grocery spend -- that's Citi's flat 2%.
    assert abs(prices[("freedom_flex", "rotating")] - 0.03) < 1e-9, prices


def test_uncontested_cap_is_free():
    """Headroom that projected spend cannot exhaust is not scarce."""
    cards, state = wallet()
    state["spend_profile"] = {"groceries": 100.0, "dining": 50.0, "drugstores": 10.0}
    prices = engine.shadow_prices(cards, state)
    assert prices[("freedom_flex", "rotating")] == 0.0, prices


def test_exhausted_cap_has_no_price():
    """A spent cap has no headroom left to protect."""
    cards, state = wallet()
    state["cards"]["freedom_flex"]["cap_used"]["rotating"] = 1500.0
    prices = engine.shadow_prices(cards, state)
    assert prices[("freedom_flex", "rotating")] == 0.0, prices


def test_opportunity_cost_flips_dining():
    """$120 dinner routes to Sapphire Reserve, NOT the 5% rotating card.

    Freedom Flex pays 5% on dining; Sapphire Reserve pays 3x at 1.5 c/pt =
    4.5%. A naive engine takes the 5%. But Freedom's pot is shared with
    groceries, where its edge over the next-best card is far larger, and
    projected grocery spend alone exhausts it. Burning that headroom on
    dining -- where the alternative is nearly as good -- destroys value.
    """
    cards, state = wallet()
    result = engine.rank(state, "dining", 120.0, cards)

    assert result["all_cards"][0]["card"] == "chase_sapphire_reserve", ranking(result)

    flex = find(result, "freedom_flex")
    csr = find(result, "chase_sapphire_reserve")

    # Freedom earns more gross reward: 5% vs. 4.5%.
    assert flex["breakdown"]["reward"] > csr["breakdown"]["reward"], (flex, csr)

    # And loses on the reward line alone once the headroom it burns is priced,
    # before risk or any other term is considered.
    flex_net = flex["breakdown"]["reward"] + flex["breakdown"]["opportunity"]
    assert flex_net < csr["breakdown"]["reward"], (flex_net, csr["breakdown"])
    assert flex["detail"]["opportunity"] > 0


def test_marginal_category_is_indifferent():
    """On groceries, Freedom's advantage exactly equals its headroom price.

    Groceries is the *marginal* category for the rotating cap, so the LP says
    you should be indifferent between spending the headroom and not. The
    engine reproduces that: gross reward minus opportunity cost lands on the
    flat-2% alternative. Later terms, not the reward, break the tie.
    """
    cards, state = wallet()
    result = engine.rank(state, "groceries", 120.0, cards)

    flex = find(result, "freedom_flex")
    citi = find(result, "citi_dc")
    flex_net = flex["breakdown"]["reward"] + flex["breakdown"]["opportunity"]
    citi_net = citi["breakdown"]["reward"] + citi["breakdown"]["opportunity"]
    assert abs(flex_net - citi_net) < 1e-9, (flex_net, citi_net)


# --- sign-up bonus ---------------------------------------------------------


def test_sub_dominates():
    """An open sign-up bonus outranks a 6% category card."""
    cards, state = wallet()
    # Give Amex its full 6% headroom back so this is a fair fight, and reopen
    # Venture X's bonus (the seed wallet ships with it already earned).
    state["cards"]["amex_bcp"]["cap_used"] = {}
    state["cards"]["venture_x"]["sub_progress"] = 800.0
    result = engine.rank(state, "groceries", 200.0, cards)

    assert result["all_cards"][0]["card"] == "venture_x", ranking(result)
    venture = find(result, "venture_x")
    # $750 on $4,000 = 18.75 cents per dollar, far above any category rate.
    assert abs(venture["detail"]["sub_rate"] - 0.1875) < 1e-9


def test_completed_sub_stops_counting():
    """Once the minimum spend is met the bonus is over, not perpetual."""
    cards, state = wallet()
    state["cards"]["venture_x"]["sub_progress"] = 4000.0
    result = engine.rank(state, "groceries", 200.0, cards)
    assert find(result, "venture_x")["detail"]["sub_value"] == 0.0


# --- protection ------------------------------------------------------------


def test_protection_wins():
    """A $1,400 laptop picks the warranty card over a higher rate."""
    cards, state = wallet()
    result = engine.rank(state, "electronics", 1400.0, cards)

    assert result["all_cards"][0]["card"] == "chase_sapphire_reserve", ranking(result)
    csr = find(result, "chase_sapphire_reserve")
    citi = find(result, "citi_dc")
    # Citi pays double the rate on an uncategorized purchase and still loses.
    assert citi["breakdown"]["reward"] > csr["breakdown"]["reward"]
    assert csr["breakdown"]["protection"] > citi["breakdown"]["protection"]


def test_protection_ignored_on_small_purchases():
    cards, state = wallet()
    result = engine.rank(state, "groceries", 80.0, cards)
    for card in result["all_cards"]:
        assert card["breakdown"]["protection"] == 0.0, card


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

    for state in (default_state, protected_state):
        # Full 6% grocery headroom makes Amex the clear reward winner...
        state["cards"]["amex_bcp"]["cap_used"] = {}

    default_result = engine.rank(default_state, "groceries", 400.0, cards)
    protected_result = engine.rank(protected_state, "groceries", 400.0, cards)

    # ...and it wins outright by default.
    assert default_result["all_cards"][0]["card"] == "amex_bcp", ranking(default_result)

    # But $1,240 + $400 on a $5,000 limit is 32.8%, so protecting the score
    # refuses it and settles for a worse-paying card.
    assert protected_result["all_cards"][0]["card"] != "amex_bcp", ranking(
        protected_result
    )
    assert "amex_bcp" in [d["card"] for d in protected_result["disqualified"]]
    assert protected_result["all_cards"][0]["score"] < default_result["all_cards"][0][
        "score"
    ]

    # Everything that would push past 30% utilization is refused outright.
    for card in protected_result["all_cards"]:
        card_state = protected_state["cards"][card["card"]]
        projected = (card_state["balance"] + 400.0) / card_state["limit"]
        assert projected <= 0.30, (card["card"], projected)


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
        self.statement_close = None


def test_adapter_skips_unmapped_account():
    accounts = [FakeAccount(1, 5000.0, card_product=None)]
    cards, state, skipped = adapter.build_wallet(accounts)
    assert cards == {} and state["cards"] == {}
    assert skipped[0]["reason"].startswith("not configured")


def test_adapter_survives_missing_credit_limit():
    """A null credit limit must not divide by zero -- it disqualifies."""
    product = FakeProduct("citi_dc", "Citi Double Cash")
    accounts = [FakeAccount(1, None, card_product=product, balance=100.0)]
    cards, state, _ = adapter.build_wallet(accounts)
    result = engine.rank(state, "groceries", 50.0, cards)
    assert result["all_cards"] == []
    assert result["disqualified"][0]["reason"] == "no credit limit on record"


def test_vectormint_points_per_dollar_is_normalized():
    """A 4x-points payload must not be read as a 400% rate."""
    fallback = rewards.load_catalog()["amex_bcp"]
    card = rewards.normalize_reward_json({"rates": {"groceries": 4}}, fallback)
    assert card["rates"]["groceries"] == 0.04, card["rates"]
    # Caps come from the local overlay, not VectorMint.
    assert card["caps"] == {"groceries": 6000}


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
