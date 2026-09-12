"""
Nessie API exploration test.
Investigates whether credit_limit can be stored/retrieved on Credit Card accounts.

Run: python -m tests.test_nessie   (from backend/)
  or: python tests/test_nessie.py
"""

import json
import os
import sys
import urllib.request
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import NESSIE_API_KEY as API_KEY, NESSIE_CUSTOMER_ID as CUSTOMER_ID

BASE_URL = "https://api.nessieisreal.com"

if not API_KEY or not CUSTOMER_ID:
    sys.exit("NESSIE_API_KEY / NESSIE_CUSTOMER_ID not set in backend/.env")
ACCOUNT_IDS = {
    "Chase Sapphire Preferred":       "54022219-396b-4e5b-98ec-50ae376e1c70",
    "Capital One Venture":            "636963f1-4c73-4f76-8a9c-210c95acbbee",
    "Bank of America Cash Rewards":   "b8cdae51-4518-466c-95c0-b5b50cd954d4",
}


def request(method, path, body=None):
    url = f"{BASE_URL}{path}?key={API_KEY}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(req) as res:
            return json.loads(res.read())
    except urllib.error.HTTPError as e:
        return {"error": e.code, "reason": e.read().decode()}


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ── Test 1: GET individual account — does it return more fields than the list? ──
section("Test 1: GET /accounts/{id} for each card")
for name, acct_id in ACCOUNT_IDS.items():
    res = request("GET", f"/accounts/{acct_id}")
    print(f"\n{name}")
    print(json.dumps(res, indent=2))


# ── Test 2: PUT /accounts/{id} — try to set credit_limit ──
section("Test 2: PUT credit_limit onto existing accounts")
credit_limits = {
    "Chase Sapphire Preferred":       10000,
    "Capital One Venture":            8000,
    "Bank of America Cash Rewards":   5000,
}
for name, acct_id in ACCOUNT_IDS.items():
    body = {
        "nickname": name,
        "balance": {"amount": [2500, 5200, 800][list(ACCOUNT_IDS.keys()).index(name)]},
        "credit_limit": credit_limits[name],
    }
    res = request("PUT", f"/accounts/{acct_id}", body)
    print(f"\n{name} - PUT response:")
    print(json.dumps(res, indent=2))


# ── Test 3: Re-fetch after PUT — did credit_limit stick? ──
section("Test 3: Re-fetch accounts after PUT")
for name, acct_id in ACCOUNT_IDS.items():
    res = request("GET", f"/accounts/{acct_id}")
    limit = res.get("credit_limit", "NOT PRESENT")
    balance = res.get("balance", "NOT PRESENT")
    print(f"{name}: balance={balance}, credit_limit={limit}")


# ── Test 4: Create a brand-new account with credit_limit, check if it persists ──
section("Test 4: Create new account with credit_limit — does it persist?")
new_acct = request("POST", f"/customers/{CUSTOMER_ID}/accounts", {
    "nickname": "Test Amex Gold",
    "type": "Credit Card",
    "rewards": 0,
    "balance": 1500,
    "credit_limit": 12000,
})
print(json.dumps(new_acct, indent=2))

new_id = new_acct.get("objectCreated", {}).get("_id")
if new_id:
    fetched = request("GET", f"/accounts/{new_id}")
    print(f"\nRe-fetched account:")
    print(json.dumps(fetched, indent=2))
    print(f"\ncredit_limit in fetched account: {fetched.get('credit_limit', 'NOT PRESENT')}")


# ── Summary ──
section("Summary")
print("""
If credit_limit is NOT returned by Nessie in any test above:
  - Store it ourselves in Postgres linked_accounts.credit_limit
  - User enters it once during the card-mapping step (they know their limit)
  - Balance still comes live from Nessie; only the limit is self-reported

If credit_limit IS returned after PUT in Test 3:
  - Use PUT /accounts/{id} at sync time to write + read the limit
  - No user input needed
""")
