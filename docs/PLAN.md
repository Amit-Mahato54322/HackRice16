# CreditPick — Full Plan

## 1. Problem
Someone standing in a store with several credit cards doesn't know which one earns the most for that purchase, or whether using it pushes them past a utilization level they care about. Existing reward-optimizer apps (Kudos, CardPointers, MaxRewards) validate real demand, but all of them do the same thing: merchant → category → highest-rate lookup. That's a dictionary, not an optimizer. None of them split a purchase across a partially-exhausted cap, weigh purchase protection against raw cash back, or trade rewards against credit-score damage. Scoring every card in dollars — reward *and* protection *and* float *minus* a utilization risk penalty — is the differentiator here.

## 2. User Flow
1. User opens the app to a seeded demo wallet. No signup, no login — the wallet is pre-populated and the same every run.
2. Dashboard shows every card with balance, credit limit, utilization %, and remaining category cap headroom.
3. User enters a purchase — merchant and amount (typed, or spoken if the voice layer ships).
4. Backend maps merchant → category, then scores every card in the wallet: `score = reward + protection + float − risk_penalty`.
5. The winning card is displayed with a one-line `why` string and the full dollar breakdown of all four terms, so the reasoning is visible rather than asserted.
6. User taps "Why?" to see every card ranked, each with its own breakdown — plus disqualified cards and the reason each was skipped.
7. User taps "I used this card" to commit the purchase. Balance rises, the category cap fills, sign-up bonus progress advances. Spend groceries repeatedly and the recommendation flips live as the 6% cap exhausts.
8. User toggles "buying a house in 12 months." `dollars_per_fico_point` jumps from ~$2 to ~$50 and the engine starts refusing cash back to protect the score.
9. Reset button restores the seeded wallet. The demo will be run four or five times and needs a clean slate each run.

## 3. Architecture

```
[Phone: merchant + amount] --> [Backend: POST /recommend]
                                    |
                                    v
                        categorize.py (merchant -> category)
                                    |
                                    v
                     WalletState (in-memory dict: balances,
                     limits, cap_used, sub_progress, dates)
                                    +
                       card_db.json (rates, caps, subs,
                       protections, point values)
                                    |
                                    v
                    Scoring engine (scores every card in dollars,
                    applies disqualifiers, ranks, builds breakdown)
                                    |
                                    v
        [Phone: winning card + why + full ranked breakdown]
```

Mobile (Expo) talks only to the FastAPI backend. The engine itself is pure Python — no framework, no I/O, no network, no LLM anywhere in the scoring path. It is deterministic and explainable line by line: if a judge asks how a number was produced, we point at the arithmetic.

## 4. Data Model (in-memory — no database)

A database is a liability on this timeline. State is a module-level dict in `api/wallet.py`, reset via `POST /reset`.

- **card_db.json** — 15 cards, keyed by card id: `name`, `annual_fee`, `point_value` (cents per point; 1.0 for cash back, higher for transferable), `base_rate`, `rates` (category → bonus rate), `caps` (category → annual dollar cap; absent = uncapped), `sub` (`{value, min_spend, window_days}` or null), `protection` (`{warranty_years, purchase_protection, price_protection}`)
- **WalletState** — `dollars_per_fico_point`, `protection_mode`, and per card: `balance`, `limit`, `cap_used` (category → dollars), `sub_progress`, `statement_close`

Statement close dates are generated relative to today at seed time so the demo doesn't rot. The card catalog is static reference data; the wallet is the only thing that mutates.

Card DB composition matters more than count: at least one high-rate-but-capped card, one flat 2% no-fee card, one with strong warranty but a weak rate, one with an active sign-up bonus, and one high-`point_value` transferable-points card. If every card has an obvious non-overlapping strength, there is no interesting behavior to demonstrate.

## 5. Key API Endpoints (FastAPI)

