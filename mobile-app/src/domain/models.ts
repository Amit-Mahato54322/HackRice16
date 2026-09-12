export type Category = "Groceries" | "Dining" | "Travel" | "Other";
export type Purchase = { store: string; category: Category; amount: number };
export type CreditCard = {
  id: string;
  name: string;
  digits: string;
  limit: number;
  balance: number;
  reward: "cashback" | "points";
  color: string;
};
export const categories: Category[] = [
  "Groceries",
  "Dining",
  "Travel",
  "Other",
];
export const money = (value: number, decimals = 0) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
// Input validation only. Eligibility and recommendation rules belong to services.
export function validateAmount(input: string, maximum = 2500): number | null {
  const cleaned = input.trim().replace(/^\$/, "");
  if (!/^(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d{1,2})?$/.test(cleaned)) return null;
  const value = Number(cleaned.replace(/,/g, ""));
  return Number.isFinite(value) && value > 0 && value <= maximum ? value : null;
}
