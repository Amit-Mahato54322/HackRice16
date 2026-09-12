# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### Added
- M1 backend scaffold:
  - SQLAlchemy models: `User`, `LinkedAccount`, `CardProduct` (`backend/app/models/`), per the data model in `docs/PLAN.md`.
  - `backend/app/db.py` (sync engine/session, `get_db` dependency, `create_tables()` helper for a future seed script) and `backend/app/config.py` (env loading).
  - Five frozen mock fixtures under `backend/mock/`: `login.json`, `dashboard.json`, `cards_search.json`, `cards_map.json`, `recommend.json`.
  - Routers serving those fixtures: `auth`, `dashboard`, `cards`, `recommend`. A `nessie` router is also registered as a stub (501s) and is not part of the frozen contract yet.
  - `backend/app/main.py`: FastAPI app with permissive CORS, all routers registered, and a `/health` endpoint.
  - Smoke-tested end to end via `uvicorn` — every endpoint hit with correct shapes/status codes, no Postgres required (table creation is deliberately not run on startup).
- Not yet done: the mobile (Expo) half of M1.
