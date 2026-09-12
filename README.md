# CreditPick

Tells you which credit card to pay with, and why.

You say what you're buying. The engine scores every card you own against your
real balances and the card's real earn rates, and answers in one sentence.
Built for HackRice 16 (Finance track).

---

## How it works

```
Nessie ──── balances ────┐
                         ├──→ scoring engine ──→ ranking ──→ Gemini ──→ reply
VectorMint ── rates ─────┘         (deterministic)            (wording only)
```

The split is the point. **The engine decides; Gemini only speaks.**

Every figure in a reply is computed by [`backend/app/scoring/engine.py`](backend/app/scoring/engine.py)
before Gemini is called. Gemini gets that ranking as JSON and turns it into
English. Any reply containing a number the engine did not produce is thrown
away and the engine's own sentence is sent instead — so the worst case is a
plainer answer, never a wrong one. There is no LLM anywhere in the scoring
path, so any number on screen can be traced to arithmetic.

### Scoring

```
score = reward                       maximize
subject to   utilization ≤ ceiling   the user's own limit
```

`reward` is `amount × rate × point_value`. The constraint is what makes this
more than a rate lookup: a card that would push utilization past the user's
ceiling is refused however well it pays, so a 2% card can beat a 5% one. A
purchase past 95% of a limit is refused too — it would likely be declined at
the terminal.

Nothing is estimated. Balances come from Nessie, rates from VectorMint, credit
limits and the ceiling from the user.

---

## Prerequisites

- Python 3.11+
- Node 22.13+
- A PostgreSQL database (we use [Tiger Data](https://www.tigerdata.com/); any Postgres works)
- API keys: Nessie, VectorMint, Gemini

---

## Setup

**1. Python environment** (from the repo root):

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
```

**2. Environment variables:**

```bash
cp backend/.env.example backend/.env
```

Fill in `backend/.env`:

| Variable | Where it comes from | Needed for |
|---|---|---|
| `DATABASE_URL` | your Postgres / Tiger Data service | everything |
| `NESSIE_API_KEY` | [Capital One Nessie](http://api.nessieisreal.com/) | accounts, balances |
| `NESSIE_CUSTOMER_ID` | printed by the seed script in step 3 | accounts, balances |
| `VECTORMINT_API_KEY` | [VectorMint](https://www.vectormint.app/) | reward rates |
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/) | conversational replies |
| `ELEVENLABS_API_KEY` | ElevenLabs | spoken recommendation (optional) |

Use `postgresql://`, not `postgres://` — SQLAlchemy 2.0 rejects the short form.

**Do not put an inline comment after a value.** `dotenv` reads it as part of
the value, which produces confusing 502s from Nessie.

**3. Seed the demo wallet:**

```bash
cd backend
python scripts/seed_nessie.py
```

This creates a Nessie customer with three credit card accounts and writes them
to Postgres with credit limits (Nessie has no `credit_limit` field, so we own
it). Copy the printed customer ID into `NESSIE_CUSTOMER_ID` in `.env`.

Tables are created automatically on startup — no migration step.

---

## Run

**Backend** (from `backend/`):

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

`--host 0.0.0.0` matters: a phone can't reach `localhost` on your laptop.

- Swagger UI: http://localhost:8000/docs
- Health: http://localhost:8000/health

**Map each account to a real card product.** Until an account is mapped, we
have no reward rates for it and it is skipped:

```bash
curl localhost:8000/dashboard                     # find the account ids
curl "localhost:8000/cards/search?q=sapphire"     # find the vectormint ids

curl -X POST localhost:8000/cards/map \
  -H 'content-type: application/json' \
  -d '{"linked_account_id": 1, "vectormint_card_id": "chase-sapphire-preferred"}'
```

**Frontend** (from `mobile-app/`):

```bash
npm install
EXPO_PUBLIC_API_URL=http://<your-lan-ip>:8000 npx expo start
```

Find your LAN IP with `ipconfig getifaddr en0`. Then scan the QR code in Expo
Go, or press `i` / `a` for a simulator, or `w` for the browser.

Without `EXPO_PUBLIC_API_URL` the app defaults to `http://localhost:8000`,
which only works in the browser. There is no offline mode — if the backend is
down you get an error rather than invented numbers.

---

## API

| Endpoint | Does |
|---|---|
| `POST /recommend` | Rank every card for a purchase. `{merchant, amount, category?}` |
| `POST /conversation` | Ask a question in English. `{message, purchase, history?}` |
| `GET /dashboard` | Cards, balances, limits, utilization |
| `POST /nessie/sync` | Refresh balances from Nessie |
| `GET /cards/search?q=` | Search the VectorMint catalog |
| `POST /cards/map` | Link an account to a card product |
| `POST /auth/login` | Returns a placeholder token (auth is not implemented) |

`/recommend` returns the winner, the full ranking, and every card it refused
with the reason — nothing disappears silently.

`/conversation` returns `generated: true` when the wording came from Gemini and
passed the grounding check, `false` when it is the engine's own sentence.

---

## Tests

```bash
.venv/bin/python backend/tests/test_engine.py    # scoring engine
cd mobile-app && npm run typecheck               # frontend types
```

The engine tests are plain asserts with no pytest dependency, and run without a
server, a database, or a network.

---

## What is and isn't wired

**Working end to end:** Nessie account sync, VectorMint rates, the scoring
engine, the recommendation screen, and the Gemini-phrased chat.

**Not wired:**

- **Voice input.** The microphone button reports that it isn't connected. Use
  the chat icon beside it. Audio capture needs a streaming endpoint that
  doesn't exist yet.
- **Auth.** `/auth/login` returns a fixed token; every route acts as user 1.
- **Adding a card from the app.** Accounts are created by the seed script.
- **`GET /nessie/merchants`** returns an empty list, so merchant-category
  cross-referencing falls back to a keyword map.

---

## Known limitations

State these before someone finds them.

- **Category caps, sign-up bonuses and purchase protection are not modelled.**
  No API publishes cap sizes or usage, and modelling them would mean inventing
  the numbers. A card whose bonus cap is already spent will be over-rated.
- **The utilization ceiling is a user preference, not a credit-score
  guarantee.** We refuse cards above it; we don't claim to predict FICO.
- **Merchant → category mapping is the real-world error source.** Issuers pay
  on merchant category codes, and there's no public MCC dataset.
- **Nessie is mock banking data.** Balances are real API responses; the
  accounts behind them are not real accounts.
- **Gemini's free tier returns 503 under load.** We retry, then fall back to
  the engine's sentence. Fluency degrades; accuracy doesn't.
