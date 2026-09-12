# CreditPick — Full Plan

## 1. Problem
Someone standing in a store with several credit cards doesn't know which one earns the most for that purchase, or whether using it pushes them past a utilization level they care about. Existing reward-optimizer apps exist (CardPointers, MaxRewards) validating real demand, but the voice-in-the-checkout-line moment plus utilization-aware scoring is the differentiator here.

## 2. User Flow
1. User signs in (seeded demo user, JWT auth).
2. Dashboard loads the demo customer's credit accounts from Capital One Nessie (mock accounts with real balance + credit_limit fields).
3. User maps each Nessie account to a real card product via a VectorMint-backed searchable picker (necessary because Nessie account names don't map to real card products automatically).
4. Dashboard shows connected cards, balances, credit limit, and utilization %.
5. User taps the voice button and speaks a purchase description, e.g. "I'm buying groceries at Whole Foods, around $90."
6. Audio is uploaded to the backend, sent to Gemini (audio in, structured JSON out) → `{merchant, amount, category}`. The merchant name is also cross-referenced against the Nessie merchant catalog for category validation. No clarifying follow-up questions in v1 — single shot only.
7. Backend scores every eligible (credit) card using its VectorMint reward rate for that category × amount, plus the utilization impact of the purchase on that card.
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
                        reward rates + Nessie balance/limit)
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
- **linked_accounts**(id, user_id, nessie_account_id, nessie_customer_id, official_name, mask, credit_limit, current_balance, last_synced_at, card_product_id nullable FK)
- **card_products**(id, vectormint_card_id, display_name, issuer, art_url, cached_reward_json, cached_at) — reward_json is the cached VectorMint response for that card's category rates

A `linked_accounts` row with `card_product_id = null` means "synced from Nessie but not yet mapped to a real card" — excluded from scoring, shown on the dashboard as "not configured."

## 5. Key API Endpoints (FastAPI)

- `POST /auth/login`
- `POST /nessie/sync` — fetch the demo customer's credit accounts from Nessie, upsert into `linked_accounts` (balance + credit_limit)
- `GET /nessie/merchants?q=` — proxy Nessie merchant search; used internally for category cross-reference during `/recommend`
- `GET /cards/search?q=` — search the VectorMint catalog, backs the card-mapping picker
- `POST /cards/map` — map a `linked_account` to a `card_product`; fetches + caches VectorMint reward data at this moment (not fetched again per recommendation)
- `GET /dashboard` — returns cards, balances, utilization for the signed-in user
- `POST /recommend` — multipart audio upload; runs the full pipeline (Gemini extraction + Nessie merchant lookup → scoring → ElevenLabs audio); returns the audio + the full ranked breakdown as JSON for the "Why" screen

## 6. Nessie Integration Details

Nessie base URL: `http://api.nessieisreal.com`
Auth: `?key=NESSIE_API_KEY` appended to every request.

Endpoints used:

| Endpoint | Purpose |
|---|---|
| `GET /customers/{id}/accounts` | List demo customer's accounts; filter `type=credit card` |
| `GET /accounts/{id}` | Single account detail — `balance`, `credit_limit` |
| `GET /merchants` | Full merchant list with categories; cached in memory, used for category cross-reference |
| `GET /merchants/{id}` | Single merchant detail |
| `GET /accounts/{id}/purchases` | Transaction history shown on the "Why" screen |

Demo setup: create one Nessie customer with 3–4 credit card accounts at varied balances and limits. Store the customer ID as `NESSIE_CUSTOMER_ID` in `.env`.

## 7. Scoring Formula (v1)

For each eligible (credit, mapped) card the user owns:

