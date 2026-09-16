"""
JSON-backed inventory store.

Each Discord server has:
- a normal item inventory
- a separate currency inventory

Currency:
    1 DL = 100 WL
    1 BGL = 100 DL
    1 BGL = 10,000 WL
"""

import json
import os
from threading import Lock

INVENTORY_FILE = os.path.join(os.path.dirname(__file__), "inventory.json")
_lock = Lock()


def _load() -> dict:
    if not os.path.exists(INVENTORY_FILE):
        return {}

    with open(INVENTORY_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def _save(data: dict) -> None:
    with open(INVENTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _get_guild_data(data: dict, guild_id: int) -> dict:
    guild_data = data.setdefault(str(guild_id), {})

    # Keep old inventories working.
    if "items" not in guild_data:
        old_items = {
            key: value
            for key, value in guild_data.items()
            if key not in ("items", "currency")
        }

        guild_data.clear()
        guild_data["items"] = old_items
        guild_data["currency"] = {}

    guild_data.setdefault("items", {})
    guild_data.setdefault("currency", {})

    return guild_data


# =========================
# NORMAL ITEMS
# =========================

def get_inventory(guild_id: int) -> dict:
    with _lock:
        data = _load()
        guild_data = _get_guild_data(data, guild_id)

        return dict(guild_data["items"])


def add_item(guild_id: int, item_name: str, qty: int = 1) -> int:
    """Add qty of item_name, return new quantity."""

    with _lock:
        data = _load()
        guild_data = _get_guild_data(data, guild_id)
        items = guild_data["items"]

        item_name = " ".join(
            item_name.strip().split()
        ).title()

        items[item_name] = items.get(item_name, 0) + qty

        _save(data)

        return items[item_name]


def remove_item(guild_id: int, item_name: str, qty: int = 1) -> int:
    """Remove qty of item_name, floored at 0."""

    with _lock:
        data = _load()
        guild_data = _get_guild_data(data, guild_id)

        items = guild_data["items"]

        current = items.get(item_name, 0)
        new_qty = max(0, current - qty)

        if new_qty == 0:
            items.pop(item_name, None)
        else:
            items[item_name] = new_qty

        _save(data)

        return new_qty


def set_item(guild_id: int, item_name: str, qty: int) -> int:
    with _lock:
        data = _load()
        guild_data = _get_guild_data(data, guild_id)

        items = guild_data["items"]

        item_name = " ".join(
            item_name.strip().split()
        ).title()

        if qty <= 0:
            items.pop(item_name, None)
            qty = 0
        else:
            items[item_name] = qty

        _save(data)

        return qty


def find_item_key(guild_id: int, item_name_guess: str):
    """Case-insensitive lookup with normalized capitalization."""

    inv = get_inventory(guild_id)

    normalized_guess = " ".join(
        item_name_guess.strip().split()
    ).title()

    for key in inv:
        normalized_key = " ".join(
            key.strip().split()
        ).title()

        if normalized_key == normalized_guess:
            return key

    return None


# =========================
# CURRENCY
# =========================

VALID_CURRENCIES = ("BGL", "DL", "WL")


def get_currency(guild_id: int) -> dict:
    """Return the server's currency inventory."""

    with _lock:
        data = _load()
        guild_data = _get_guild_data(data, guild_id)

        return dict(guild_data["currency"])


def add_currency(guild_id: int, currency: str, qty: int = 1) -> int:
    """Add currency and automatically convert WL -> DL and DL -> BGL."""

    currency = currency.upper()

    if currency not in VALID_CURRENCIES:
        raise ValueError(f"Invalid currency: {currency}")

    with _lock:
        data = _load()
        guild_data = _get_guild_data(data, guild_id)

        currencies = guild_data["currency"]

        currencies[currency] = currencies.get(currency, 0) + qty

        # Convert every 100 WL into 1 DL
        wl = currencies.get("WL", 0)

        if wl >= 100:
            extra_dl = wl // 100
            currencies["DL"] = currencies.get("DL", 0) + extra_dl
            currencies["WL"] = wl % 100

        # Convert every 100 DL into 1 BGL
        dl = currencies.get("DL", 0)

        if dl >= 100:
            extra_bgl = dl // 100
            currencies["BGL"] = currencies.get("BGL", 0) + extra_bgl
            currencies["DL"] = dl % 100

        _save(data)

        # Return the final quantity of the currency that was added.
        return currencies.get(currency, 0)


def remove_currency(guild_id: int, currency: str, qty: int = 1) -> int:
    """
    Remove currency while automatically breaking down larger denominations.

    1 DL = 100 WL
    1 BGL = 100 DL = 10,000 WL

    If there is not enough total currency, nothing is removed.
    """

    currency = currency.upper()

    if currency not in VALID_CURRENCIES:
        raise ValueError(f"Invalid currency: {currency}")

    if qty <= 0:
        return get_currency(guild_id).get(currency, 0)

    with _lock:
        data = _load()
        guild_data = _get_guild_data(data, guild_id)
        currencies = guild_data["currency"]

        bgl = currencies.get("BGL", 0)
        dl = currencies.get("DL", 0)
        wl = currencies.get("WL", 0)

        # Convert the entire balance to WL
        total_wls = (
            bgl * 10000
            + dl * 100
            + wl
        )

        values = {
            "WL": 1,
            "DL": 100,
            "BGL": 10000
        }

        remove_wls = qty * values[currency]

        # Not enough currency: make NO changes
        if remove_wls > total_wls:
            return currencies.get(currency, 0)

        # Remove the requested value
        total_wls -= remove_wls

        # Rebuild the inventory using the largest denominations first
        new_bgl = total_wls // 10000
        remainder = total_wls % 10000

        new_dl = remainder // 100
        new_wl = remainder % 100

        # Replace the old currency inventory
        currencies.clear()

        if new_bgl > 0:
            currencies["BGL"] = new_bgl

        if new_dl > 0:
            currencies["DL"] = new_dl

        if new_wl > 0:
            currencies["WL"] = new_wl

        _save(data)

        return currencies.get(currency, 0)


def set_currency(guild_id: int, currency: str, qty: int) -> dict:
    currency = currency.upper()

    if currency not in VALID_CURRENCIES:
        raise ValueError(f"Invalid currency: {currency}")

    if qty < 0:
        raise ValueError("Currency quantity cannot be negative.")

    values = {
        "WL": 1,
        "DL": 100,
        "BGL": 10000
    }

    total_wls = qty * values[currency]

    new_bgl = total_wls // 10000
    remainder = total_wls % 10000

    new_dl = remainder // 100
    new_wl = remainder % 100

    with _lock:
        data = _load()
        guild_data = _get_guild_data(data, guild_id)

        currencies = guild_data["currency"]

        currencies.clear()

        if new_bgl > 0:
            currencies["BGL"] = new_bgl

        if new_dl > 0:
            currencies["DL"] = new_dl

        if new_wl > 0:
            currencies["WL"] = new_wl

        _save(data)

        return dict(currencies)


def get_total_wls(guild_id: int) -> int:
    """
    Convert the entire currency inventory into World Locks.

    1 DL = 100 WL
    1 BGL = 10,000 WL
    """

    currency = get_currency(guild_id)

    bgl = currency.get("BGL", 0)
    dl = currency.get("DL", 0)
    wl = currency.get("WL", 0)

    return (bgl * 10000) + (dl * 100) + wl


def reset_inventory(guild_id: int) -> None:
    """Completely reset normal items and currency for a guild."""

    with _lock:
        data = _load()
        guild_data = _get_guild_data(data, guild_id)

        guild_data["items"] = {}
        guild_data["currency"] = {}

        _save(data)