- `POST /recommend` — body `{merchant, amount}`; returns the winning card, score, four-term breakdown, `why` string, runner-up, the full ranked list, and disqualified cards with reasons
- `POST /purchase` — body `{card, merchant, amount}`; commits the transaction — increments `balance`, `cap_used[category]`, and `sub_progress`. This is what makes the demo interactive.
- `GET /wallet` — current wallet state: balances, limits, utilization, cap headroom, sub progress
- `POST /reset` — restores the seeded state

`/recommend` response shape:

```json
{
  "card": "amex_bcp",
  "card_name": "Amex Blue Cash Preferred",
  "score": 4.60,
  "breakdown": { "reward": 4.80, "protection": 0, "float": 0.12, "risk": -0.32 },
  "why": "6% groceries — $50 of cap left, remainder at 1%",
  "runner_up": { "card": "citi_dc", "card_name": "Citi Double Cash", "score": 1.60, "why": "2% flat, no cap" },
  "all_cards": [ ... ],
  "disqualified": [ { "card": "freedom_flex", "reason": "would exceed 95% of limit" } ]
}
```

The engine returns data and never formats for display — the client owns presentation.

## 6. Frontend Independence

Backend and frontend run as separate workstreams against one coordination point: the contract above, frozen before any engine code is written.

| Mechanism | Effect |
|---|---|
| Contract frozen in M1, committed as `api/mock/*.json` | Frontend codes against real response shapes on day one |
| Mock fixtures are complete, valid responses | Every screen buildable with no backend running at all |
| Engine is pure and importable | Backend progress never blocks on HTTP being up |
| Server is stateless across restarts (dict + `/reset`) | Frontend never needs a seeded DB or a migration |
| Post-M1 contract changes are additive only | New fields may be added; existing ones never renamed or removed |
| Permissive CORS from the first commit | Expo on a phone hits a laptop dev server with no detour |

FastAPI's auto-generated `/docs` doubles as the living integration contract.

## 7. Scoring Formula (v1)

Every card is scored in dollars. Highest score wins.

```
score = reward + protection + float − risk_penalty
```

### Disqualifiers — checked before scoring
```python
if balance + amount > limit * 0.95:                  return DISQUALIFIED
if protection_mode and (balance + amount) / limit > 0.30:  return DISQUALIFIED
```
A disqualified card is excluded from ranking but still returned with its reason, so the UI can show why it was skipped rather than silently dropping it.

### 7.1 Reward — cap-aware
```python
bonus_rate = card["rates"].get(category, card["base_rate"])
cap        = card["caps"].get(category)          # None = uncapped
bonus_part = amount if cap is None else min(amount, max(0, cap - cap_used.get(category, 0)))
rest       = amount - bonus_part
reward     = (bonus_part * bonus_rate + rest * card["base_rate"]) * card["point_value"]
```
A $300 grocery run on a card with $50 of 6% headroom is not a 6% purchase. **This split is the single most important piece of logic in the engine.**

### 7.2 Sign-up bonus
While `sub` is active (not null, `sub_progress < min_spend`), every dollar toward the minimum is worth far more than any category rate:
```python
reward += amount * (sub["value"] / sub["min_spend"])   # typically 15–25 cents/$
```
Which correctly swamps a 6% category bonus.

### 7.3 Purchase protection
Only meaningful above a threshold. Coefficients are expected-value estimates (claim probability × payout), kept as named constants so they can be tuned.
```python
WARRANTY_COEF, PURCHASE_COEF, PRICE_COEF, PROTECTION_MIN = 0.02, 0.01, 0.005, 200

if amount > PROTECTION_MIN:
    protection = (p["warranty_years"]      * amount * WARRANTY_COEF
                + p["purchase_protection"] * amount * PURCHASE_COEF
                + p["price_protection"]    * amount * PRICE_COEF)
else:
    protection = 0
```
This is why a $1,400 laptop routes to the two-extra-years-of-warranty card instead of the one paying 1% more.

### 7.4 Float
```python
float_value = amount * 0.05 * (days_until_statement_close + 21) / 365
```
Small, but it makes statement timing matter.

