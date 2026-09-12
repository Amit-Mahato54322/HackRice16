# CreditPick — Full Plan

## 1. Problem
Someone standing in a store with several credit cards doesn't know which one earns the most for that purchase, or whether using it pushes them past a utilization level they care about. Existing reward-optimizer apps exist (CardPointers, MaxRewards) validating real demand, but the voice-in-the-checkout-line moment plus utilization-aware scoring is the differentiator here.

## 2. User Flow
1. User signs in (seeded demo user, JWT auth).
2. Dashboard loads the demo customer's credit accounts — balance from Nessie, credit limit from our Postgres seed data (set once by the seed script at account-creation time, never touched again).
3. User maps each Nessie account to a real card product via a VectorMint-backed searchable picker. No manual data entry — credit limit, used amount, and remaining are all computed and displayed automatically.
4. Dashboard shows connected cards, balances, credit limit, and utilization %.
5. User taps the voice button and speaks a purchase description, e.g. "I'm buying groceries at Whole Foods, around $90."
6. Audio is uploaded to the backend, sent to Gemini (audio in, structured JSON out) → `{merchant, amount, category}`. The merchant name is also cross-referenced against the Nessie merchant catalog for category validation. No clarifying follow-up questions in v1 — single shot only.
7. Backend scores every eligible (credit) card in dollars: `reward` (a rate lookup × amount) minus `risk` (the dollar cost of the FICO damage this purchase's utilization would cause, priced per-card and wallet-wide, scaled to the user's credit profile) — see §7.
8. The top recommendation is turned into a natural-language response, sent to ElevenLabs TTS, and the returned audio plays on the phone; the dashboard simultaneously highlights the winning card with its reward value and utilization callout (e.g. "Use Amex Gold. 4x points on groceries, ~$3.60 value. Utilization would be 22%, below your 30% threshold.").
9. User can tap "Why?" to see every eligible card ranked, each with its estimated value and utilization impact.

## 3. Architecture

```
[Phone: record voice clip] --> [Backend: POST /recommend]
                                    |
                                    v
                          Gemini (audio -> structured JSON)
                                    +
                          Nessie merchant catalog (category validation)
                                    |
                                    v
                    Postgres (linked cards + cached VectorMint
                        reward rates + Nessie balance + user-entered credit_limit)
                                    |
                                    v
                            Scoring engine (ranks all cards)
                                    |
                                    v
                          ElevenLabs (text -> speech)
                                    |
                                    v
        [Phone: plays audio, dashboard highlights winner + shows ranked list]
```

Mobile (Expo) talks only to the FastAPI backend. The backend is the only thing that talks to Nessie, VectorMint, Gemini, and ElevenLabs — keeps API keys off the device and keeps the mobile app thin.

## 4. Data Model (Postgres)

- **users**(id, email, password_hash)
- **linked_accounts**(id, user_id, nessie_account_id, nessie_customer_id, official_name, mask, credit_limit, current_balance, last_synced_at, card_product_id nullable FK) — `credit_limit` is written once by the seed script at account-creation time and never changes; `current_balance` is synced live from Nessie. `amount_used`, `amount_remaining`, and `utilization_pct` are computed fields (`balance`, `credit_limit - balance`, `balance / credit_limit`) — not stored, derived on read. Nessie does not store credit_limit (confirmed by API test).
- **card_products**(id, vectormint_card_id, display_name, issuer, art_url, cached_reward_json, cached_at) — reward_json is the cached VectorMint response for that card's category rates

A `linked_accounts` row with `card_product_id = null` means "synced from Nessie but not yet mapped to a real card" — excluded from scoring, shown on the dashboard as "not configured."

## 5. Key API Endpoints (FastAPI)

