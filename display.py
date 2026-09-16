"""
Tracks, per guild:
- which channel holds the live inventory display
- the ID of the permanent inventory message
- which channel holds trade history
"""

import json
import os
from threading import Lock


STATE_FILE = os.path.join(
    os.path.dirname(__file__),
    "display_state.json"
)

_lock = Lock()


def _load() -> dict:
    if not os.path.exists(STATE_FILE):
        return {}

    with open(STATE_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def _save(data: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_channel_id(guild_id: int):
    with _lock:
        return _load().get(
            str(guild_id),
            {}
        ).get("channel_id")


def get_message_id(guild_id: int):
    with _lock:
        return _load().get(
            str(guild_id),
            {}
        ).get("message_id")


def set_channel_id(
    guild_id: int,
    channel_id: int
) -> None:

    with _lock:
        data = _load()

        entry = data.setdefault(
            str(guild_id),
            {}
        )

        entry["channel_id"] = channel_id
        entry["message_id"] = None

        _save(data)


def set_message_id(
    guild_id: int,
    message_id: int
) -> None:

    with _lock:
        data = _load()

        entry = data.setdefault(
            str(guild_id),
            {}
        )

        entry["message_id"] = message_id

        _save(data)


def get_history_channel_id(guild_id: int):
    with _lock:
        return _load().get(
            str(guild_id),
            {}
        ).get("history_channel_id")


def set_history_channel_id(
    guild_id: int,
    channel_id: int
) -> None:

    with _lock:
        data = _load()

        entry = data.setdefault(
            str(guild_id),
            {}
        )

        entry["history_channel_id"] = channel_id

        _save(data)

def get_audit_channel_id(guild_id: int):
    with _lock:
        return _load().get(
            str(guild_id),
            {}
        ).get("audit_channel_id")


def set_audit_channel_id(
    guild_id: int,
    channel_id: int
) -> None:

    with _lock:
        data = _load()

        entry = data.setdefault(
            str(guild_id),
            {}
        )

        entry["audit_channel_id"] = channel_id

        _save(data)