### 7.5 Risk penalty — the differentiator
FICO impact from utilization is not linear; it steps at thresholds.
```python
FICO_STEPS = [(0.30, 0), (0.50, 8), (0.70, 15), (0.90, 25)]

old_util = balance / limit
new_util = (balance + amount) / limit
penalty  = (fico_cost(new_util) - fico_cost(old_util)) * dollars_per_fico_point
```
`dollars_per_fico_point` defaults to ~$2; the "buying a house in 12 months" toggle raises it to ~$50, at which point the engine will give up 6% cash back to protect the score.

Utilization reports to the bureaus at **statement close**, not payment date, so a card closing tomorrow is riskier to load than one that closed yesterday:
```python
if days_to_statement_close > 20:
    penalty *= 0.3    # plenty of time to pay it down before it reports
```
Aggregate utilization (total balance / total limit) is tracked across all cards and adds a secondary penalty — FICO cares about both per-card and overall.

All tunable coefficients live as named module-level constants, never magic numbers inline.

### Edge cases to handle
- **Unrecognized merchant** → category defaults to `"other"`; every card scores at its `base_rate` rather than guessing a bonus category.
- **Category cap fully exhausted** → the entire purchase scores at `base_rate`, and the `why` string says so explicitly rather than still advertising the headline rate.
- **Every card disqualified** → return an empty recommendation with all disqualification reasons attached, so the UI can say "none of your cards can absorb this" rather than failing silently.
- **Sign-up bonus completed mid-purchase** → `sub_progress` may cross `min_spend` on commit; the bonus term applies to the whole amount in v1 rather than pro-rating the crossing dollar. Documented simplification.
- **Purchase larger than remaining cap headroom** → split across bonus and base rate; this is the primary demo case, not an edge case.
- **Zero or missing credit limit** → card excluded from scoring rather than dividing by zero.
- **Protection mode on with no qualifying card** → still return the ranked list with everything disqualified and the reason visible; never suppress the constraint just because it's universal.

## 8. Milestones

Build and test in this exact order. Stop after each step and verify before moving on.

### Day 1 — engine

**M1 — Contract freeze + scaffold**
- Backend: `api/` package skeleton; the four endpoint shapes written as literal `api/mock/*.json` files and committed *before* any engine code; permissive CORS. Done when the frontend can build screens against the fixtures with no backend running.
- Frontend: Expo project init, Expo Router layout, Dashboard / Purchase / Why screens stubbed, wired to the mock fixtures.

**M2 — Card DB + wallet state**
- Backend: `card_db.json` expanded to 15 cards with the composition described in §4; `wallet.py` with the seed wallet, rigged for the demo — one card with ~$50 of grocery cap left, one at 68% utilization, one with an active sign-up bonus. Done when both load and shapes validate.
- Frontend: Dashboard renders real card rows from `GET /wallet`.

**M3 — Reward term only**
- Backend: `engine.py` — loop cards, apply the cap-aware split, score, sort. Nothing else. Done when `test_cap_split` passes: $300 groceries with $50 headroom splits 50@6% + 250@1%.
- Frontend: Purchase screen posts to `/recommend`, shows the winning card.

**M4 — Sign-up bonus term**
- Backend: the `sub` term. Done when `test_sub_dominates` passes — an active sign-up bonus outranks a 6% category card.
- Frontend: none.

**M5 — Risk penalty + disqualifiers**
- Backend: FICO step table, old-vs-new utilization delta, the `>20 days to close` × 0.3 discount, aggregate-utilization secondary penalty, both disqualifiers. Done when `test_utilization_blocks` and `test_mortgage_mode` pass.
- Frontend: utilization bars on Dashboard; "buying a house" toggle.

### Day 2 — API, polish, demo

**M6 — Protection + float terms**
- Backend: protection above the $200 threshold, float from statement timing. Done when `test_protection_wins` passes — a $1,400 purchase picks the warranty card over a higher rate.
- Frontend: none.

