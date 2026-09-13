"""Merchant -> category.

A keyword dict, deliberately. Real-world merchant category codes are a hard
problem we are explicitly not solving (docs/PLAN.md). When a Nessie merchant
record is available its own category wins, since it is authoritative for the
demo data; this map is the fallback for free-text merchant names.
"""

DEFAULT_CATEGORY = "other"

MERCHANT_CATEGORIES = {
    "heb": "groceries",
    "h-e-b": "groceries",
    "kroger": "groceries",
    "whole foods": "groceries",
    "trader joes": "groceries",
    "randalls": "groceries",
    "shell": "gas",
    "exxon": "gas",
    "chevron": "gas",
    "buc-ee": "gas",
    "united": "travel",
    "marriott": "travel",
    "delta": "travel",
    "hilton": "travel",
    "chipotle": "dining",
    "torchys": "dining",
    "whataburger": "dining",
    "starbucks": "dining",
    "netflix": "streaming",
    "spotify": "streaming",
    "cvs": "drugstores",
    "walgreens": "drugstores",
    "best buy": "electronics",
    "apple store": "electronics",
    "nike": "online_shopping",
    "adidas": "online_shopping",
    "amazon": "online_shopping",
    "target": "online_shopping",
    "walmart": "online_shopping",
    "etsy": "online_shopping",
}

# Nessie's own merchant categories don't match our reward-category vocabulary,
# so they're translated rather than trusted verbatim.
NESSIE_CATEGORY_MAP = {
    "grocery": "groceries",
    "groceries": "groceries",
    "food": "dining",
    "restaurant": "dining",
    "dining": "dining",
    "gas": "gas",
    "fuel": "gas",
    "travel": "travel",
    "airline": "travel",
    "hotel": "travel",
    "pharmacy": "drugstores",
    "entertainment": "streaming",
}


def categorize(merchant, nessie_category=None):
    """Best category for this purchase, preferring Nessie's own label."""
    if nessie_category:
        mapped = NESSIE_CATEGORY_MAP.get(nessie_category.strip().lower())
        if mapped:
            return mapped

    key = (merchant or "").strip().lower()
    if key in MERCHANT_CATEGORIES:
        return MERCHANT_CATEGORIES[key]
    for name, category in MERCHANT_CATEGORIES.items():
        if name in key:
            return category
    return DEFAULT_CATEGORY
