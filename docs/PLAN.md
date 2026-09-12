# CreditPick — Full Plan

## 1. Problem
Someone standing in a store with several credit cards doesn't know which one earns the most for that purchase, or whether using it pushes them past a utilization level they care about. Existing reward-optimizer apps exist (CardPointers, MaxRewards) validating real demand, but the voice-in-the-checkout-line moment plus utilization-aware scoring is the differentiator here.

## 2. User Flow
1. User signs in (seeded demo user, JWT auth).
2. User connects cards via Plaid Link (Sandbox) — or the demo uses pre-seeded/pre-linked cards.
3. After linking, the user maps each linked account to a real card product via a VectorMint-backed searchable picker (necessary because Plaid Sandbox doesn't return real card identities — this step is needed regardless of Sandbox vs Production).
4. Dashboard shows connected cards, balances, credit limit, and utilization %.
5. User taps the voice button and speaks a purchase description, e.g. "I'm buying groceries at Whole Foods, around $90."
6. Audio is uploaded to the backend, sent to Gemini (audio in, structured JSON out) → `{merchant, amount, category}`. No clarifying follow-up questions in v1 — single shot only.
7. Backend scores every eligible (credit) card using its VectorMint reward rate for that category × amount, plus the utilization impact of the purchase on that card.
8. The top recommendation is turned into a natural-language response, sent to ElevenLabs TTS, and the returned audio plays on the phone; the dashboard simultaneously highlights the winning card with its reward value and utilization callout (e.g. "Use Amex Gold. 4x points on groceries, ~$3.60 value. Utilization would be 22%, below your 30% threshold.").
9. User can tap "Why?" to see every eligible card ranked, each with its estimated value and utilization impact.

## 3. Architecture

```
[Phone: record voice clip] --> [Backend: POST /recommend]
                                    |
                                    v
                          Gemini (audio -> structured JSON)
                                    |
                                    v
                    Postgres (linked cards + cached VectorMint
                        reward rates + Plaid balance/limit)
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

Mobile (Expo) talks only to the FastAPI backend. The backend is the only thing that talks to Plaid, VectorMint, Gemini, and ElevenLabs — keeps API keys off the device and keeps the mobile app thin.

## 4. Data Model (Postgres)

- **users**(id, email, password_hash)
- **linked_accounts**(id, user_id, plaid_account_id, plaid_item_id, official_name, mask, credit_limit, current_balance, last_synced_at, card_product_id nullable FK)
- **card_products**(id, vectormint_card_id, display_name, issuer, art_url, cached_reward_json, cached_at) — reward_json is the cached VectorMint response for that card's category rates
- A `linked_accounts` row with `card_product_id = null` means "linked but not yet mapped to a real card" — excluded from scoring, shown on the dashboard as "not configured."

## 5. Key API Endpoints (FastAPI)

- `POST /auth/login`
- `POST /plaid/link-token` — create a Plaid Link token for the mobile SDK
- `POST /plaid/exchange` — exchange the public token, fetch accounts (credit only), store as `linked_accounts`
- `GET /cards/search?q=` — search the VectorMint catalog, backs the card-mapping picker
- `POST /cards/map` — map a `linked_account` to a `card_product`; fetches + caches VectorMint reward data at this moment (not fetched again per recommendation)
- `GET /dashboard` — returns cards, balances, utilization for the signed-in user
- `POST /recommend` — multipart audio upload; runs the full pipeline (Gemini extraction → scoring → ElevenLabs audio); returns the audio + the full ranked breakdown as JSON for the "Why" screen

## 6. Scoring Formula (v1)

For each eligible (credit, mapped) card the user owns:

- `reward_rate` = cached VectorMint rate for (card, category); fall back to the card's general/base rate if no category-specific rate exists for that card
- `estimated_value` = `reward_rate × amount` (confirm VectorMint's point-to-dollar convention once in their docs/playground — if they express rates as points-per-dollar rather than %, adjust the multiplier accordingly; this is an open item, see §8)
- `projected_utilization` = `(current_balance + amount) / credit_limit`
- `utilization_flag` = true if `projected_utilization` crosses a fixed 30% threshold (hardcoded constant for v1, no per-user setting)
- Sort all eligible cards by `estimated_value` descending. The top card is the spoken/displayed recommendation. The full sorted list (value + utilization_flag per card) backs the "Why" screen.

### Edge cases to handle
- **Unrecognized category** (Gemini can't classify the merchant) → default to `"other"`, score using each card's general/base reward rate instead of a category-specific one.
- **Card with no cached VectorMint data** (user skipped mapping it) → excluded from scoring entirely, shown on the dashboard as "not yet configured," not silently included with a wrong rate.
- **Every eligible card would cross the utilization threshold** → still recommend the highest-value card, but visibly show the flag rather than hiding the risk — never suppress it just because it's universal.
- **Gemini returns no amount** (user didn't say one) → treat amount as null, skip the utilization-impact calculation for this query, but still rank cards by `reward_rate` alone.
- **No eligible cards at all** (nothing mapped yet) → dashboard/voice response should say so plainly and prompt the user to map a card, not fail silently.

## 7. Milestones

### Day 1 — core pipeline, no voice yet
- **M1** — Repo scaffold: FastAPI skeleton + Postgres schema; Expo skeleton with Login / Dashboard / Voice / Why screens stubbed out (no logic yet)
- **M2** — JWT login working end to end, one seeded demo user
- **M3** — Plaid Link (Sandbox) working from the app; credit-only account filter; accounts stored as `linked_accounts`
- **M4** — VectorMint integration: `/cards/search` + the card-mapping picker UI; reward data cached into `card_products` on mapping
- **M5** — Scoring engine built as a standalone, directly-testable function — call it with a hardcoded category/amount before any voice code exists, so it's validated independently

### Day 2 — voice layer + polish
- **M6** — Record audio on the phone, upload it, get back `{merchant, amount, category}` from Gemini — test against real spoken store names, not just typed text
- **M7** — Wire the voice pipeline into the scoring engine — full `/recommend` endpoint working end to end
- **M8** — ElevenLabs TTS on the response, played back on the phone
- **M9** — Dashboard + "Why" screen polish: highlight the recommended card, show utilization bars, ranked breakdown list
- **M10 (stretch)** — Add-card flow via the same Plaid Link component, reused (built for completeness, not part of the demo script)
- **M11** — Full run-throughs of the live demo, Devpost submission (write-up + required video)

## 8. Open items to confirm once you're in VectorMint's docs/playground
- Exact convention their reward-rate fields use (flat %, points-per-dollar, or something else) so `estimated_value` is computed correctly — adjust the formula in §6 once confirmed.
- Whether their 250-card catalog includes your specific 5 real cards, or if any need to be entered as a manual fallback (their docs mention provenance/change-history tracking, so coverage is likely good, but worth a quick check on your actual 5 before Day 1 is over).
