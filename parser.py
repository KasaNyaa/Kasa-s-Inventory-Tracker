"""
Turns raw OCR text into a best-guess structured action:

    {"action": "add" | "sell" | "unknown", "item": str | None, "qty": int}

This is inherently fuzzy — OCR text from game screenshots is messy, and
"guess from the text" has no hard signal to rely on. Keyword matching is
a reasonable first pass, but it WILL be wrong sometimes. That's why the
bot asks for a reaction-confirm before touching the inventory rather than
trusting this output blindly.
"""
import re


def classify_action(text: str, sell_keywords: list, add_keywords: list) -> str:
    lower = text.lower()

    sell_hit = any(kw.lower() in lower for kw in sell_keywords)
    add_hit = any(kw.lower() in lower for kw in add_keywords)

    if sell_hit and not add_hit:
        return "sell"
    if add_hit and not sell_hit:
        return "add"
    if sell_hit and add_hit:
        # Both matched (common with generic words) — take whichever
        # keyword appears first in the text as the stronger signal.
        sell_pos = min((lower.find(kw.lower()) for kw in sell_keywords if kw.lower() in lower), default=10**9)
        add_pos = min((lower.find(kw.lower()) for kw in add_keywords if kw.lower() in lower), default=10**9)
        return "sell" if sell_pos < add_pos else "add"
    return "unknown"


# Matches "Wrench x5", "5x Wrench", "Wrench (x5)"
_QTY_ITEM_PATTERNS = [
    re.compile(r"([A-Za-z][A-Za-z0-9'\-\s]{2,40}?)\s*[x\u00d7]\s*(\d+)", re.IGNORECASE),
    re.compile(r"(\d+)\s*[x\u00d7]\s*([A-Za-z][A-Za-z0-9'\-\s]{2,40})", re.IGNORECASE),
]



def extract_trade_items(text: str):
    """
    Reads a trade message and returns separate inventory changes.

    Currency aliases:
    Diamond Lock -> DL
    World Lock -> WL
    Blue Gem Lock -> BGL
    """

    import re

    # OCR sometimes turns spaces into underscores
    text = text.replace("_", " ")
    text = re.sub(r"\s+", " ", text).strip()

    # First try a normal trade with "and received"
    match = re.search(
        r"You\s+traded\s*(.*?)\s*[‘’'\";,:.-]*\s*with\b.*?[\s;,:.-]+and[\s_]+received\s*(.*)",
        text,
        re.IGNORECASE
    )

    if match:
        given_text = match.group(1)
        received_text = match.group(2)
    else:
        # Sell-only trade:
        # You traded [4 Goat Leash] with Mother Lilith in AUCS ...
        match = re.search(
            r"You\s+traded\s*(.*?)\s*[‘’'\";,:.-]*\s*with\b.*",
            text,
            re.IGNORECASE
        )

        if not match:
            return []

        given_text = match.group(1)
        received_text = ""

    changes = []

    # Currency aliases
    currency_aliases = {
        "diamond lock": "DL",
        "world lock": "WL",
        "blue gem lock": "BGL",
    }

    def parse_items(side_text, action):
        items = re.findall(
            r"\[\s*(\d+)\s+([^\]]+?)\s*\]",
            side_text
        )

        for qty, item in items:
            item = item.strip()

            # Convert currency names from the screenshot
            alias = currency_aliases.get(item.lower())

            if alias:
                changes.append({
                    "action": action,
                    "item": alias,
                    "qty": int(qty),
                    "currency": True
                })
            else:
                changes.append({
                    "action": action,
                    "item": item,
                    "qty": int(qty),
                    "currency": False
                })

    # Items/currency given
    parse_items(given_text, "sell")

    # Items/currency received
    parse_items(received_text, "add")

    # Combine duplicates
    combined = {}

    for change in changes:
        key = (
            change["action"],
            change["item"].lower()
        )

        if key not in combined:
            combined[key] = {
                "action": change["action"],
                "item": change["item"],
                "qty": 0,
                "currency": change["currency"]
            }

        combined[key]["qty"] += change["qty"]

    return list(combined.values())