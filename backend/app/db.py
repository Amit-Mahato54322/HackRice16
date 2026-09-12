"""SQLAlchemy engine/session setup (sync — see CLAUDE.md for why)."""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a request-scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create all tables from the declared models.

    Not called on app startup on purpose: the M1 stub routes only need to
    serve the committed mock/*.json fixtures, so the app should boot and
    /docs should render even before Postgres exists. Call this explicitly
    from a seed/init script once Postgres is actually running (M2/M3).
    """
    from app import models  # noqa: F401 - registers models on Base.metadata

    Base.metadata.create_all(bind=engine)
