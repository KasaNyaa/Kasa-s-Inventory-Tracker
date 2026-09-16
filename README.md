# Screenshot → Inventory Discord Bot

Reads text out of screenshots posted in your server, guesses whether it's an
item you **got** or one you **sold**, and updates a per-server inventory —
after you confirm with a ✅/❌ reaction.

## Important: why there's a confirm step

You asked for "guess from the text in the screenshot" with no command or
channel to disambiguate add-vs-sell. That's doable, but OCR + keyword
guessing on game screenshots **will misread things sometimes** (bad OCR,
unexpected wording, no keyword at all). Rather than silently corrupting
your inventory, the bot posts its guess and waits for a ✅ (confirm) or ❌
(cancel) reaction from you (or someone with an admin/mod role) before it
touches the data. If you'd rather it commit automatically, see "Going
fully automatic" at the bottom.

## 1. Install Tesseract (the OCR engine)

The Python package `pytesseract` is just a wrapper — you need the actual
Tesseract binary installed on the machine running the bot:

- **Windows**: install from https://github.com/UB-Mannheim/tesseract/wiki,
  then add its install folder to your PATH.
- **macOS**: `brew install tesseract`
- **Linux (Debian/Ubuntu)**: `sudo apt install tesseract-ocr`

## 2. Set up the project

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and paste your bot token:
```
DISCORD_BOT_TOKEN=your_token_here
```

## 3. Create the Discord bot & invite it

1. Go to https://discord.com/developers/applications → New Application.
2. Bot tab → Add Bot → copy the token into `.env`.
3. Under **Privileged Gateway Intents**, enable **Message Content Intent**.
4. OAuth2 → URL Generator → scopes: `bot`. Permissions: Send Messages,
   Read Message History, Add Reactions, Embed Links, Attach Files.
5. Open the generated URL and invite it to your server.

## 4. Configure `config.json`

```json
{
  "listen_channel_ids": [],
  "admin_role_names": ["Admin", "Moderator"],
  "sell_keywords": ["sold", "you sold", "sale complete"],
  "add_keywords": ["you received", "you got", "picked up"]
}
```

- `listen_channel_ids`: leave empty to watch every channel, or list channel
  IDs (right-click a channel → Copy Channel ID, with Developer Mode on) to
  restrict it to e.g. a `#trade-log` channel.
- `sell_keywords` / `add_keywords`: edit these to match the actual wording
  that shows up in your screenshots — the more specific, the more reliable
  the guessing. Growtopia trade-complete screens usually say things like
  "You received" or show a sold confirmation — check a few real screenshots
  and tune these lists.
- `admin_role_names`: roles (besides the original poster) allowed to
  confirm/cancel a pending guess.

## 5. Run it

```bash
python bot.py
```

## How it works

1. Someone posts a screenshot in a watched channel.
2. The bot OCRs it, checks the text against `sell_keywords` /
   `add_keywords`, and guesses an item name + quantity.
3. It replies with an embed showing the guess and reacts with ✅ / ❌.
4. The original poster (or an admin/mod) reacts ✅ to commit the change to
   `inventory.json`, or ❌ to discard it.

## Live inventory channel

Point a channel to show a permanently up-to-date inventory board (one
message the bot edits in place, and pins, every time inventory changes):

```
!setinvchannel #inventory
```

Run it with no channel argument to use whatever channel you type it in.
Requires `Manage Server` permission or one of `admin_role_names`. The
board updates automatically on every confirmed screenshot and every
manual `!additem`/`!removeitem`.

## Manual commands (fallback when OCR gets it wrong)

- `!additem <qty> <item name>` — add directly
- `!removeitem <qty> <item name>` — remove directly
- `!inventory` — show the current inventory (also posts to the live board if set)
- `!setinvchannel [#channel]` — admin-only, set the live inventory board channel

## Going fully automatic (skip the confirm step)

If you decide the guessing is reliable enough for your use case, open
`bot.py` and replace the block that adds reactions and stores the pending
action with a direct call to `inventory.add_item(...)` /
`inventory.remove_item(...)`. Not recommended until you've watched it get
a few dozen real screenshots right first.

## Data

- `inventory.json` — the inventory itself, keyed by server (guild) ID, so
  one bot instance can serve multiple servers without mixing up their data.
- `display_state.json` — which channel/message each guild's live inventory
  board lives in, so the bot can keep editing the same message across
  restarts instead of spamming new ones.