**M7 — `why` strings + breakdown**
- Backend: per-card `why` sentence and the four-term breakdown dict, matching the M1 contract exactly.
- Frontend: Why screen — full ranked list, per-card breakdown, disqualified cards with reasons.

**M8 — FastAPI wrapper**
- Backend: `main.py` — the four endpoints, thin; `/purchase` commits, `/reset` reseeds. Done when `/docs` renders and responses match the M1 fixtures field for field.
- Frontend: swap the mock base URL for the live server. Should be a one-line change.

**M9 — Polish**
- Backend: none.
- Frontend: cap-headroom indicators, winning-card highlight, commit-purchase button, reset button.

**M10 — Stretch: voice layer**
- Backend: `POST /recommend` also accepts audio; Gemini extracts `{merchant, amount}`; `why` string sent to ElevenLabs, audio returned alongside the JSON.
- Frontend: record button with `expo-av`, plays the returned audio.

**M11 — Demo + submission**
- Four beats, ninety seconds, two surprises: (1) $80 at HEB → the 6% card, establishing the baseline works; (2) $1,400 laptop → *not* the highest-rate card, the warranty card — first surprise; (3) judge spends groceries until the cap exhausts and the recommendation flips live; (4) toggle "buying a house" and the engine gives up 6% to protect the score — second surprise.
- Rehearse three times. Devpost write-up + demo video.

**Feature freeze at T+8h.** Teams lose hackathons by adding features at hour 13.

## 9. Tests

`api/test_engine.py` — plain asserts, no pytest fixtures, runnable as `python api/test_engine.py`. These five cases are the demo; they must stay green while coefficients get tuned at 3 AM.

| Test | Asserts |
|---|---|
| `test_cap_split` | $300 groceries with $50 cap headroom splits 50@6% + 250@1% |
| `test_sub_dominates` | an active sign-up bonus outranks a 6% category card |
| `test_protection_wins` | a $1,400 purchase picks the warranty card over a higher rate |
| `test_utilization_blocks` | a card at 68% util is not recommended for a large purchase |
| `test_mortgage_mode` | `dollars_per_fico_point=50` flips the answer vs. default |

## 10. Explicitly Out of Scope
- **Portfolio solver / PuLP** (which-cards-to-own, MILP) — phase 2, after the engine ships
- **Nessie / Capital One integration** — the engine takes a wallet state dict; no external financial data source
- **Persona identity gate**
- Database, migrations, ORM, auth, signup, Docker, TypeScript
- Annual-fee and APR-aware scoring (v1 is reward + protection + float − risk only)
- Debit cards; multi-user accounts

The existing `/backend` tree (FastAPI + SQLAlchemy + Postgres + Plaid + Gemini) belongs to an earlier version of this product and is **deprecated**. Nothing in this plan touches it; all new work lands in `/api`.

## 11. Honest Limitations
State these before a judge finds them. Getting caught overclaiming is worse than a narrower true claim.
- The card database is 15 hand-entered cards with simplified reward terms. The model scales to 200 without changes; data entry is the bottleneck, not the math.
- Protection and FICO coefficients are expected-value estimates, not derived from claims data. The contribution is modeling risk as a dollar-denominated penalty against reward — the coefficients are calibratable.
- Merchant → category mapping is the real-world error source. Issuers pay on merchant category codes and there is no public MCC dataset.
- The wallet is seeded, not connected to real accounts. The engine's input contract is the same either way.
- No Apple Wallet integration. Apple provides no API to read Wallet contents or influence Apple Pay selection. A platform restriction, not a gap in the build.

## 12. Open Items
- Tune the protection coefficients so the $1,400 laptop case wins by a visible margin rather than a rounding error — if the gap is under ~$5 it won't read on a demo screen.
- Confirm the aggregate-utilization secondary penalty doesn't double-count against the per-card penalty; pick a weight that keeps per-card dominant.
- Decide whether the sign-up bonus term should pro-rate the dollar that crosses `min_spend`. v1 does not; revisit only if it produces a visibly wrong number.
