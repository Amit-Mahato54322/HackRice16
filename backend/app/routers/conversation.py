"""Conversation route.

The user types a question; the engine answers it and Gemini says the answer out
loud in English. The division is strict: every number in the reply was computed
by app/scoring/engine.py before Gemini was called, and a reply containing a
figure the engine did not produce is discarded (see services/gemini.py).

So the worst case is a plainer sentence, never a wrong one.

The reply is also spoken: ElevenLabs turns it into audio the same way
/recommend does (see app/routers/recommend.py), returning
`{ transcript, audio: { url, mimeType } }`. Falls back to placeholder audio
if ELEVENLABS_API_KEY isn't set or the call fails.

/conversation/voice accepts a recorded clip instead of typed text: Gemini
transcribes it (services/gemini.transcribe), and the transcript is handed to
the exact same reply pipeline as typed text -- no separate audio-specific
extraction path to keep the honesty guarantee above in one place.
"""

import logging
import re
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from app.config import ELEVENLABS_API_KEY
from app.db import get_db
from app.models.linked_account import LinkedAccount
from app.scoring import adapter, engine, limits
from app.scoring.categorize import categorize
from app.services import gemini
from app.services.elevenlabs import synthesize_speech
from app.static_files import save_audio

logger = logging.getLogger(__name__)

router = APIRouter(tags=["conversation"])

DEMO_USER_ID = 1  # replaced by JWT auth in M2 (deferred, see docs/PLAN.md)

MAX_AMOUNT = 2500.0

FALLBACK_AUDIO = {"url": "/mock/recommend-audio-placeholder.mp3", "mimeType": "audio/mpeg"}


def _build_voice(transcript: str) -> dict:
    if not ELEVENLABS_API_KEY:
        return {"transcript": transcript, "audio": FALLBACK_AUDIO}

    try:
        audio_bytes = synthesize_speech(transcript)
        url = save_audio(f"{uuid.uuid4()}.mp3", audio_bytes)
        return {"transcript": transcript, "audio": {"url": url, "mimeType": "audio/mpeg"}}
    except Exception:
        logger.exception("ElevenLabs synthesis failed, falling back to placeholder audio")
        return {"transcript": transcript, "audio": FALLBACK_AUDIO}


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

    # The wallet is reported whether or not there is anything to rank. Handing
    # over an empty card list when the amount is simply unknown made Gemini
    # announce that the user owns no cards -- true of the payload, false of
    # the person.
    wallet = [
        {
            "card_id": card_id,
            "name": cards[card_id]["name"],
            "credit_limit": card_state.get("limit") or None,
            "current_balance": card_state.get("balance", 0.0),
        }
        for card_id, card_state in state["cards"].items()
        if card_id in cards
    ]

    if amount <= 0:
        return {
            "purchase": {
                "store": purchase.store,
                "amount": amount,
                "category": category,
            },
            "wallet": wallet,
            "cards": [],
            "skipped": [],
            "ranking_available": False,
        }

    result = engine.rank(state, category, amount, cards)

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
        "wallet": wallet,
        "cards": scored,
        "skipped": [
            {"name": item.get("card_name"), "reason": item["reason"]}
            for item in result["disqualified"]
        ],
        "ranking_available": True,
    }


