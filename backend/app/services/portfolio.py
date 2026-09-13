"""Sum recommendation history into the dashboard's savings totals."""

from __future__ import annotations


def _round(x: float) -> float:
    return round(x or 0.0, 2)


def summarize(rows: list, recent_limit: int = 10) -> dict:
    """Portfolio totals from history rows (chronological order in)."""
    if not rows:
        return {
            "transaction_count": 0,
            "total_spent": 0.0,
            "total_cashback": 0.0,
            "total_saved": 0.0,
            "total_extra_cash": 0.0,
            "avg_saved_per_txn": 0.0,
            "by_category": [],
            "timeline": [],
            "recent": [],
        }

    total_spent = sum(r.amount for r in rows)
    total_cashback = sum(r.chosen_reward for r in rows)
    total_saved = sum(r.saved for r in rows)
    total_extra_cash = sum(r.extra_cash for r in rows)

    # Per-category rollup.
    cats: dict[str, dict] = {}
    for r in rows:
        c = cats.setdefault(
            r.category, {"category": r.category, "count": 0, "spent": 0.0,
                         "cashback": 0.0, "saved": 0.0}
        )
        c["count"] += 1
        c["spent"] += r.amount
        c["cashback"] += r.chosen_reward
        c["saved"] += r.saved
    by_category = sorted(
        (
            {k: (_round(v) if isinstance(v, float) else v) for k, v in c.items()}
            for c in cats.values()
        ),
        key=lambda c: c["saved"],
        reverse=True,
    )

    # Cumulative savings timeline.
    timeline = []
    running = 0.0
    for r in rows:
        running += r.saved
        timeline.append(
            {
                "date": r.created_at.isoformat() if r.created_at else None,
                "merchant": r.merchant,
                "saved": _round(r.saved),
                "cumulative_saved": _round(running),
            }
        )

    recent = [
        {
            "date": r.created_at.isoformat() if r.created_at else None,
            "merchant": r.merchant,
            "category": r.category,
            "amount": _round(r.amount),
            "card": r.chosen_card_name,
            "cashback": _round(r.chosen_reward),
            "saved": _round(r.saved),
        }
        for r in rows[-recent_limit:][::-1]  # newest first
    ]

    return {
        "transaction_count": len(rows),
        "total_spent": _round(total_spent),
        "total_cashback": _round(total_cashback),
        "total_saved": _round(total_saved),
        "total_extra_cash": _round(total_extra_cash),
        "avg_saved_per_txn": _round(total_saved / len(rows)),
        "by_category": by_category,
        "timeline": timeline,
        "recent": recent,
    }
