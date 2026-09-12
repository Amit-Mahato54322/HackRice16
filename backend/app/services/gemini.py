"""Gemini, used strictly as a translator.

The scoring engine decides which card wins and by how much. Gemini's only job
is to say that in a sentence, and to notice when the user has changed what
they are buying. It is never asked to compare cards, estimate a reward, or
reason about credit -- those answers already exist, computed, before this
module is called.

Three things keep it honest:

1. Every figure it is allowed to use is handed to it as JSON. The system
   instruction tells it to refuse rather than estimate.
2. `response_schema` forces JSON back, and `card_id` is an enum of the cards
   the user actually holds -- so naming a card they do not own is not a
   thing the model can express.
3. `validate_reply` checks every currency and percentage figure in the reply
   against the figures it was given. Anything else means it invented a number,
   and the caller falls back to the deterministic sentence.

The API key stays here on the backend; the mobile app never sees it.
"""

import base64
import json
import logging
import os
import re
import time

import httpx

from app.config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

# gemini-2.5-flash was retired ("no longer available to new users" as of
# 2026-09-12, verified via a direct API call) — gemini-3.6-flash is its
# replacement, confirmed working against this exact schema/request shape.
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
TIMEOUT_SECONDS = 25.0

# The free tier returns 503 under load and 429 at the rate limit, both
# transient. Retry briefly rather than dropping straight to the plainer
# sentence -- but never so long that someone at a checkout is left waiting.
MAX_ATTEMPTS = 3
RETRY_STATUSES = {429, 500, 502, 503, 504}
BACKOFF_SECONDS = 1.5

# Low, not zero: the wording may vary, the numbers may not.
TEMPERATURE = 0.2

SYSTEM_INSTRUCTION = """\
You are CreditPick's assistant. You help someone choose which credit card to \
pay with.

You will be given JSON describing the user's cards and a ranking that has \
already been computed for their current purchase. That JSON is the only source \
of truth you have.

Rules:
- Use ONLY figures that appear in the JSON. Never estimate, round differently, \
or infer a number that is not there.
- Never use anything you know about these cards from training. Real card terms \
change; the JSON is current and you are not.
- If the user asks something the JSON cannot answer, say you do not have that \
information. Refusing is correct behaviour, not a failure.
- The ranking is already decided. Report it; do not re-argue it.
- If the user changes what they are buying (a different store, amount, or \
category), put the change in purchase_patch. Leave it null otherwise.
- Two or three sentences, conversational, no bullet points, no markdown.
"""

# The reply shape. card_id's allowed values are filled in per request from the
# wallet, which is what makes naming an unheld card structurally impossible.
def _response_schema(card_ids):
    return {
        "type": "OBJECT",
        "properties": {
            "reply": {"type": "STRING"},
            "card_id": {
                "type": "STRING",
                "enum": list(card_ids) + ["none"],
                "description": "The card the reply recommends, or 'none'.",
            },
            "purchase_patch": {
                "type": "OBJECT",
                "nullable": True,
                "properties": {
                    "store": {"type": "STRING", "nullable": True},
                    "amount": {"type": "NUMBER", "nullable": True},
                    "category": {"type": "STRING", "nullable": True},
                },
            },
        },
        "required": ["reply", "card_id"],
    }


def is_configured() -> bool:
    return bool(GEMINI_API_KEY)


# --- grounding check --------------------------------------------------------

_MONEY = re.compile(r"\$\s?([\d,]+(?:\.\d{1,2})?)")
_PERCENT = re.compile(r"([\d]+(?:\.\d+)?)\s?%")


def _figures(text: str) -> set[str]:
    """Currency and percentage figures mentioned, normalized for comparison."""
    found = set()
    for raw in _MONEY.findall(text):
        found.add("$" + _trim(raw.replace(",", "")))
    for raw in _PERCENT.findall(text):
        found.add(_trim(raw) + "%")
    return found


def _trim(value: str) -> str:
    """'5.40' -> '5.4', '26.60' -> '26.6', '90.00' -> '90'."""
    try:
        number = float(value)
    except ValueError:
        return value
    return ("%f" % number).rstrip("0").rstrip(".")


def allowed_figures(context: dict) -> set[str]:
    """Every figure the model is permitted to repeat, in the same forms."""
    allowed: set[str] = set()

    def add(value, percent=False):
        if value is None:
            return
        number = float(value)
        allowed.add(_trim("%.2f" % number) + "%" if percent else "$" + _trim("%.2f" % number))
        allowed.add(_trim("%.1f" % number) + "%" if percent else "$" + _trim("%.0f" % number))

    add(context["purchase"]["amount"])
    for card in context["cards"]:
        add(card.get("estimated_value"))
        add(card.get("available"))
        add(card.get("credit_limit"))
        add(card.get("current_balance"))
        if card.get("utilization") is not None:
            add(card["utilization"] * 100, percent=True)
        if card.get("reward_rate") is not None:
            add(card["reward_rate"] * 100, percent=True)
    return allowed


