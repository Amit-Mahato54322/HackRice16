# Project: CreditPick

## Goal
A mobile app that recommends the best credit card to use for a purchase in real time, by voice. The user says what they're buying and where; the app scores every linked card by expected reward value and utilization impact, then speaks and displays the best choice. Built for HackRice 16 (Fintech track), ~2-day build.

## Scope & Non-Goals
- In scope: Capital One Nessie API for mock credit account + merchant data, a local reward-rate catalog (a VectorMint-shaped cache path exists but isn't called live yet), voice input → Gemini extraction → card scoring → ElevenLabs spoken recommendation, dashboard with cards + utilization, "Why" screen with full ranked breakdown, hand-entered credit limits (no API in the stack publishes them).
- Explicitly OUT of scope (v1): login/signup (deferred entirely — the app boots straight to a hardcoded demo user; see M2 in docs/PLAN.md), clarifying/multi-turn voice dialogue (single-shot voice only, no follow-up questions), real banking API access, debit cards, annual-fee/APR-aware scoring, category caps, sign-up bonus tracking, purchase protection, and statement-timing float (v1 scoring is reward minus a dollar-priced utilization risk term only — see docs/PLAN.md §7), multi-user accounts.

## Stack & Key Decisions
- **Mobile:** Expo (React Native), Expo Router, `expo-audio` for recording and playback (`expo-av` is superseded by it in the SDK version this project pins — see `mobile-app/AGENTS.md`) — chosen over a bare RN app or native build because Expo Go demos live on a real phone with no build/store step. `mobile-app` (the actively developed frontend) is TypeScript, not plain JS as originally planned.
- **Backend:** FastAPI + sync SQLAlchemy + PostgreSQL — sync chosen over async to avoid await-related bugs under time pressure; FastAPI still runs sync routes in a threadpool, so this costs little.
- **Card reward data:** a small hand-entered local catalog (`backend/app/scoring/card_db.json`) is the actual source today. A VectorMint-shaped cache path exists (`CardProduct.cached_reward_json`, normalized in `app/scoring/rewards.py`) for whenever `/cards/map` calls it live — not wired up yet.
- **Scoring engine:** pure Python, `score = reward - risk` — reward is a rate lookup; risk prices the FICO damage of the utilization this purchase would cause (a step function, not linear, applied per-card and wallet-wide, scaled to the user's baseline credit score) in the same dollar unit as reward, so the engine can decline a higher rate to protect a score. Category caps, sign-up bonuses, purchase protection, and statement-timing float are deliberately excluded — no API in the stack publishes the inputs they'd need, so modelling them means inventing numbers (see `app/scoring/engine.py`'s docstring for the full reasoning).
- **Voice in:** raw audio clip → Gemini (audio input + structured JSON schema output) does transcription + extraction in one call, returning `{merchant, amount, category}`. No separate STT service.
- **Voice out:** ElevenLabs TTS, single-shot response only (no agent platform, no multi-turn — clarifying questions are explicitly out of scope for v1).
- **Capital One Nessie API:** Mock banking sandbox — credit account balances, merchant catalog with categories, transaction history. No credit_limit field (confirmed by a live API probe, `backend/tests/test_nessie.py`) — that's hand-entered instead, see below. No OAuth; just an API key + pre-seeded customer ID. Chosen to target the Capital One "Best Use of Nessie" prize at HackRice 16. Nessie's merchant catalog also cross-references Gemini's category extraction for higher accuracy.
- **Known limitations (accepted tradeoffs):**
  - Nessie is mock data, so each account must be manually mapped to a real card product (no auto-match between mock account names and real card products) — until that's built (M4), `/recommend` runs on a seeded demo wallet.
  - Nessie has no credit_limit field — entered by hand once at seed time (`scripts/seed_nessie.py`) or via `PUT /cards/{card}/limit`; a card with no limit on record is disqualified, never guessed.
  - Gemini's audio-native extraction may be slightly less consistent than a dedicated ASR model — acceptable for a demo, revisit if accuracy is a problem in practice.
  - The live demo depends on network connectivity for every voice query (Nessie + Gemini + ElevenLabs are all remote calls).

## Conventions
- Monorepo layout: `/backend` (FastAPI), `/mobile` (Expo), `/docs` (this plan).
- Secrets (Nessie, Gemini, ElevenLabs, VectorMint keys) via `.env`, never committed.
- Cache VectorMint responses in Postgres at card-mapping time — don't hit VectorMint live on every recommendation call.

## Current Status
- Done: M1 (backend scaffold + `mobile-app` Expo skeleton, since superseded by a fuller build), M3 (real Nessie sync + live `/dashboard`), the scoring engine (dollar-priced reward-minus-risk model, 11 passing tests in `backend/tests/test_engine.py`), M7 (engine wired into `/recommend`, falling back to a seeded demo wallet until M4 ships), M8 (ElevenLabs TTS — backend generates real audio, `mobile-app`'s playback service plays a backend URL when present, on-device speech otherwise)
- In progress: M4 (real card mapping — `/cards/search` and `/cards/map` are still M1 stubs, so `/recommend` runs on the demo wallet for anything not hand-wired like `scripts/seed_nessie.py`'s three cards)
- Deferred: M2 (login) — out of scope for the demo, app boots straight to a hardcoded user
- Known issue: `backend/tests/test_nessie.py` has a real Nessie API key committed in plaintext — rotate it on Nessie's dashboard
- Next: M4 (real card mapping), M6 (voice capture + Gemini extraction)

## Full Plan
See `docs/PLAN.md` for architecture, data model, scoring formula, edge cases, and the full milestone list.