def _computed_sentence(context: dict) -> str:
    """What we say when Gemini is unavailable or invented a figure.

    Deliberately the same facts in a plainer voice, so the fallback is a
    downgrade in fluency rather than in accuracy.
    """
    purchase = context["purchase"]
    cards = context["cards"]

    if not cards:
        # Usually nothing is wrong with the wallet -- we just do not know the
        # purchase yet. Saying "no card can cover that" in that situation
        # reads as a rejection, which is both wrong and discouraging.
        missing = []
        if not purchase["store"].strip():
            missing.append("where you're shopping")
        if not purchase["amount"]:
            missing.append("roughly how much")
        if missing:
            return (
                "I still need " + " and ".join(missing) + ". "
                "Try something like \"shoes from Nike for $120\"."
            )
        if not context.get("wallet"):
            return (
                "You don't have a card linked yet. Link one and I'll compare "
                "them for you."
            )
        if context["skipped"]:
            reasons = "; ".join(
                "%s (%s)" % (item["name"], item["reason"]) for item in context["skipped"]
            )
            return "None of your cards can take that right now: " + reasons + "."
        return (
            f"You have {len(context['wallet'])} cards linked, but none of them "
            "can take that purchase right now."
        )
    best = cards[0]
    return (
        f"Use {best['name']} for your "
        f"${context['purchase']['amount']:,.2f} purchase"
        f"{' at ' + context['purchase']['store'] if context['purchase']['store'] else ''}. "
        f"{best['why']}, worth about ${best['estimated_value']:,.2f}."
    )


def _find_card(message: str, cards: list[dict]) -> dict | None:
    """A card the user named, matched on any distinctive word in its name."""
    words = set(re.findall(r"[a-z]+", message.lower()))
    generic = {"card", "credit", "rewards", "the", "my", "bank", "of", "america"}
    best, best_hits = None, 0
    for card in cards:
        name_words = set(re.findall(r"[a-z]+", card["name"].lower())) - generic
        hits = len(name_words & words)
        if hits > best_hits:
            best, best_hits = card, hits
    return best


def _answer(message: str, context: dict) -> str:
    """Answer the question from the computed ranking, without an LLM.

    Gemini phrases this better, but it is a flaky free tier and a fallback
    that ignores the question entirely gives the same sentence to "why?",
    "what about my Sapphire?" and "which is best for travel?" -- which reads
    as a broken app rather than a degraded one.
    """
    cards = context["cards"]
    if not cards:
        return _computed_sentence(context)

    lowered = message.lower()
    best = cards[0]
    purchase = context["purchase"]

    named = _find_card(message, cards)
    if named and named is not best:
        rank = cards.index(named) + 1
        return (
            f"{named['name']} would earn {named['why'].lower()}, about "
            f"${named['estimated_value']:,.2f} -- that ranks {rank} of "
            f"{len(cards)}. {best['name']} still pays more here, about "
            f"${best['estimated_value']:,.2f}."
        )
    if named is best:
        return (
            f"Yes -- {best['name']} is the pick for this one. {best['why']}, "
            f"worth about ${best['estimated_value']:,.2f}."
        )

    if any(word in lowered for word in ("why", "how come", "explain", "reason")):
        answer = (
            f"{best['name']} wins because it pays {best['why'].lower()} on "
            f"{purchase['category']}, about ${best['estimated_value']:,.2f} back."
        )
        if len(cards) > 1:
            runner = cards[1]
            answer += (
                f" Next best is {runner['name']} at about "
                f"${runner['estimated_value']:,.2f}."
            )
        return answer

    if any(word in lowered for word in ("all", "compare", "other", "alternative", "rest")):
        lines = ", ".join(
            f"{card['name']} ${card['estimated_value']:,.2f}" for card in cards
        )
        return f"For ${purchase['amount']:,.2f} at {purchase['store']}: {lines}."

    return _computed_sentence(context)


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


# "$120", "120 dollars", "120 bucks".
_AMOUNT = re.compile(
    r"\$\s?(\d[\d,]*(?:\.\d{1,2})?)|(\d[\d,]*(?:\.\d{1,2})?)\s*(?:dollars|bucks|usd)\b",
    re.IGNORECASE,
)
# "at Whole Foods", "from HEB", and "form HEB" -- that typo is common enough
# to match, since the alternative is silently extracting nothing.
# A bare number only counts when the sentence is clearly about spending:
# "make it 600", "spend 45". Otherwise digits mean something else.
_BARE_AMOUNT = re.compile(
    r"\b(?:make it|spend|spending|for|about|around|costs?|it'?s)\s+"
    r"(\d[\d,]*(?:\.\d{1,2})?)\b",
    re.IGNORECASE,
)
_STORE = re.compile(
    r"\b(?:at|from|form|with)\s+([A-Za-z][\w&'\-.]*(?:\s+[A-Za-z][\w&'\-.]*){0,2})",
    re.IGNORECASE,
)
_STORE_STOPWORDS = {"the", "my", "a", "an", "least", "most", "home"}
# Words that follow a store name rather than belonging to it: "at HEB for
# groceries", "at United instead".
_TRAILING = {
    "for", "instead", "please", "today", "tonight", "now", "tomorrow", "and",
    "with", "about", "around", "on", "in", "using", "to", "buying", "it",
}


