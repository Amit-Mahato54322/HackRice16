# Project: CreditPick

## Goal
A mobile app that recommends the best credit card to use for a purchase in real time, by voice. The user says what they're buying and where; the app scores every linked card by expected reward value and utilization impact, then speaks and displays the best choice. Built for HackRice 16 (Fintech track), ~2-day build.

## Scope & Non-Goals
- In scope: Plaid Link (Sandbox) card connection, VectorMint-backed reward data, voice input → Gemini extraction → card scoring → ElevenLabs spoken recommendation, dashboard with cards + utilization, "Why" screen with full ranked breakdown, add-card flow (built, not part of the demo script).
- Explicitly OUT of scope (v1): clarifying/multi-turn voice dialogue (single-shot voice only, no follow-up questions), real Plaid Production access, signup/password-reset flows, debit cards, annual-fee/APR-aware scoring (v1 scoring is reward value + utilization only), multi-user accounts beyond one seeded demo login.

## Stack & Key Decisions
- **Mobile:** Expo (React Native), plain JS (not TS), Expo Router, `expo-av` for recording, `react-native-plaid-link-sdk` — chosen over a bare RN app or native build because Expo Go demos live on a real phone with no build/store step.
- **Backend:** FastAPI + sync SQLAlchemy + PostgreSQL — sync chosen over async to avoid await-related bugs under time pressure; FastAPI still runs sync routes in a threadpool, so this costs little.
- **Card reward data:** VectorMint API (250-card catalog, reward categories/rates, free tier 5k req/month) — replaces any hand-maintained reward database entirely.
- **Voice in:** raw audio clip → Gemini (audio input + structured JSON schema output) does transcription + extraction in one call, returning `{merchant, amount, category}`. No separate STT service.
- **Voice out:** ElevenLabs TTS, single-shot response only (no agent platform, no multi-turn — clarifying questions are explicitly out of scope for v1).
- **Plaid:** Sandbox environment, credit-card accounts only. Used for account linking + balance/utilization data — NOT for reward data (VectorMint owns that).
- **Known limitations (accepted tradeoffs):**
  - Plaid Sandbox returns fake institution/account data, so every linked account must be manually mapped by the user to a real VectorMint card product after linking (there's no way to auto-match a Sandbox account to a real card).
  - Gemini's audio-native extraction may be slightly less consistent than a dedicated ASR model — acceptable for a demo, revisit if accuracy is a problem in practice.
  - The live demo depends on network connectivity for every voice query (Plaid + Gemini + VectorMint + ElevenLabs are all remote calls).

## Conventions
- Monorepo layout: `/backend` (FastAPI), `/mobile` (Expo), `/docs` (this plan).
- Secrets (Plaid, Gemini, ElevenLabs, VectorMint keys) via `.env`, never committed.
- Cache VectorMint responses in Postgres at card-mapping time — don't hit VectorMint live on every recommendation call.

## Current Status
- Done: brainstorm + architecture locked in
- In progress: —
- Next: M1 — scaffold backend + mobile skeleton (see docs/PLAN.md)

## Full Plan
See `docs/PLAN.md` for architecture, data model, scoring formula, edge cases, and the full milestone list.