def validate_reply(reply: str, context: dict) -> str | None:
    """The first invented figure in the reply, or None if it is all grounded."""
    allowed = allowed_figures(context)
    for figure in _figures(reply):
        if figure not in allowed:
            return figure
    return None


# --- voice input --------------------------------------------------------


def transcribe(audio_bytes: bytes, mime_type: str) -> str | None:
    """Speech-to-text only. The transcript is then handed to translate()
    exactly like a typed message, so it goes through the same grounding
    pipeline -- no separate audio-specific extraction path to keep honest.

    None on any failure; the caller should ask the user to type instead
    rather than guess at what was said.
    """
    if not GEMINI_API_KEY:
        return None

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "inlineData": {
                            "mimeType": mime_type,
                            "data": base64.b64encode(audio_bytes).decode(),
                        }
                    },
                    {
                        "text": "Transcribe exactly what is said. Reply with "
                        "only the transcript, nothing else -- no quotes, no "
                        "commentary."
                    },
                ],
            }
        ],
        "generationConfig": {"temperature": 0.0},
    }

    # Same transient-failure tolerance as translate() -- the free tier 503s
    # under load and 429s at the rate limit, and a recording the user just
    # made deserves the same retry budget as a typed message would get.
    last_error: Exception | None = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            response = httpx.post(
                f"{BASE_URL}/{MODEL}:generateContent",
                params={"key": GEMINI_API_KEY},
                json=payload,
                timeout=TIMEOUT_SECONDS,
            )
            if response.status_code in RETRY_STATUSES:
                raise httpx.HTTPStatusError(
                    f"retryable {response.status_code}",
                    request=response.request,
                    response=response,
                )
            response.raise_for_status()
            body = response.json()
            text = body["candidates"][0]["content"]["parts"][0]["text"].strip()
            # The model occasionally prefixes a bare meta-label ("thought",
            # "transcript:") despite the instruction not to -- seen
            # intermittently at temperature 0, both as its own line ("Thought\n
            # ...") and inline ("Thought: ..."). Strip it either way; a
            # response that's *only* the label (nothing real said) collapses
            # to an empty string, which `or None` below treats as "no speech."
            text = re.sub(
                r"^\s*(thought|transcript)s?:?\s*\n?\s*", "", text, flags=re.IGNORECASE
            ).strip()
            return text or None
        except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
            last_error = exc
            if attempt + 1 < MAX_ATTEMPTS:
                time.sleep(BACKOFF_SECONDS * (attempt + 1))
        except Exception as exc:  # malformed body, bad key, anything else
            last_error = exc
            break

    logger.warning(
        "Gemini transcription unavailable after %d attempt(s) (%s)",
        MAX_ATTEMPTS,
        type(last_error).__name__,
    )
    return None


# --- the call ---------------------------------------------------------------


def translate(message: str, context: dict, history: list[dict]) -> dict | None:
    """Turn the computed ranking into a sentence. None if unavailable.

    Returns {"reply": str, "card_id": str, "purchase_patch": dict | None}.
    Every failure path returns None so the caller can fall back rather than
    surface an error to someone who just wants to know which card to use.
    """
    if not is_configured():
        return None

    card_ids = [card["card_id"] for card in context["cards"]]
    contents = []
    for turn in history[-6:]:
        contents.append(
            {
                "role": "model" if turn.get("role") == "assistant" else "user",
                "parts": [{"text": turn.get("text", "")}],
            }
        )
    contents.append(
        {
            "role": "user",
            "parts": [
                {"text": "Data (the only figures you may use):\n" + json.dumps(context)},
                {"text": "User says: " + message},
            ],
        }
    )

    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
        "contents": contents,
        "generationConfig": {
            "temperature": TEMPERATURE,
            "responseMimeType": "application/json",
            "responseSchema": _response_schema(card_ids),
        },
    }

    last_error: Exception | None = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            response = httpx.post(
                f"{BASE_URL}/{MODEL}:generateContent",
                params={"key": GEMINI_API_KEY},
                json=payload,
                timeout=TIMEOUT_SECONDS,
            )
            if response.status_code in RETRY_STATUSES:
                raise httpx.HTTPStatusError(
                    f"retryable {response.status_code}",
                    request=response.request,
                    response=response,
                )
            response.raise_for_status()
            body = response.json()
            text = body["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text)
        except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
            last_error = exc
            if attempt + 1 < MAX_ATTEMPTS:
                time.sleep(BACKOFF_SECONDS * (attempt + 1))
        except Exception as exc:  # malformed body, bad key, anything else
            last_error = exc
            break

    logger.warning(
        "Gemini unavailable after %d attempt(s) (%s); using the computed sentence",
        MAX_ATTEMPTS,
        type(last_error).__name__,
    )
    return None
