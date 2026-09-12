# CreditPick — Backend Plan

**Scope of this document:** the scoring engine and recommendation API only.
Frontend, voice, and deploy are owned by other workstreams and coordinate with
this plan through the frozen API contract in Phase 0.

---

## 1. Problem

People with several credit cards lose $800–1,500/year using the wrong card at
the wrong time. Rotating categories, quarterly caps, sign-up bonuses, and
purchase protections are impossible to track manually.

Existing apps (Kudos, MaxRewards, CardPointers) do a merchant → category →
highest-rate lookup. That is a dictionary, not an optimizer. None of them:

- split a purchase across a partially-exhausted cap
- weigh purchase protection against raw cash back
- trade rewards against credit-score damage

## 2. What we build

A scoring engine that treats a wallet as a portfolio: cards are holdings,
annual fees are carrying costs, credit utilization is the risk constraint.

For every purchase, each card is scored in dollars:

```
score = reward + protection + float − risk_penalty
```

The best score wins. The API returns the full breakdown so the reasoning is
visible rather than asserted — if a judge asks how a number was produced, we
point at the arithmetic.

## 3. Explicitly out of scope

- **Portfolio solver / PuLP** (which-cards-to-own, MILP) — cut
- **Nessie / Capital One integration** — cut; the engine takes a wallet state dict
- **Persona identity gate** — cut
- ElevenLabs voice and Vultr deploy — real, but owned by the integration
  workstream and outside `/api`'s scoring path
- Database, migrations, ORM, auth, Docker, TypeScript
- Any frontend

The existing `/backend` tree (FastAPI + SQLAlchemy + Postgres + Plaid + Gemini)
belongs to an earlier version of this product and is **deprecated**. It is left
in place rather than deleted, but nothing in this plan touches it. All new work
lands in `/api`.

---

## 4. Repo layout

```
api/
├── engine.py          # pure scoring — no I/O, no framework   ← the graded piece
├── categorize.py      # merchant → category keyword map
├── wallet.py          # in-memory WalletState: seed / reset / commit
├── main.py            # thin FastAPI wrapper
├── test_engine.py     # plain asserts, no pytest fixtures
├── data/
│   └── card_db.json   # 15 cards
└── mock/
    ├── recommend_heb.json      # frozen example responses
    ├── recommend_laptop.json
    ├── wallet.json
    └── README.md               # how the frontend runs against these
```

Constraints: Python, stdlib + FastAPI only. All tunable coefficients as named
module-level constants, never magic numbers inline. The engine returns data and
never formats for display — the client owns presentation. No LLM calls anywhere
in the scoring path; the engine is deterministic and explainable line by line.
Target: `engine.py` under ~300 lines. If it grows past that, something is
over-engineered.

---

## 5. Data structures

### Card database — `api/data/card_db.json`

```json
{
  "amex_bcp": {
    "name": "Amex Blue Cash Preferred",
    "annual_fee": 95,
    "point_value": 1.0,
    "base_rate": 0.01,
    "rates":  { "groceries": 0.06, "gas": 0.03 },
    "caps":   { "groceries": 6000 },
    "sub":    { "value": 250, "min_spend": 3000, "window_days": 180 },
    "protection": { "warranty_years": 1, "purchase_protection": true, "price_protection": false }
  }
}
```

- `rates` — category bonus rates; categories not listed fall back to `base_rate`
- `caps` — annual dollar cap on the bonus rate for that category; absent = uncapped
- `point_value` — cents per point; 1.0 for cash back, higher for transferable points
- `sub` — sign-up bonus; `null` if not applicable or already earned

### Wallet state — `api/wallet.py`

```python
{
  "dollars_per_fico_point": 2.0,   # raised to ~50 in credit-protection mode
  "protection_mode": False,        # "buying a house in 12 months"
  "cards": {
    "amex_bcp": {
      "balance": 1240.00,
      "limit": 5000.00,
      "cap_used": { "groceries": 1450.00 },
      "sub_progress": 800.00,
      "statement_close": "2026-09-28"
    }
  }
}
```

