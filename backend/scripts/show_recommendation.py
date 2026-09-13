"""Show what the backend GETS and SENDS for a purchase, on live API data.

Every number here comes from the running backend: card balances synced from
Capital One Nessie, reward rates from VectorMint (cached at mapping), scored
by the deployed engine via POST /recommend. No fixtures, no fallback.

Run from backend/ with the server up on :8000:
    python scripts/show_recommendation.py
"""

import sys
import os

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import httpx

BASE = "http://127.0.0.1:8000"


def show_wallet():
    cards = httpx.get(f"{BASE}/dashboard", timeout=15).json()["cards"]
    print("WALLET (balances from Nessie API, limits from DB seed):")
    for c in cards:
        print(f"  - {c['card_display_name'] or c['official_name']}: "
              f"balance ${c['current_balance']:.0f} / limit ${c['credit_limit']:.0f} "
              f"= {c['utilization_pct']}% utilized")
    print()


def scenario(person, place, merchant, amount, category=None):
    body = {"merchant": merchant, "amount": amount}
    if category:
        body["category"] = category

    print("=" * 74)
    print(f"  {person}: at {place}")
    print("=" * 74)
    print("BACKEND RECEIVES (request):")
    print("  " + json.dumps(body))

    resp = httpx.post(f"{BASE}/recommend", json=body, timeout=40).json()

    best = resp["recommendation"]
    others = resp["ranked"]
    ordered = [best] + others  # best first
    s = resp["savings"]

    print(f"\nBACKEND SENDS (category detected: '{resp['category']}'):\n")
    print(f"{person}: At {place} has {len(ordered)} cards  (priority order)")

    for c in ordered:
        pr = c.get("priority")
        util = c.get("current_utilization_pct")
        rate_pct = c["reward_rate"] * 100
        reward = c["estimated_value"]
        score = c["score"]
        gap = c.get("below_optimal", 0.0)
        tag = "  <-- USE THIS" if pr == 1 else f"  (-${gap:.2f} vs best)"
        print(f"  Priority {pr}: {c['display_name'][:34]:<34} "
              f"util {util}%  {rate_pct:.3g}% (${reward:.2f})  "
              f"score {score:.2f}{tag}")

    print(f"\n  SAVED on this purchase: ${s['saved']:.2f} "
          f"(best ${s['best_value']:.2f} vs average ${s['average_value']:.2f})")
    print(f"  spoken: \"{resp['voice']['transcript']}\"\n")


if __name__ == "__main__":
    show_wallet()
    # Case 1: HEB -> categorizer maps to groceries.
    scenario("Person 1", "HEB ($100 groceries)", "HEB", 100)
    # Case 2: Nike.com -> categorizer maps to online_shopping.
    scenario("Person 1", "Nike.com ($120 shopping)", "Nike.com", 120)
