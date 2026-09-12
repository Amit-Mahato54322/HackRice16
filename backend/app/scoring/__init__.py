"""Scoring engine package.

`engine` is pure -- dicts in, dicts out, no framework, no I/O. `adapter`
translates SQLAlchemy rows (Nessie-synced accounts) into what it expects.
`rewards` loads the local card catalog, the only hand-entered data the engine
scores on. `categorize` maps a merchant to a reward category.
"""

from app.scoring import adapter, categorize, engine, rewards

__all__ = ["adapter", "categorize", "engine", "rewards"]
