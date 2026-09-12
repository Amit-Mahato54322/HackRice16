import assert from "node:assert/strict";
import test from "node:test";
// Node executes this pure TypeScript module without a native runtime.
import {
  cards,
  estimate,
  initialPurchase,
  rankCards,
  validateAmount,
  wallet,
} from "../src/data/demo.ts";

test("wallet summary reconciles all ten balances", () => {
  assert.equal(cards.length, 10);
  assert.equal(wallet.limit - wallet.balance, 8200);
  assert.equal((wallet.balance / wallet.limit) * 100, 18);
});
test("default recommendation matches the requested demo", () => {
  const result = estimate(cards[0], initialPurchase);
  assert.equal(result.rewards, 2.7);
  assert.equal(result.available, 2410);
  assert.equal(result.utilization.toFixed(1), "23.4");
  assert.equal(estimate(cards[1], initialPurchase).rewards, 180);
  assert.equal(rankCards(initialPurchase)[0].id, "everyday");
});
test("edits update rewards, credit, ranking and threshold crossing", () => {
  const purchase = { ...initialPurchase, amount: 400.25 };
  const result = estimate(cards[0], purchase);
  assert.equal(result.rewards, 12.01);
  assert.equal(result.available, 2099.75);
  assert.ok(result.utilization > 30);
  assert.equal(rankCards({ ...purchase, category: "Dining" })[0].id, "travel");
  assert.equal(
    rankCards({ ...purchase, category: "Dining", amount: 1700 })[0].id,
    "everyday",
  );
});
test("invalid and unaffordable amounts are rejected", () => {
  for (const value of [
    "",
    "0",
    "-10",
    "NaN",
    "90abc",
    "1.001",
    "2500.01",
    "Infinity",
  ])
    assert.equal(validateAmount(value), null);
  assert.equal(validateAmount("$2,500.00"), 2500);
  assert.equal(validateAmount("0.01"), 0.01);
});
