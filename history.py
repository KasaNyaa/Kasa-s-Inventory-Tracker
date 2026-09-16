"""
Trade history storage.

Stores confirmed trades for each Discord server.
"""

import json
import os
from datetime import datetime, timezone
from threading import Lock


HISTORY_FILE = os.path.join(
    os.path.dirname(__file__),
    "trade_history.json"
)

_lock = Lock()


def _load() -> dict:
    if not os.path.exists(HISTORY_FILE):
        return {}

    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def _save(data: dict) -> None:
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False
        )


def add_trade(
    guild_id: int,
    author_id: int,
    changes: list,
    fingerprint: str = None
) -> dict:

    with _lock:
        data = _load()

        guild_history = data.setdefault(
            str(guild_id),
            []
        )

        trade = {
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),
            "author_id": author_id,
            "changes": changes,
            "fingerprint": fingerprint,
            "undone": False
        }

        guild_history.append(trade)
        _save(data)
        return trade


def get_history(guild_id: int) -> list:

    with _lock:
        data = _load()

        return list(
            data.get(
                str(guild_id),
                []
            )
        )

def is_duplicate_trade(
    guild_id: int,
    fingerprint: str
) -> bool:

    if not fingerprint:
        return False

    normalized = " ".join(
        fingerprint.lower().split()
    )

    with _lock:
        data = _load()

        guild_history = data.get(
            str(guild_id),
            []
        )

        for trade in guild_history:
            if trade.get("undone", False):
                continue

            old_fingerprint = trade.get("fingerprint")

            if not old_fingerprint:
                continue

            old_normalized = " ".join(
                old_fingerprint.lower().split()
            )

            if old_normalized == normalized:
                return True

    return False

def get_last_active_trade(guild_id: int):
    with _lock:
        data = _load()

        guild_history = data.get(
            str(guild_id),
            []
        )

        for trade in reversed(guild_history):
            if not trade.get("undone", False):
                return trade

    return None


def mark_trade_undone(
    guild_id: int,
    timestamp: str
) -> bool:

    with _lock:
        data = _load()

        guild_history = data.get(
            str(guild_id),
            []
        )

        for trade in reversed(guild_history):
            if trade.get("timestamp") == timestamp:

                if trade.get("undone", False):
                    return False

                trade["undone"] = True
                _save(data)
                return True

    return False