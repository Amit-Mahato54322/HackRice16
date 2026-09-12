"""FastAPI app entrypoint. Scaffold only — see docs/PLAN.md for M1."""

from fastapi import FastAPI

app = FastAPI(title="SmartSwipe API")


@app.get("/health")
def health():
    return {"status": "ok"}
