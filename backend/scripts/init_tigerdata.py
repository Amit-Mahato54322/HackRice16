"""Create CreditPick's hypertables on Tiger Data.

Run once, from backend/:

    python scripts/init_tigerdata.py

Idempotent -- CREATE TABLE IF NOT EXISTS, so re-running is safe and will not
touch existing data.

Three tables, each append-only, each recording something that is true at a
moment and then gone:

  utilization_snapshots  how loaded each card was, after every Nessie sync.
                         The reason this is the important one: utilization is
                         a snapshot the issuer reports and then overwrites.
                         Nobody -- not Nessie, not the issuer -- can tell you
                         later what it was last Tuesday. It exists only if we
                         wrote it down.

  purchases              spending as synced from Nessie's transaction history,
                         which is what any per-category analysis reads from.

  recommendations        what the engine answered and the inputs behind it, so
                         a recommendation can be audited after the fact.

The WITH clause is Tiger Data's declarative hypertable syntax: `tsdb.hypertable`
turns the table into one, `segmentby` groups rows that are queried and
compressed together, and `orderby` sets the order within each segment. Recent
data is what gets read, so every table orders time DESC.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.timeseries import cursor, dsn  # noqa: E402

SCHEMA = [
    (
        "utilization_snapshots",
        """
        CREATE TABLE IF NOT EXISTS utilization_snapshots (
            time          TIMESTAMPTZ      NOT NULL,
            account_id    TEXT             NOT NULL,
            balance       DOUBLE PRECISION NOT NULL,
            credit_limit  DOUBLE PRECISION NULL,
            utilization   DOUBLE PRECISION NULL
        ) WITH (
            tsdb.hypertable,
            tsdb.segmentby = 'account_id',
            tsdb.orderby = 'time DESC'
        );
        """,
    ),
    (
        "purchases",
        """
        CREATE TABLE IF NOT EXISTS purchases (
            time        TIMESTAMPTZ      NOT NULL,
            account_id  TEXT             NOT NULL,
            merchant    TEXT             NULL,
            category    TEXT             NULL,
            amount      DOUBLE PRECISION NOT NULL
        ) WITH (
            tsdb.hypertable,
            tsdb.segmentby = 'account_id',
            tsdb.orderby = 'time DESC'
        );
        """,
    ),
    (
        "recommendations",
        """
        CREATE TABLE IF NOT EXISTS recommendations (
            time               TIMESTAMPTZ      NOT NULL,
            user_id            TEXT             NOT NULL,
            merchant           TEXT             NULL,
            category           TEXT             NULL,
            amount             DOUBLE PRECISION NOT NULL,
            chosen_account_id  TEXT             NULL,
            reward_rate        DOUBLE PRECISION NULL,
            score              DOUBLE PRECISION NULL,
            utilization        DOUBLE PRECISION NULL,
            ceiling            DOUBLE PRECISION NULL
        ) WITH (
            tsdb.hypertable,
            tsdb.segmentby = 'user_id',
            tsdb.orderby = 'time DESC'
        );
        """,
    ),
]


def redacted(url):
    """The connection target, without the password."""
    if "@" not in url:
        return url
    scheme, rest = url.split("://", 1) if "://" in url else ("", url)
    _, host = rest.rsplit("@", 1)
    return "%s://***@%s" % (scheme, host) if scheme else "***@%s" % host


def main():
    print("Connecting to %s" % redacted(dsn()))

    with cursor() as cur:
        cur.execute("SELECT extversion FROM pg_extension WHERE extname = 'timescaledb'")
        row = cur.fetchone()
        if row is None:
            print(
                "\n  timescaledb extension not found on this database.\n"
                "  Hypertables need it. On Tiger Data it is enabled by default;\n"
                "  if you pointed DATABASE_URL at a plain Postgres, point it at\n"
                "  your Tiger Data service instead.\n"
            )
            return 1
        print("timescaledb %s" % row[0])

        for name, ddl in SCHEMA:
            cur.execute(ddl)
            print("  OK    %s" % name)

        cur.execute(
            """
            SELECT hypertable_name, num_chunks
            FROM timescaledb_information.hypertables
            WHERE hypertable_schema = 'public'
            ORDER BY hypertable_name
            """
        )
        print("\nHypertables:")
        for hypertable_name, num_chunks in cur.fetchall():
            print("  %-24s %d chunk(s)" % (hypertable_name, num_chunks))

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
