# Kasa's Inventory Tracker

A free, open-source Discord inventory tracker built for Growtopia-style trading workflows.

The bot can read trade screenshots with OCR, detect items and locks, ask for reaction confirmation, update inventory automatically, maintain trade history, log manual changes, prevent duplicate confirmations, reject impossible trades, undo confirmed trades, and export/import backups.

> **Unofficial community project.** This project is not affiliated with, endorsed by, or sponsored by Ubisoft or Growtopia.

---

## Features

- OCR trade detection from screenshots
- ✅ Confirm / ❌ cancel workflow before inventory changes
- Standard two-sided trade support
- Sell-only trade support
- Item inventory tracking
- Separate WL / DL / BGL currency tracking
- Automatic currency conversion
- Permanent live inventory display
- Inventory search
- Trade-history logging
- Audit logging for manual changes
- Duplicate-trade protection
- Invalid-trade protection
- Undo for confirmed trades
- JSON export/import backups
- Case-insensitive item matching
- Automatic item-name capitalization
- Built-in `!commands` help menu
- Built-in `!restarthelp` instructions

---

# Currency System

The bot supports:

- `WL` = World Lock
- `DL` = Diamond Lock
- `BGL` = Blue Gem Lock

Conversions:

```text
100 WL = 1 DL
100 DL = 1 BGL
1 BGL = 10,000 WL
```

BGL can be greater than 100.

---

# Example Trade Detection

A screenshot containing:

```text
You traded [1 Diamond Lock][20 World Lock] with Player in AUCS and received [1 Armored Riding Troll][2 Battle Boar][4 Goat Leash]
```

is detected as:

```text
REMOVE 1 × DL
REMOVE 20 × WL
ADD 1 × Armored Riding Troll
ADD 2 × Battle Boar
ADD 4 × Goat Leash
```

A sell-only trade such as:

```text
You traded [4 Goat Leash] with Player in AUCS
```

is detected as:

```text
REMOVE 4 × Goat Leash
```

The bot does not change inventory until the trade is confirmed.

---

# Installation

## 1. Requirements

You need:

- Python 3.10 or newer
- Tesseract OCR
- A Discord bot application
- A Discord bot token
- Git, if you want to clone the repository

Python dependencies are listed in:

```text
requirements.txt
```

---

## 2. Download the project

Clone the repository:

```powershell
git clone https://github.com/KasaNyaa/Kasas-Inventory-Tracker.git
cd Kasas-Inventory-Tracker
```

Or download the repository as a ZIP from GitHub and extract it.

---

## 3. Create a virtual environment

### Windows PowerShell

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

After activation, your prompt should begin with:

```text
(venv)
```

### Linux / macOS

```bash
python3 -m venv venv
source venv/bin/activate
```

---

## 4. Install dependencies

With the virtual environment activated:

```powershell
pip install -r requirements.txt
```

---

# Tesseract OCR Setup

The bot uses Tesseract OCR to read trade screenshots.

A common Windows install location is:

```text
C:\Program Files\Tesseract-OCR\tesseract.exe
```

If `ocr_utils.py` contains:

```python
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
```

make sure that path matches your installation.

If you use Linux, macOS, or a different Windows path, update the Tesseract path in `ocr_utils.py`.

---

# Discord Bot Setup

## 1. Create a Discord application

Create an application in the Discord Developer Portal.

Create a bot for the application and copy its token.

Never publish or share your bot token.

---

## 2. Create your `.env` file

Copy:

```text
.env.example
```

and rename the copy to:

```text
.env
```

Inside `.env`, add:

```env
DISCORD_BOT_TOKEN=your_real_discord_bot_token_here
```

The real `.env` file is ignored by Git and should never be uploaded to GitHub.

---

## 3. Enable required intents

The bot uses:

- Guilds
- Reactions
- Message Content

Enable **Message Content Intent** in the Discord Developer Portal if required.

---

## 4. Recommended Discord permissions

The bot should have:

- View Channel
- Send Messages
- Embed Links
- Attach Files
- Add Reactions
- Read Message History
- Manage Messages

`Manage Messages` is used so the bot can clear trade confirmation reactions.

---

# Starting the Bot

Activate the virtual environment:

```powershell
.\venv\Scripts\Activate.ps1
```

Start the bot:

```powershell
python bot.py
```

Keep the PowerShell window open while the bot is running.

To stop the bot:

```text
Ctrl + C
```

You can also run:

```text
!restarthelp
```

inside Discord for restart instructions.

---

# First-Time Discord Setup

After the bot is running, configure the channels you want it to use.

## Inventory channel

Run this in the channel where you want the permanent inventory board:

```text
!setinventorychannel
```

---

## Trade-history channel

Run this in the channel where confirmed OCR trades should be logged:

```text
!sethistorychannel
```

---

## Audit-log channel

Run this in the channel where manual inventory changes should be logged:

```text
!setauditchannel
```

---

# Commands

You can always run:

```text
!commands
```

to see the built-in command list inside Discord.

---

## Inventory Commands

### `!inventory`

Shows the current inventory.

```text
!inventory
```

---

### `!search`

Opens the inventory search interface.

```text
!search
```

Use the Search button and enter part of an item name.

---

### `!export`

Exports the current inventory and currency as a JSON backup.

```text
!export
```

Keep the generated JSON file somewhere safe.

---

### `!import`

Restores inventory from an exported JSON backup.

Attach the `.json` backup file to your Discord message and send:

```text
!import
```

The import is recorded in the audit log.

---

### `!resetinventory`

Removes all items and currency.

```text
!resetinventory
```

The bot asks for confirmation:

```text
✅ Confirm
❌ Cancel
```

Confirmed resets are recorded in the audit log.

---

# Item Commands

Item names are matched case-insensitively.

All of these refer to the same item:

```text
Goat Leash
Goat leash
goat leash
GOAT LEASH
```

Item names are normalized so every word starts with a capital letter.

---

### `!additem <quantity> <item>`

Adds items.

Example:

```text
!additem 5 Goat Leash
```

---

### `!removeitem <quantity> <item>`

Removes items.

Example:

```text
!removeitem 2 Goat Leash
```

---

### `!setitem <quantity> <item>`

Sets an item's exact quantity.

Example:

```text
!setitem 10 Goat Leash
```

This sets the item to exactly `10`.

---

# Currency Commands

### `!addcurrency <quantity> <WL/DL/BGL>`

Adds currency.

Example:

```text
!addcurrency 50 WL
```

---

### `!removecurrency <quantity> <WL/DL/BGL>`

Removes currency.

Example:

```text
!removecurrency 2 DL
```

The bot checks total currency value before removing anything.

---

### `!setcurrency <quantity> <WL/DL/BGL>`

Sets the full currency balance using the chosen denomination.

Example:

```text
!setcurrency 250 WL
```

Result:

```text
0 BGL, 2 DL, 50 WL
```

Another example:

```text
!setcurrency 5 BGL
```

---

# Trade Commands

## `!undo`

Reverses the most recent active confirmed trade.

```text
!undo
```

Undo activity is recorded in the audit log.

---

# Help Commands

## `!commands`

Shows the command list and descriptions.

```text
!commands
```

---

## `!restarthelp`

Shows instructions for starting the bot again after a computer restart.

```text
!restarthelp
```

---

# Automatic OCR Trade Workflow

The normal workflow is:

1. Upload a supported Growtopia trade screenshot.
2. The bot runs OCR.
3. The trade parser detects item/currency changes.
4. The bot posts a trade-detected message.
5. Review the detected changes carefully.
6. Press ✅ to confirm or ❌ to cancel.
7. On confirmation:
   - inventory is updated
   - the permanent inventory message is refreshed
   - trade history is saved
   - the history channel receives the confirmed trade

Always verify the OCR result before pressing ✅.

---

# Supported Trade Formats

## Standard trade

```text
You traded [23 Diamond Lock] with Player in AUCS and received [1 Pharaoh Mask][3 Mini-Mod]
```

Detected as:

```text
REMOVE 23 × DL
ADD 1 × Pharaoh Mask
ADD 3 × Mini-Mod
```

---

## Multiple currencies and items

```text
You traded [1 Diamond Lock][20 World Lock] with Player in AUCS and received [1 Armored Riding Troll][2 Battle Boar][4 Goat Leash]
```

---

## Sell-only trade

```text
You traded [4 Goat Leash] with Player in AUCS
```

Detected as:

```text
REMOVE 4 × Goat Leash
```