- `POST /auth/login`
- `POST /nessie/sync` — fetch the demo customer's credit accounts from Nessie, upsert into `linked_accounts` (balance only — Nessie does not return credit_limit)
- `GET /nessie/merchants?q=` — proxy Nessie merchant search; used internally for category cross-reference during `/recommend`
- `GET /cards/search?q=` — search the VectorMint catalog, backs the card-mapping picker
- `POST /cards/map` — map a `linked_account` to a `card_product`; fetches + caches VectorMint reward data at this moment (not fetched again per recommendation); no credit_limit input — already seeded
- `GET /dashboard` — returns cards, balances, utilization for the signed-in user
- `POST /recommend` — body `{merchant, amount, category?}` (multipart audio + Gemini extraction lands in M6; until then the caller sends merchant/amount directly); runs the scoring engine against the caller's real wallet, falling back to the seeded demo wallet if nothing's mapped to a card product yet, then ElevenLabs; returns the audio + the full ranked breakdown as JSON for the "Why" screen
- `GET /cards/limits` — every user-entered credit limit so far, keyed by card
- `PUT /cards/{card}/limit` — enter or update one card's credit limit by hand (no API in the stack publishes this field)
- `DELETE /cards/{card}/limit` — forget an entered limit; the card is then excluded from scoring rather than guessed

## 6. Nessie Integration Details

Nessie base URL: `http://api.nessieisreal.com`
Auth: `?key=NESSIE_API_KEY` appended to every request.

Endpoints used:

| Endpoint | Purpose |
|---|---|
| `GET /customers/{id}/accounts` | List demo customer's accounts; filter `type=credit card` |
| `GET /accounts/{id}` | Single account detail — `balance` only (`credit_limit` not supported by Nessie) |
| `GET /merchants` | Full merchant list with categories; cached in memory, used for category cross-reference |
| `GET /merchants/{id}` | Single merchant detail |
| `GET /accounts/{id}/purchases` | Transaction history shown on the "Why" screen |

Demo setup: a one-time seed script (`backend/scripts/seed_nessie.py`) creates the Nessie customer + accounts and simultaneously writes `linked_accounts` rows in Postgres with hardcoded credit limits. After that, the app never touches credit limits again — only balance is synced live from Nessie.

Seeded accounts:

| Card | Nessie balance | Credit limit (seeded) | Used | Remaining |
|---|---|---|---|---|
| Chase Sapphire Preferred | $2,500 | $10,000 | 25% | $7,500 |
| Capital One Venture | $5,200 | $8,000 | 65% | $2,800 |
| Bank of America Cash Rewards | $800 | $5,000 | 16% | $4,200 |

Store `NESSIE_CUSTOMER_ID` in `.env` after the seed script runs.

## 7. Scoring Formula (v1)

Every eligible card is scored in dollars (`backend/app/scoring/engine.py`):

```
score = reward - risk
```

- **`reward`** = a straight rate lookup: `rate(card, category) × amount × point_value`. Category caps, sign-up bonuses, and purchase-protection value are deliberately absent — no API in the stack publishes cap usage, offer terms, or claim rates, so modelling them would mean scoring on invented numbers instead of data.
- **`risk`** = the dollar cost of the FICO damage this purchase's utilization would cause — a step function (not a smooth curve), applied both per-card and to aggregate (whole-wallet) utilization, scaled by the user's baseline credit score (a ~790 profile is charged roughly 3x what a ~600 profile is for the same utilization jump). This is the actual differentiator: utilization is *priced*, not merely flagged, so the engine can decline a higher cash-back rate to protect a score — a trade no plain rewards-lookup app makes.
- **Disqualifiers** (checked before scoring, not scored around): no credit limit on record (nothing to divide by), or the purchase would push the card past 95% of its limit (likely declined at the terminal). Both return a reason string rather than silently dropping the card.
- Sort all eligible cards by `score` descending. The top card is the spoken/displayed recommendation; disqualified cards are still returned with their reason so the UI can show what was skipped and why.

### Data sources — and what's deliberately excluded
- `reward` rates come from a small hand-entered local catalog (`backend/app/scoring/card_db.json`). A VectorMint-shaped cache path exists (`CardProduct.cached_reward_json`, normalized in `app/scoring/rewards.py`) for the moment `/cards/map` actually calls VectorMint — nothing does yet, so the local catalog is the only reward-rate source populated today (see §9).
- `credit_limit` is published by no API in the stack — Nessie's account object has no such field (confirmed by a live probe, `backend/tests/test_nessie.py`). It's entered by hand: once at seed time (`scripts/seed_nessie.py`) or per-card via `PUT /cards/{card}/limit`. A card with no limit on record is disqualified, never guessed.
- Category caps, sign-up bonus tracking, purchase protection, and statement-timing float are all explicitly out of the v1 model for the same reason as `credit_limit`: modelling them would mean inventing cap-usage, claim-probability, or billing-cycle figures no source publishes.