Held in a module-level dict. Statement close dates are generated relative to
today at seed time so the demo does not rot.

---

## 6. Scoring model

### Disqualifiers — checked before scoring

```python
if balance + amount > limit * 0.95:
    return DISQUALIFIED   # would nearly max the card

if protection_mode and (balance + amount) / limit > 0.30:
    return DISQUALIFIED   # user is protecting their score
```

A disqualified card is excluded from ranking but still appears in the response
with its reason, so the UI can show why it was skipped.

### 6.1 Reward — cap-aware

```python
bonus_rate = card["rates"].get(category, card["base_rate"])
cap        = card["caps"].get(category)          # None = uncapped

if cap is None:
    bonus_part = amount
else:
    remaining  = max(0, cap - state["cap_used"].get(category, 0))
    bonus_part = min(amount, remaining)

rest   = amount - bonus_part
reward = (bonus_part * bonus_rate + rest * card["base_rate"]) * card["point_value"]
```

A $300 grocery run on a card with $50 of 6% headroom is not a 6% purchase.
**This split is the single most important piece of logic in the engine.**

### 6.2 Sign-up bonus

While a card has an active `sub` (not null, `sub_progress < min_spend`), every
dollar toward the minimum is worth far more than any category rate:

```python
reward += amount * (sub["value"] / sub["min_spend"])
```

Typically 15–25 cents per dollar, which correctly swamps a 6% category bonus.

### 6.3 Purchase protection

Only meaningful above a threshold. Coefficients are expected-value estimates
(claim probability × payout), not derived from claims data — named constants so
they can be tuned.

```python
WARRANTY_COEF  = 0.02
PURCHASE_COEF  = 0.01
PRICE_COEF     = 0.005
PROTECTION_MIN = 200

if amount > PROTECTION_MIN:
    protection = (p["warranty_years"]      * amount * WARRANTY_COEF
                + p["purchase_protection"] * amount * PURCHASE_COEF
                + p["price_protection"]    * amount * PRICE_COEF)
else:
    protection = 0
```

This is why a $1,400 laptop routes to the two-extra-years-of-warranty card
instead of the one paying 1% more.

### 6.4 Float

```python
days_free   = days_until_statement_close(card) + 21   # grace period
float_value = amount * 0.05 * days_free / 365
```

Small, but it makes statement timing matter.

### 6.5 Risk penalty — the differentiator

FICO impact from utilization is not linear; it steps at thresholds.

```python
FICO_STEPS = [(0.30, 0), (0.50, 8), (0.70, 15), (0.90, 25)]

def fico_cost(util):
    cost = 0
    for threshold, points in FICO_STEPS:
        if util >= threshold:
            cost = points
    return cost

old_util = balance / limit
new_util = (balance + amount) / limit
penalty  = (fico_cost(new_util) - fico_cost(old_util)) * state["dollars_per_fico_point"]
```

`dollars_per_fico_point` defaults to ~$2. The "buying a house in 12 months"
toggle raises it to ~$50, at which point the engine will refuse 6% cash back to
protect the score.

Utilization reports to the bureaus at **statement close**, not payment date, so
a card closing tomorrow is riskier to load than one that closed yesterday:

```python
if days_to_statement_close > 20:
    penalty *= 0.3   # plenty of time to pay it down before it reports
```

Aggregate utilization (total balance / total limit) is tracked across all cards
and adds a secondary penalty — FICO cares about both per-card and overall.

---

## 7. API contract

```
POST /recommend   { "merchant": "HEB", "amount": 80.00 }
POST /purchase    { "card": "amex_bcp", "merchant": "HEB", "amount": 80.00 }
GET  /wallet
POST /reset
```

`/recommend` response:

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

- `POST /purchase` commits the transaction: increments `balance`,
  `cap_used[category]`, and `sub_progress`. This is what makes the demo
  interactive — a judge can spend groceries repeatedly and watch the cap
  exhaust and the recommendation flip live.