def _local_patch(message: str) -> dict | None:
    """Read the purchase straight out of the sentence, without an LLM.

    Gemini does this better, but it is a flaky free tier and this is the only
    way to enter a purchase by typing. A regex that handles "$120 at HEB" keeps
    the app usable when the model is returning 503s.
    """
    patch: dict = {}

    amount_match = _AMOUNT.search(message)
    raw = None
    if amount_match:
        raw = amount_match.group(1) or amount_match.group(2)
    else:
        bare = _BARE_AMOUNT.search(message)
        raw = bare.group(1) if bare else None
    if raw:
        try:
            amount = float(raw.replace(",", ""))
            if 0 < amount <= MAX_AMOUNT:
                patch["amount"] = amount
        except ValueError:
            pass

    store_match = _STORE.search(message)
    if store_match:
        words = store_match.group(1).strip(" .,").split()
        while words and words[-1].lower() in _TRAILING:
            words.pop()
        if words and words[0].lower() not in _STORE_STOPWORDS:
            # "nike" -> "Nike", but leave HEB and BJ's alone.
            patch["store"] = " ".join(
                word.capitalize() if word.islower() else word for word in words
            )

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


def _reply(db: Session, message: str, purchase: PurchaseIn, history: list[dict]) -> dict:
    """Shared by /conversation (typed) and /conversation/voice (spoken)."""
    context = _context(db, purchase)

    translated = gemini.translate(message, context, history)
    patch = _patch(translated.get("purchase_patch") if translated else None)
    # Gemini is the better extractor, but it is not always reachable.
    if patch is None:
        patch = _local_patch(message)

    # If they changed what they are buying, the answer is about the new
    # purchase -- so re-rank before judging the reply.
    if patch:
        context = _context(db, _patched(purchase, patch))
        # `translated["reply"]` was phrased against the *old* context (e.g.
        # "no cards yet" from a blank starting purchase) -- it has no figures
        # for validate_reply() to catch, so a stale-but-figure-free sentence
        # would otherwise sail through ungrounded-but-undetected. Re-translate
        # against what actually changed rather than ship a true-at-the-time,
        # false-by-now sentence.
        translated = gemini.translate(message, context, history)

    reply = _answer(request.message, context)
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
        "voice": _build_voice(reply),
    }


@router.post("/conversation")
def conversation(request: ConversationRequest, db: Session = Depends(get_db)):
    history = [turn.model_dump() for turn in request.history]
    return _reply(db, request.message, request.purchase, history)


@router.post("/conversation/voice")
async def conversation_voice(
    db: Session = Depends(get_db),
    audio: UploadFile = File(...),
    store: str = Form(""),
    amount: float = Form(0.0),
    category: str | None = Form(None),
):
    """Single-shot voice input -- no history, no follow-up questions, per
    CLAUDE.md's non-goals. The transcript is treated exactly like a typed
    message once Gemini produces it.
    """
    audio_bytes = await audio.read()
    mime_type = audio.content_type or "audio/mp4"

    message = gemini.transcribe(audio_bytes, mime_type)
    if not message:
        raise HTTPException(
            status_code=422,
            detail="Could not transcribe the audio. Please try again or type instead.",
        )

    purchase = PurchaseIn(store=store, amount=amount, category=category)
    result = _reply(db, message, purchase, [])
    result["transcript"] = message  # what the user said, for the UI's own chat bubble
    return result
