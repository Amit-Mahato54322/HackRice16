# Project: CreditPick

## Goal
A mobile app that recommends the best credit card to use for a purchase in real time, by voice. The user says what they're buying and where; the app scores every linked card by expected reward value and utilization impact, then speaks and displays the best choice. Built for HackRice 16 (Fintech track), ~2-day build.

## Scope & Non-Goals
- In scope: Capital One Nessie API for mock credit account + merchant data, VectorMint-backed reward data, voice input → Gemini extraction → card scoring → ElevenLabs spoken recommendation, dashboard with cards + utilization, "Why" screen with full ranked breakdown.
- Explicitly OUT of scope (v1): clarifying/multi-turn voice dialogue (single-shot voice only, no follow-up questions), real banking API access, signup/password-reset flows, debit cards, annual-fee/APR-aware scoring (v1 scoring is reward value + utilization only), multi-user accounts beyond one seeded demo login.

## Stack & Key Decisions
- **Mobile:** Expo (React Native), plain JS (not TS), Expo Router, `expo-av` for recording — chosen over a bare RN app or native build because Expo Go demos live on a real phone with no build/store step.
- **Backend:** FastAPI + sync SQLAlchemy + PostgreSQL — sync chosen over async to avoid await-related bugs under time pressure; FastAPI still runs sync routes in a threadpool, so this costs little.
- **Card reward data:** VectorMint API (250-card catalog, reward categories/rates, free tier 5k req/month) — replaces any hand-maintained reward database entirely.
- **Voice in:** raw audio clip → Gemini (audio input + structured JSON schema output) does transcription + extraction in one call, returning `{merchant, amount, category}`. No separate STT service.
- **Voice out:** ElevenLabs TTS, single-shot response only (no agent platform, no multi-turn — clarifying questions are explicitly out of scope for v1).
- **Capital One Nessie API:** Mock banking sandbox — credit accounts (balance + credit_limit), merchant catalog with categories, transaction history. Replaces Plaid. No OAuth; just an API key + pre-seeded customer ID. Chosen to target the Capital One "Best Use of Nessie" prize at HackRice 16. Nessie's merchant catalog also cross-references Gemini's category extraction for higher accuracy.
- **Known limitations (accepted tradeoffs):**
  - Nessie is mock data, so each account must be manually mapped to a real VectorMint card product (no auto-match between mock account names and real card products).
  - Gemini's audio-native extraction may be slightly less consistent than a dedicated ASR model — acceptable for a demo, revisit if accuracy is a problem in practice.
  - The live demo depends on network connectivity for every voice query (Nessie + Gemini + VectorMint + ElevenLabs are all remote calls).

## Conventions
- Monorepo layout: `/backend` (FastAPI), `/mobile` (Expo), `/docs` (this plan).
- Secrets (Nessie, Gemini, ElevenLabs, VectorMint keys) via `.env`, never committed.
- Cache VectorMint responses in Postgres at card-mapping time — don't hit VectorMint live on every recommendation call.

## Current Status
- Done: brainstorm + architecture locked in; M1 backend scaffold (models, db/config, mock fixtures, auth/dashboard/cards/recommend routers serving fixtures, nessie router stubbed 501, CORS + /health) — smoke-tested end to end with no Postgres needed
- In progress: M1 mobile skeleton (Expo screens) — not yet started
- Next: finish M1 frontend, then M2 (see docs/PLAN.md)

## Full Plan
See `docs/PLAN.md` for architecture, data model, scoring formula, edge cases, and the full milestone list.
