"""Tiger Data (Postgres + TimescaleDB) connection helpers.

The connection string comes from DATABASE_URL, the same variable the
SQLAlchemy session in db.py uses -- Tiger Data is Postgres, so one database
serves both the relational tables and the hypertables.

psycopg2 is used directly here rather than through SQLAlchemy because the
hypertable DDL and the append-only inserts are plain SQL, and there is no ORM
model worth defining for rows nothing ever updates.

Tiger Data requires TLS. If DATABASE_URL does not already ask for it, sslmode
is added, so a copied connection string works without anyone remembering.
"""

import contextlib

import psycopg2
import psycopg2.extras

from app.config import DATABASE_URL


def dsn():
    """DATABASE_URL, with TLS required if the URL does not say otherwise."""
    url = DATABASE_URL
    if "sslmode=" in url:
        return url
    return url + ("&" if "?" in url else "?") + "sslmode=require"


@contextlib.contextmanager
def connection():
    """A committed-on-success, rolled-back-on-error connection."""
    conn = psycopg2.connect(dsn())
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextlib.contextmanager
def cursor(dict_rows=False):
    """A cursor on a managed connection. `dict_rows` for name-keyed reads."""
    factory = psycopg2.extras.RealDictCursor if dict_rows else None
    with connection() as conn:
        with conn.cursor(cursor_factory=factory) as cur:
            yield cur


# --- writes ----------------------------------------------------------------
#
# Every table here is append-only: a row records what was true at a moment and
# is never updated. That is what makes them worth storing as time series
# rather than as columns on linked_accounts.


def record_utilization(account_id, balance, credit_limit, at=None):
    """One account's utilization at a point in time.

    Written after each Nessie sync. Utilization is a snapshot that the card
    issuer reports and then forgets, so a history of it is something neither
    Nessie nor the issuer will give you later -- it only exists if we keep it.
    """
    utilization = (balance / credit_limit) if credit_limit else None
    with cursor() as cur:
        cur.execute(
            """
            INSERT INTO utilization_snapshots
                (time, account_id, balance, credit_limit, utilization)
            VALUES (COALESCE(%s, now()), %s, %s, %s, %s)
            """,
            (at, str(account_id), balance, credit_limit, utilization),
        )


def record_purchase(account_id, merchant, category, amount, at=None):
    """One purchase, as synced from Nessie's transaction history."""
    with cursor() as cur:
        cur.execute(
            """
            INSERT INTO purchases
                (time, account_id, merchant, category, amount)
            VALUES (COALESCE(%s, now()), %s, %s, %s, %s)
            """,
            (at, str(account_id), merchant, category, amount),
        )


def record_recommendation(
    user_id, merchant, category, amount, chosen_account_id,
    reward_rate, score, utilization, ceiling=None, at=None,
):
    """What the engine answered, and the inputs it answered from.

    Logged on every /recommend call. This is what makes the engine auditable
    after the fact: given a recommendation someone questions, the row says
    what the rate and the projected utilization were at the time.
    """
    with cursor() as cur:
        cur.execute(
            """
            INSERT INTO recommendations
                (time, user_id, merchant, category, amount, chosen_account_id,
                 reward_rate, score, utilization, ceiling)
            VALUES (COALESCE(%s, now()), %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                at, str(user_id), merchant, category, amount,
                str(chosen_account_id) if chosen_account_id else None,
                reward_rate, score, utilization, ceiling,
            ),
        )
