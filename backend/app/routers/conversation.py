"""Conversation route.

The user types a question; the engine answers it and Gemini says the answer out
loud in English. The division is strict: every number in the reply was computed
by app/scoring/engine.py before Gemini was called, and a reply containing a
figure the engine did not produce is discarded (see services/gemini.py).

So the worst case is a plainer sentence, never a wrong one.
"""

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.models.linked_account import LinkedAccount
from app.scoring import adapter, engine, limits
from app.scoring.categorize import categorize
from app.services import gemini

logger = logging.getLogger(__name__)

router = APIRouter(tags=["conversation"])

DEMO_USER_ID = 1  # replaced by JWT auth in M2 (deferred, see docs/PLAN.md)

MAX_AMOUNT = 2500.0


class PurchaseIn(BaseModel):
    store: str = ""
    amount: float = Field(default=0.0, ge=0)
    category: str | None = None


class Turn(BaseModel):
    role: str
    text: str


class ConversationRequest(BaseModel):
    message: str
    purchase: PurchaseIn = PurchaseIn()
    history: list[Turn] = []


def _context(db: Session, purchase: PurchaseIn) -> dict:
    """The computed ranking, as the only facts Gemini is allowed to use."""
    accounts = (
        db.query(LinkedAccount)
        .options(joinedload(LinkedAccount.card_product))
        .filter_by(user_id=DEMO_USER_ID)
        .all()
    )
    cards, state, _ = adapter.build_wallet(accounts)
    limits.apply(state)

    category = purchase.category or categorize(purchase.store)
    amount = purchase.amount or 0.0
    result = engine.rank(state, category, amount, cards) if amount > 0 else {
        "all_cards": [],
        "disqualified": [],
    }

    scored = []
    for card in result["all_cards"]:
        card_state = state["cards"].get(card["card"], {})
        limit = card_state.get("limit") or 0.0
        balance = card_state.get("balance", 0.0)
        scored.append(
            {
                "card_id": card["card"],
                "name": card["card_name"],
                "reward_rate": card["reward_rate"],
                "estimated_value": round(card["estimated_value"], 2),
                "why": card["why"],
                "credit_limit": limit or None,
                "current_balance": balance,
                "available": round(limit - balance - amount, 2) if limit else None,
                "utilization": round((balance + amount) / limit, 4) if limit else None,
            }
        )

    return {
        "purchase": {
            "store": purchase.store,
            "amount": amount,
            "category": category,
        },
        "cards": scored,
        "skipped": [
            {"name": item.get("card_name"), "reason": item["reason"]}
            for item in result["disqualified"]
        ],
    }


def _computed_sentence(context: dict) -> str:
    """What we say when Gemini is unavailable or invented a figure.

    Deliberately the same facts in a plainer voice, so the fallback is a
    downgrade in fluency rather than in accuracy.
    """
    cards = context["cards"]
    if not cards:
        return (
            "I don't have a card that can cover that yet. "
            "Add an amount, or link a card to get a recommendation."
        )
    best = cards[0]
    return (
        f"Use {best['name']} for your "
        f"${context['purchase']['amount']:,.2f} purchase"
        f"{' at ' + context['purchase']['store'] if context['purchase']['store'] else ''}. "
        f"{best['why']}, worth about ${best['estimated_value']:,.2f}."
    )


def _patch(raw: dict | None) -> dict | None:
    """Only fields the user could plausibly have changed, within bounds."""
    if not raw:
        return None
    patch: dict = {}
    store = raw.get("store")
    if isinstance(store, str) and store.strip():
        patch["store"] = store.strip()
    amount = raw.get("amount")
    if isinstance(amount, (int, float)) and 0 < amount <= MAX_AMOUNT:
        patch["amount"] = float(amount)
    return patch or None


def _patched(purchase: PurchaseIn, patch: dict) -> PurchaseIn:
    """The purchase as the user just redescribed it."""
    store = patch.get("store", purchase.store)
    return PurchaseIn(
        store=store,
        amount=patch.get("amount", purchase.amount),
        # A new store implies a new category; let categorize() decide.
        category=None if patch.get("store") else purchase.category,
    )


@router.post("/conversation")
def conversation(request: ConversationRequest, db: Session = Depends(get_db)):
    context = _context(db, request.purchase)

    translated = gemini.translate(
        request.message,
        context,
        [turn.model_dump() for turn in request.history],
    )
    patch = _patch(translated.get("purchase_patch") if translated else None)

    # If they changed what they are buying, the answer is about the new
    # purchase -- so re-rank before judging the reply. Otherwise a perfectly
    # good sentence about $600 gets rejected for quoting a figure that only
    # looks ungrounded because the context was still describing $90.
    if patch:
        context = _context(db, _patched(request.purchase, patch))

    computed = _computed_sentence(context)
    reply = computed
    grounded = False

    if translated and translated.get("reply"):
        invented = gemini.validate_reply(translated["reply"], context)
        if invented:
            # A figure the engine never computed. Drop the whole reply rather
            # than ship a number we cannot trace.
            logger.warning("Gemini reply rejected: ungrounded figure %s", invented)
        else:
            reply = translated["reply"]
            grounded = True

    return {
        "reply": reply,
        "purchasePatch": patch,
        # True when the wording came from Gemini and passed the grounding
        # check; false when this is the engine's own sentence.
        "generated": grounded,
    }
