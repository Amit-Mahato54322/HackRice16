import httpx

from app.config import NESSIE_API_KEY

NESSIE_BASE = "https://api.nessieisreal.com"


def _url(path: str) -> str:
    return f"{NESSIE_BASE}{path}?key={NESSIE_API_KEY}"


def get_customer_accounts(customer_id: str) -> list[dict]:
    res = httpx.get(_url(f"/customers/{customer_id}/accounts"))
    res.raise_for_status()
    return [a for a in res.json() if a.get("type") == "Credit Card"]


def get_account(account_id: str) -> dict:
    res = httpx.get(_url(f"/accounts/{account_id}"))
    res.raise_for_status()
    return res.json()


def get_account_purchases(account_id: str) -> list[dict]:
    res = httpx.get(_url(f"/accounts/{account_id}/purchases"))
    res.raise_for_status()
    return res.json()


def search_merchants(q: str) -> list[dict]:
    res = httpx.get(_url("/merchants"))
    res.raise_for_status()
    merchants = res.json()
    if not q:
        return merchants
    q_lower = q.lower()
    return [m for m in merchants if q_lower in m.get("name", "").lower()]
