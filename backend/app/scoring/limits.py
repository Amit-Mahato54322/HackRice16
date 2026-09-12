"""User-entered credit limits.

Nessie's account object has no credit limit field, and no API publishes one.
The user does know it, though -- it is printed on their statement and shown in
their banking app -- so it is entered by hand, per card, and stored here.

This is user-supplied input, the same category as the utilization ceiling. It
is not a figure we invented: a limit nobody has entered stays `None`, and the
engine disqualifies that card with a reason rather than guessing a value.

In-memory on purpose. Once Postgres is running these belong on
`LinkedAccount.credit_limit`, which already exists -- `set_limit` is then a
column write and `all_limits` a query. Nothing else changes.
"""

_LIMITS = {}


def set_limit(card_key, limit):
    """Record a user-entered limit. `None` or 0 clears it."""
    if limit is None or float(limit) <= 0:
        _LIMITS.pop(card_key, None)
        return None
    _LIMITS[card_key] = float(limit)
    return _LIMITS[card_key]


def get_limit(card_key):
    return _LIMITS.get(card_key)


def all_limits():
    return dict(_LIMITS)


def clear():
    _LIMITS.clear()


def apply(state):
    """Overlay entered limits onto a wallet state, in place.

    A card with no entered limit keeps whatever the state already carries,
    which is `None` for anything Nessie synced.
    """
    for card_key, card_state in state["cards"].items():
        entered = _LIMITS.get(card_key)
        if entered is not None:
            card_state["limit"] = entered
    return state
