"""Scoring engine package.

`engine` is pure -- dicts in, dicts out, no framework, no I/O. `adapter`
translates SQLAlchemy rows into what it expects. `rewards` normalizes
VectorMint payloads and carries the hand-maintained cap overlay.
"""

from app.scoring import adapter, categorize, engine, rewards

__all__ = ["adapter", "categorize", "engine", "rewards"]
