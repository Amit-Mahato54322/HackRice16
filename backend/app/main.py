"""FastAPI app entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.db import Base, engine
import app.models  # noqa: F401 — registers all models on Base.metadata
from app.routers import (
    auth,
    cards,
    conversation,
    dashboard,
    nessie,
    portfolio,
    recommend,
)
from app.static_files import STATIC_DIR

Base.metadata.create_all(bind=engine)

app = FastAPI(title="CreditPick API")

# Permissive CORS from the first commit — Expo on a phone hits a laptop dev
# server with no detour (see docs/PLAN.md). Tighten before any real deploy.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serves ElevenLabs-generated clips (see app/routers/recommend.py, M8).
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(cards.router)
app.include_router(nessie.router)
app.include_router(recommend.router)
app.include_router(conversation.router)
app.include_router(portfolio.router)


@app.get("/health")
def health():
    return {"status": "ok"}
