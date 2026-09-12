import type { CreditCard as DemoCard, Purchase } from "../domain/models.ts";
export { money, validateAmount } from "../domain/models.ts";
export const initialPurchase: Purchase = {
  store: "Whole Foods",
  category: "Groceries",
  amount: 90,
};
export const cards: DemoCard[] = [
  {
    id: "everyday",
    name: "Everyday Cash",
    digits: "2048",
    limit: 3146,
    balance: 646,
    reward: "cashback",
    color: "#633440",
  },
  {
    id: "travel",
    name: "Travel Plus",
    digits: "8812",
    limit: 2000,
    balance: 400,
    reward: "points",
    color: "#49353F",
  },
  ...[
    "Green Rewards",
    "City Cash",
    "Weekend Card",
    "Daily Perks",
    "Simple Cash",
    "Adventure",
    "Essentials",
  ].map((name, i): DemoCard => ({
    id: `demo-${i}`,
    name,
    digits: String(3200 + i * 117),
    limit: 600,
    balance: 100,
    reward: "cashback",
    color: "#523D49",
  })),
  {
    id: "reserve",
    name: "Reserve",
    digits: "9021",
    limit: 654,
    balance: 54,
    reward: "cashback",
    color: "#45343D",
  },
];
export const comparisonCards = cards.slice(0, 2);
export const wallet = cards.reduce(
  (sum, card) => ({
    limit: sum.limit + card.limit,
    balance: sum.balance + card.balance,
  }),
  { limit: 0, balance: 0 },
);
export function estimate(card: DemoCard, purchase: Purchase) {
  const rate =
    card.reward === "points" ? 2 : purchase.category === "Groceries" ? 3 : 1;
  const rewards =
    card.reward === "points"
      ? Math.floor(purchase.amount * rate)
      : Math.round(purchase.amount * rate) / 100;
  return {
    rate,
    rewards,
    rewardValue: card.reward === "points" ? rewards / 100 : rewards,
    available:
      Math.round((card.limit - card.balance - purchase.amount) * 100) / 100,
    utilization: ((card.balance + purchase.amount) / card.limit) * 100,
  };
}
export function rankCards(purchase: Purchase) {
  return [...comparisonCards].sort((a, b) => {
    const first = estimate(a, purchase),
      second = estimate(b, purchase);
    if (first.available >= 0 !== second.available >= 0)
      return first.available >= 0 ? -1 : 1;
    return second.rewardValue - first.rewardValue;
  });
}