- `POST /reset` restores the seeded state. We will run the demo four or five
  times and need a clean slate each run.

Merchant → category is a keyword dict (`"HEB" → groceries`). Nothing clever;
real-world merchant category codes are a hard problem we are explicitly not
solving tonight.

---

## 8. Build order

Build and test in this exact order. Stop after each step and verify before
moving on.

| # | Step | Verified by |
|---|------|-------------|
| 0 | Freeze the API contract as `api/mock/*.json`; enable CORS | frontend can start |
| 1 | `card_db.json` (15 cards) + `wallet.py` seed state | loads, shapes correct |
| 2 | **Reward term only.** Loop cards, score, sort | `test_cap_split` |
| 3 | Sign-up bonus term | `test_sub_dominates` |
| 4 | Risk penalty + disqualifiers | `test_utilization_blocks`, `test_mortgage_mode` |
| 5 | Protection term | `test_protection_wins` |
| 6 | Float term, `why` strings, breakdown dict | all five green |
| 7 | FastAPI wrapper (`main.py`) | `/docs` renders; endpoints match Phase 0 |

### Card DB composition

15 cards, chosen so the answers are not trivially obvious: at least one
high-rate-but-capped card, one flat 2% no-fee card, one with strong warranty but
a weak rate, one with an active sign-up bonus, and one high-`point_value`
transferable-points card. If every card has an obvious non-overlapping strength,
there is no interesting behavior to demonstrate.

---

## 9. Tests — `api/test_engine.py`

Plain asserts, no pytest fixtures, runnable as `python api/test_engine.py`.
These five cases are the demo; they must stay green while coefficients get
tuned at 3 AM.

| Test | Asserts |
|------|---------|
| `test_cap_split` | $300 groceries with $50 cap headroom splits 50@6% + 250@1% |
| `test_sub_dominates` | an active sign-up bonus outranks a 6% category card |
| `test_protection_wins` | a $1,400 purchase picks the warranty card over a higher rate |
| `test_utilization_blocks` | a card at 68% util is not recommended for a large purchase |
| `test_mortgage_mode` | `dollars_per_fico_point=50` flips the answer vs. default |

---

## 10. How backend and frontend work independently

1. **The contract is frozen in Phase 0**, before any engine work, and committed
   as JSON. It is the only coordination point between the two workstreams.
2. **Mock mode:** `api/mock/*.json` are valid, complete responses. The frontend
   can import them directly or serve them statically and build every screen
   with no backend running at all.
3. **The engine is pure** — importable and unit-testable with no server — so
   backend progress never blocks on HTTP being up.
4. **The server is stateless across restarts** (in-memory dict + `/reset`), so
   the frontend never needs a seeded database or a migration to get a working
   environment.
5. **Contract changes after Phase 0 are additive only** — new fields may be
   added, existing ones are never renamed or removed.
6. CORS is permissive from the first commit, so Expo on a phone can hit a
   laptop's dev server without a debugging detour.

---

## 11. Honest limitations

State these before a judge finds them. Getting caught overclaiming is worse
than a narrower true claim.

- The card database is 15 hand-entered cards with simplified reward terms. The
  model scales to 200 without changes; data entry is the bottleneck, not math.
- Protection and FICO coefficients are estimates, not derived from claims data.
  The contribution is modeling risk as a dollar-denominated penalty against
  reward — the coefficients are calibratable.
- Merchant → category mapping is the real-world error source. Issuers pay on
  merchant category codes and there is no public MCC dataset.
- No Apple Wallet integration. Apple provides no API to read Wallet contents or
  influence Apple Pay selection. A platform restriction, not a gap in the build.

## 12. Roadmap (post-hackathon)

- Portfolio solver — which cards to own, as a MILP (cut from v1)
- Monitoring mode — re-solve monthly, notify only when the answer changes
- Effective annual fee — `stated_fee − credits_actually_used`
- Counterfactual ledger — replay last year against the optimal policy
- Annual-fee and APR-aware scoring