### Edge cases handled
- **Unrecognized merchant** (`app/scoring/categorize.py`) → category defaults to `"other"`; every card scores at its base rate rather than guessing a bonus category.
- **Nessie's own merchant category is available** → it wins over the free-text keyword match, since it's authoritative for the demo data.
- **No credit limit on record** → disqualified with that reason, never defaulted to zero or guessed.
- **Purchase would exceed 95% of a card's limit** → disqualified (likely declined at the terminal), not merely penalized by the risk term.
- **Every eligible card disqualified** → an empty recommendation is still returned, with every disqualification reason attached, so the UI can say plainly that nothing can absorb this purchase rather than failing silently.
- **Nothing mapped to a real card product yet** (M4 not done) → `/recommend` falls back to a seeded demo wallet so the engine still runs on real logic instead of returning canned data.

## 8. Milestones

Backend and frontend are meant to run as parallel workstreams, not a relay race. The trick is M1: every endpoint's response shape is written down as a literal `backend/mock/*.json` fixture and committed before any real backend logic exists. Frontend builds every screen against those fixtures starting in M1 and never has to wait on backend again — later milestones just swap a screen's mock data source for the real URL once backend ships it, which is a one-line change, not new UI work. Backend-only milestones (M5) have no frontend task at all, so there's nothing to block there either.

### Day 1 — core pipeline, no voice yet

**M1 — Contract freeze + scaffold** (~2–3h)
- Backend (~90 min): FastAPI app skeleton; SQLAlchemy models (`users`, `linked_accounts`, `card_products`); Postgres schema; every route file registered with a stub handler; the response JSON for `/auth/login`, `/dashboard`, `/cards/search`, `/cards/map`, and `/recommend` written as literal `backend/mock/*.json` fixtures and committed *before* any real logic; permissive CORS enabled immediately. Done when `/docs` renders every route and each stub returns its fixture's exact shape.
- Frontend (~90 min, fully parallel — zero backend dependency): Expo project init, Expo Router layout, Login / Dashboard / Voice / Why screens stubbed and wired to the mock fixtures, not a live server. Done when a user can tap through all four screens end-to-end on fake data with no backend running at all.

**M2 — Auth** ~~(~1h)~~ **DEFERRED — out of scope for demo**
- No login/logout screen. App boots directly to Dashboard.
- All backend endpoints use a hardcoded `DEMO_USER_ID = 1` (seeded by `seed_nessie.py`).
- Single demo user is sufficient for HackRice demo — multi-user auth adds no value to judges.

**M3 — Nessie account sync** (~1.5h)
- Backend (~75 min): Nessie client wrapper (list customer accounts, get account detail); `POST /nessie/sync` upserts into `linked_accounts`; `GET /dashboard` returns the real account list matching the M1 fixture shape. Done when sync runs against the real Nessie sandbox and `/dashboard` reflects real balances.
- Frontend (~15 min): swap Dashboard's mock data source for `GET /dashboard`. Already renders correctly since M1 — this is a data-source swap, not new UI.

**M4 — VectorMint card mapping** (~1.5h)
- Backend (~75 min): VectorMint client wrapper (search, fetch reward data); `GET /cards/search?q=` proxies the catalog; `POST /cards/map` links a `linked_account` to a `card_product` and caches the reward JSON. Credit limit is already in the DB from the seed script — no user input. Done when mapping a seeded account persists a `card_product` row and `/dashboard` shows it as "configured" with utilization fully computed.
- Frontend (~15 min): swap the card-mapping picker's mock search results for `GET /cards/search`; wire the confirm button to `POST /cards/map`. No extra input fields — credit_limit, used, and remaining are all pre-populated from seed data.