- `reward_rate` = cached VectorMint rate for (card, category); fall back to the card's general/base rate if no category-specific rate exists for that card
- `estimated_value` = `reward_rate × amount` (confirm VectorMint's point-to-dollar convention once in their docs/playground — if they express rates as points-per-dollar rather than %, adjust the multiplier accordingly; this is an open item, see §9)
- `projected_utilization` = `(current_balance + amount) / credit_limit`
- `utilization_flag` = true if `projected_utilization` crosses a fixed 30% threshold (hardcoded constant for v1, no per-user setting)
- Sort all eligible cards by `estimated_value` descending. The top card is the spoken/displayed recommendation. The full sorted list (value + utilization_flag per card) backs the "Why" screen.

### Edge cases to handle
- **Unrecognized category** (Gemini can't classify the merchant) → default to `"other"`, score using each card's general/base reward rate instead of a category-specific one.
- **Card with no cached VectorMint data** (user skipped mapping it) → excluded from scoring entirely, shown on the dashboard as "not yet configured," not silently included with a wrong rate.
- **Every eligible card would cross the utilization threshold** → still recommend the highest-value card, but visibly show the flag rather than hiding the risk — never suppress it just because it's universal.
- **Gemini returns no amount** (user didn't say one) → treat amount as null, skip the utilization-impact calculation for this query, but still rank cards by `reward_rate` alone.
- **No eligible cards at all** (nothing mapped yet) → dashboard/voice response should say so plainly and prompt the user to map a card, not fail silently.
- **Nessie merchant match found** → use Nessie's merchant category to validate or override Gemini's category guess before scoring.

## 7. Milestones

### Day 1 — core pipeline, no voice yet

**M1 — Scaffold**
- Backend: FastAPI app skeleton, SQLAlchemy models (`users`, `linked_accounts`, `card_products`), Postgres schema, all route files registered with stub handlers
- Frontend: Expo project init, Expo Router layout, Login / Dashboard / Voice / Why screens stubbed (navigate between them, no logic)

**M2 — Auth**
- Backend: `POST /auth/login` — verify seeded demo user, return JWT; seed script for demo user
- Frontend: Login screen form → calls `/auth/login`, stores JWT, redirects to Dashboard

**M3 — Nessie account sync**
- Backend: `POST /nessie/sync` — fetch demo customer's credit accounts from Nessie, upsert into `linked_accounts` (balance + credit_limit); `GET /dashboard` returns account list
- Frontend: Dashboard screen calls `/dashboard` on load, renders card rows with balance + utilization %; "not configured" badge for unmapped cards

**M4 — VectorMint card mapping**
- Backend: `GET /cards/search?q=` — proxy VectorMint catalog search; `POST /cards/map` — link a `linked_account` to a `card_product`, cache reward JSON
- Frontend: Card-mapping picker UI on Dashboard — search field + results list + confirm tap updates the card row

**M5 — Scoring engine**
- Backend: pure function `score_cards(cards, category, amount)` — reward_rate × amount, projected utilization, utilization_flag; unit-tested with hardcoded inputs
- Frontend: none

### Day 2 — voice layer + polish

**M6 — Voice capture + extraction**
- Backend: `POST /recommend` accepts multipart audio; calls Gemini → `{merchant, amount, category}`; cross-references Nessie merchant catalog for category validation; returns extraction result (no scoring yet)
- Frontend: Voice screen — record button with `expo-av`, upload audio to `/recommend`, display extracted merchant/category/amount

**M7 — Full recommend pipeline**
- Backend: wire M5 scoring engine into `/recommend` — runs after extraction, returns ranked card list + recommendation text
- Frontend: Voice screen displays top card recommendation after upload; "Why?" button navigates to Why screen with ranked list

**M8 — ElevenLabs TTS**
- Backend: `/recommend` calls ElevenLabs with recommendation text, returns audio bytes alongside JSON
- Frontend: Voice screen plays returned audio automatically via `expo-av`

**M9 — Polish**
- Backend: none
- Frontend: Dashboard utilization bars, highlight winning card, Why screen ranked breakdown with value + utilization flag, Nessie transaction history on card detail

**M10 — Stretch: spending trends**
- Backend: `GET /dashboard/trends` — aggregate Nessie purchase history by category per card
- Frontend: spending trend rows on Dashboard per card

**M11 — Demo + submission**
- Full end-to-end run-throughs
- Devpost write-up + required demo video

## 9. Open items to confirm once you're in VectorMint's docs/playground
- Exact convention their reward-rate fields use (flat %, points-per-dollar, or something else) so `estimated_value` is computed correctly — adjust the formula in §6 once confirmed.
- Whether their 250-card catalog includes your specific 5 real cards, or if any need to be entered as a manual fallback (their docs mention provenance/change-history tracking, so coverage is likely good, but worth a quick check on your actual 5 before Day 1 is over).
