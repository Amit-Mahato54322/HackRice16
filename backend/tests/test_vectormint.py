"""
Live VectorMint reward browser.

Two modes:
  1. Card view  — everything one card pays, like its rewards page
  2. Category view — every card in the catalog ranked for one category
     (a card with no bonus for the category falls back to its base rate)

Usage from backend/:
    python tests/test_vectormint.py sapphire preferred      # card view
    python tests/test_vectormint.py --category online_shopping
    python tests/test_vectormint.py --category online_shopping --top 20
    python tests/test_vectormint.py                         # interactive

Categories: groceries, dining, gas, travel, streaming, online_shopping,
            utilities, office_supplies, base
"""

import sys
import os

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows cp1252 console
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import vectormint

# The full VectorMint spend taxonomy. Every card gets a rate for each of
# these — an explicit bonus if it has one, otherwise its base rate.
ALL_CATEGORIES = [
    "groceries",
    "dining",
    "gas",
    "travel",
    "streaming",
    "online_shopping",
    "utilities",
    "office_supplies",
]


def pick_card(query: str) -> dict | None:
    matches = vectormint.search_cards(query)

    if not matches:
        print(f"\n  No cards match '{query}'. Available cards:")
        for c in vectormint.search_cards(""):
            print(f"    - {c['display_name']} ({c['issuer']})")
        return None

    if len(matches) == 1:
        return vectormint.get_card(matches[0]["vectormint_card_id"])

    print(f"\n  {len(matches)} cards match '{query}':")
    for i, c in enumerate(matches, 1):
        print(f"    {i}. {c['display_name']} ({c['issuer']})")
    choice = input("  Pick a number: ").strip()
    idx = int(choice) - 1 if choice.isdigit() else 0
    if not (0 <= idx < len(matches)):
        idx = 0
    return vectormint.get_card(matches[idx]["vectormint_card_id"])


def show_card(card: dict):
    print()
    print("=" * 60)
    print(f"  {card['display_name']}  ({card['issuer']})")
    print("=" * 60)

    rewards = card["rewards"]
    base = rewards.get("base", 0.0)

    # Effective rate for EVERY category: explicit bonus if present,
    # otherwise the base rate. Sorted best-first so the winners lead.
    rows = []
    for category in ALL_CATEGORIES:
        if category in rewards:
            rows.append((rewards[category], category, "bonus"))
        else:
            rows.append((base, category, "base"))
    rows.sort(key=lambda r: -r[0])

    print("\n  CATEGORY RATES  (effective back per category)")
    print("  " + "-" * 45)
    for rate, category, source in rows:
        tag = "" if source == "bonus" else "  (base rate)"
        print(f"    {category:<20} {rate:>6.2%} back{tag}")

    print("\n  EVERYTHING ELSE")
    print("  " + "-" * 45)
    print(f"    {'base rate':<20} {base:>6.2%} back")
    print()


def show_category(category: str, top: int):
    """Rank every card in the live catalog for one spend category.

    Split into two tiers: cards with an explicit bonus rule for the
    category, then flat-rate cards falling back to base (co-brand cards
    park their own-store multipliers in base, so mixing tiers misleads).
    """
    explicit, fallback = [], []
    for card in vectormint.search_cards(""):
        rewards = card["rewards"]
        if category in rewards:
            explicit.append((rewards[category], card["display_name"], card["issuer"]))
        else:
            fallback.append((rewards.get("base", 0.0), card["display_name"], card["issuer"]))
    explicit.sort(key=lambda r: -r[0])
    fallback.sort(key=lambda r: -r[0])

    print()
    print("=" * 72)
    print(f"  '{category}' — {len(explicit)} cards with an explicit bonus "
          f"({len(explicit) + len(fallback)} in live catalog)")
    print("=" * 72)
    for rate, name, issuer in explicit[:top]:
        print(f"    {rate:>6.2%}  {name}")
    print(f"\n  BEST FLAT-RATE FALLBACKS (no {category} bonus, base rate applies)")
    print("  " + "-" * 68)
    for rate, name, issuer in fallback[:5]:
        print(f"    {rate:>6.2%}  {name}")
    print()


if __name__ == "__main__":
    args = sys.argv[1:]

    if "--category" in args:
        i = args.index("--category")
        category = args[i + 1]
        top = int(args[args.index("--top") + 1]) if "--top" in args else 15
        show_category(category, top)
        sys.exit(0)

    if args:
        query = " ".join(args)
    else:
        print("Available cards:")
        for c in vectormint.search_cards(""):
            print(f"  - {c['display_name']} ({c['issuer']})")
        query = input("\nEnter a card name or issuer: ").strip()

    card = pick_card(query)
    if card:
        show_card(card)