**M5 — Scoring engine** ✅ **DONE** (backend-only — no frontend task, nothing to block)
- Backend: `score = reward - risk` in `backend/app/scoring/engine.py` — `reward` is a rate lookup, `risk` prices FICO-step utilization damage (per-card + aggregate, scaled by the user's baseline credit score); disqualifiers for no-credit-limit-on-record and >95%-of-limit. 11 hand-written cases in `backend/tests/test_engine.py`, all passing (`python backend/tests/test_engine.py`), no HTTP, no DB.

### Day 2 — voice layer + polish

**M6 — Voice capture + extraction** (~1.5h)
- Backend (~75 min): Gemini client wrapper (`app/services/gemini.py`) — one call, audio bytes in, a structured JSON schema out (`{merchant, amount, category}`); no separate STT step. `POST /recommend` accepts multipart audio, calls it, cross-references the Nessie merchant catalog for category validation, then feeds the result into the M7 engine path already built — this is the piece that finally makes M7's `{merchant, amount, category}` body real instead of caller-supplied. Done when three real recorded test phrases each extract correctly and produce a real ranking.
- Frontend (~15 min; the recording UI itself can be built with `expo-audio` immediately after M1 against a hardcoded fixture, so only the final network call is blocked on backend — `expo-av` is superseded by `expo-audio` in this SDK, see AGENTS.md): record button; upload to `/recommend`; display extracted merchant/category/amount.

**M7 — Full recommend pipeline** ✅ **DONE** (interim: JSON body, not voice yet)
- Backend: `POST /recommend` now takes `{merchant, amount, category?}`, builds the caller's real wallet (`app/scoring/adapter.py`) — or falls back to a seeded demo wallet if nothing's mapped to a card product yet (M4) — and ranks it with the M5 engine. The multipart-audio + Gemini-extraction version of this same endpoint is M6's job; this delivers the scoring half of the pipeline ahead of the voice half.
- Frontend: none new — the response contract is unchanged; wiring `mobile-app` to actually call this instead of its mocks is separate, still-outstanding work.

**M8 — ElevenLabs TTS** ✅ **DONE**
- Backend: `/recommend`'s `voice` field calls ElevenLabs with the top card's real `why` string, returns `{ transcript, audio: { url, mimeType } }` (matching `mobile-app/src/services/contracts.ts`'s `VoiceOutput` directly); falls back to placeholder audio if `ELEVENLABS_API_KEY` is unset or the call fails.
- Frontend (`mobile-app/src/services/device-playback.ts`): plays the backend's audio URL via `expo-audio` when present, falls back to on-device `expo-speech` of the transcript otherwise. Not exercised in the app yet — `mobile-app` still runs entirely on `mock-services.ts` (see Open Items).

**M9 — Polish** (~1.5h, frontend-only — no backend dependency)
- Frontend: Dashboard utilization bars, highlight winning card, Why screen ranked breakdown with value + utilization flag, Nessie transaction history on card detail.

**M10 — Stretch: spending trends**
- Backend: `GET /dashboard/trends` — aggregate Nessie purchase history by category per card
- Frontend: spending trend rows on Dashboard per card

**M11 — Demo + submission**
- Full end-to-end run-throughs
- Devpost write-up + required demo video

## 9. Open items
- VectorMint is not called live anywhere yet. `app/scoring/rewards.py` can normalize a cached VectorMint payload the moment `/cards/map` actually fetches one, but until then `card_db.json`'s local catalog is the only reward-rate source. Decide whether M4 wires a real VectorMint call, or the local catalog just stays the permanent source for the demo's cards.
- `/cards/search` and `/cards/map` are still M1 stubs returning fixed mock JSON — that's M4. Until it's built, `/recommend` runs on the seeded demo wallet for any account that isn't wired up by hand like `scripts/seed_nessie.py`'s three.
- `mobile-app` has no live backend adapter yet — `src/services/index.ts` still wires up `mock-services.ts` unconditionally, so none of M3/M7/M8's real backend work is reachable from the app. Someone needs to implement `CreditPickServices` against the real HTTP endpoints (see `mobile-app/ARCHITECTURE.md`, "Backend integration") and switch `index.ts` to it.
- `backend/tests/test_nessie.py` has a real Nessie API key committed in plaintext — rotate it on Nessie's dashboard (see CLAUDE.md Current Status).