The parser also tolerates some common OCR problems such as:

- line breaks inside item names
- underscores replacing spaces
- curly quotes
- extra punctuation
- punctuation around `with`
- punctuation around `and received`

---

# Duplicate Trade Protection

Confirmed trades store an OCR fingerprint.

If the same trade is confirmed again, the bot rejects it:

```text
⚠️ Duplicate Trade

This trade has already been confirmed before.
No inventory changes were made.
```

Inventory is not changed a second time.

---

# Invalid Trade Protection

Before applying a trade, the bot checks whether enough items/currency exist.

Example:

Current inventory:

```text
Goat Leash: 2
```

Detected trade:

```text
REMOVE 4 × Goat Leash
```

The bot rejects the trade instead of silently reducing the item to zero.

Currency removals are also validated using total WL value.

---

# Permanent Inventory Display

The configured inventory channel contains one permanent message.

Example:

```text
📦 Inventory

Armored Riding Troll: 1
Battle Boar: 2
Goat Leash: 4

💰 CURRENCY

BGL: 1
DL: 25
WL: 50

Updates automatically
```

The bot edits this message whenever inventory changes.

---

# Trade History

Confirmed OCR trades can be posted to a dedicated trade-history channel.

Set it with:

```text
!sethistorychannel
```

Trade history includes:

- items removed
- items added
- currency removed
- currency added
- the user who confirmed the trade

Cancelled trades are not logged.

---

# Audit Log

The audit log records manual/admin changes.

Set it with:

```text
!setauditchannel
```

Currently audited actions include:

```text
!additem
!removeitem
!setitem
!addcurrency
!removecurrency
!setcurrency
!resetinventory
!import
!undo
```

Audit entries can include:

- command used
- user who made the change
- before/after item quantities
- before/after currency
- imported backup information
- reset details

OCR-confirmed trades are kept in trade history instead.

---

# Backup and Restore

## Create a backup

```text
!export
```

The bot sends a JSON file containing:

- items
- currency

## Restore a backup

Attach that JSON file and run:

```text
!import
```

The current inventory is replaced with the backup contents.

---

# Runtime Files

The bot stores local runtime data in JSON files such as:

```text
inventory.json
display_state.json
trade_history.json
```

These files are excluded from GitHub by `.gitignore`.

Backup files such as:

```text
inventory_backup_123456789.json
```

are also ignored.

---

# Project Structure

Typical public project structure:

```text
Kasas-Inventory-Tracker/
├── .env.example
├── .gitignore
├── LICENSE
├── README.md
├── bot.py
├── display.py
├── history.py
├── inventory.py
├── ocr_utils.py
├── parser.py
└── requirements.txt
```

Private/runtime files such as `.env`, `inventory.json`, and `trade_history.json` should not be committed.

---

# Hosting

The bot currently works as a self-hosted Python application.

You can run it:

- on your own PC
- on a VPS
- on a cloud hosting provider

If you host it online, make sure the JSON runtime files are stored on persistent storage.

For larger deployments, moving storage to a database is recommended.

---

# Security

Never publish:

```text
.env
Discord bot tokens
inventory.json
display_state.json
trade_history.json
private inventory backups
```

Before pushing changes, check:

```powershell
git status
```

Make sure private files are not listed under files to be committed.

If a Discord bot token is accidentally exposed, reset it immediately.

---

# Updating the GitHub Repository

After making changes locally:

```powershell
git status
git add .
git commit -m "Describe your changes"
git push
```

Example:

```powershell
git add .
git commit -m "Improve OCR parser"
git push
```

---

# License

This project is released under the **MIT License**.

See:

```text
LICENSE
```

The MIT License allows people to use, modify, distribute, and build on the project as long as the license notice remains included.

---

# Contributing

Contributions are welcome.

Useful contribution areas include:

- OCR improvements
- additional Growtopia trade formats
- parser reliability
- database support
- cloud hosting support
- automated tests
- Linux/macOS improvements
- error handling
- UI improvements

---

# Disclaimer

OCR is not perfect.

Always review detected trade information before pressing ✅.

The maintainers are not responsible for inventory changes caused by incorrectly confirmed OCR results, configuration errors, or modified versions of the software.

Growtopia and related trademarks belong to their respective owners.

This project is an independent community-made tool.
