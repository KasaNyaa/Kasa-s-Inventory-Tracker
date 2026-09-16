import json
import os
import tempfile

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

import display
import history
import inventory
import ocr_utils
import parser

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

with open(os.path.join(os.path.dirname(__file__), "config.json"), "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

CONFIRM_EMOJI = CONFIG["confirm_emoji"]
CANCEL_EMOJI = CONFIG["cancel_emoji"]
LISTEN_CHANNELS = set(CONFIG.get("listen_channel_ids") or [])
ADMIN_ROLE_NAMES = set(CONFIG.get("admin_role_names") or [])
SELL_KEYWORDS = CONFIG["sell_keywords"]
ADD_KEYWORDS = CONFIG["add_keywords"]

intents = discord.Intents.default()

intents.message_content = True
intents.guilds = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)

# message_id -> pending action awaiting reaction confirmation
pending_actions: dict[int, dict] = {}


def is_authorized(member: discord.Member, original_author_id: int) -> bool:
    if member.id == original_author_id:
        return True
    return any(role.name in ADMIN_ROLE_NAMES for role in getattr(member, "roles", []))


def build_embed(action: str, item: str | None, qty: int, status: str = "pending") -> discord.Embed:
    color = {
        "pending": discord.Color.gold(),
        "confirmed": discord.Color.green(),
        "cancelled": discord.Color.red(),
    }[status]

    if item is None:
        title = "Couldn't read an item from that screenshot"
        desc = "React or reply manually with `!additem` / `!removeitem` instead."
    else:
        verb = {"add": "Add to", "sell": "Remove from", "unknown": "Unclear — guessed add to"}[action]
        title = f"{verb} inventory?"
        desc = f"**{item}** x{qty}"

    embed = discord.Embed(title=title, description=desc, color=color)
    if status == "pending" and item is not None:
        embed.set_footer(text=f"React {CONFIRM_EMOJI} to confirm or {CANCEL_EMOJI} to cancel")
    elif status == "confirmed":
        embed.set_footer(text="Inventory updated.")
    elif status == "cancelled":
        embed.set_footer(text="Cancelled — no changes made.")
    return embed


def build_inventory_embed(inv: dict, currency: dict) -> discord.Embed:
    if not inv:
        item_desc = "*Empty*"
    else:
        item_desc = "\n".join(
            f"**{name}**: {qty}"
            for name, qty in sorted(inv.items())
        )

    bgl = currency.get("BGL", 0)
    dl = currency.get("DL", 0)
    wl = currency.get("WL", 0)

    currency_desc = (
        f"**BGL**: {bgl}\n"
        f"**DL**: {dl}\n"
        f"**WL**: {wl}"
    )

    embed = discord.Embed(
        title="📦 Inventory",
        color=discord.Color.blue()
    )

    embed.description = item_desc

    embed.add_field(
        name="💰 CURRENCY",
        value=currency_desc,
        inline=False
    )

    embed.set_footer(text="Updates automatically")

    return embed


async def refresh_inventory_display(guild: discord.Guild) -> None:
    """Update the single permanent inventory message."""

    channel_id = display.get_channel_id(guild.id)

    if not channel_id:
        return

    channel = bot.get_channel(channel_id)

    if channel is None:
        channel = await bot.fetch_channel(channel_id)

    inv = inventory.get_inventory(guild.id)
    currency = inventory.get_currency(guild.id)

    embed = build_inventory_embed(inv, currency)

    # First try the message ID saved in display_state.json
    message_id = display.get_message_id(guild.id)

    if message_id:
        try:
            message = await channel.fetch_message(message_id)
            await message.edit(embed=embed)
            return
        except (discord.NotFound, discord.Forbidden):
            pass

    # If the saved message ID is missing/invalid,
    # look through the channel for the bot's existing inventory message.
    try:
        async for message in channel.history(limit=100):
            if message.author.id != bot.user.id:
                continue

            if message.embeds:
                if message.embeds[0].title == "📦 Inventory":
                    await message.edit(embed=embed)

                    # Remember this message for future updates
                    display.set_message_id(guild.id, message.id)
                    return

    except discord.Forbidden:
        return

    # No existing inventory message was found.
    # Create ONE permanent inventory message.
    message = await channel.send(embed=embed)

    try:
        await message.pin()
    except discord.Forbidden:
        pass

    display.set_message_id(guild.id, message.id)

async def post_trade_history(
    guild: discord.Guild,
    author_id: int,
    changes: list
) -> None:

    channel_id = display.get_history_channel_id(guild.id)

    if not channel_id:
        return

    channel = bot.get_channel(channel_id)

    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except (discord.NotFound, discord.Forbidden):
            return

    lines = []

    for change in changes:

        if change["action"] == "sell":
            lines.append(
                f"🔴 Removed **{change['qty']} × {change['item']}**"
            )
        else:
            lines.append(
                f"🟢 Added **{change['qty']} × {change['item']}**"
            )

    embed = discord.Embed(
        title="📜 Confirmed Trade",
        description="\n".join(lines),
        color=discord.Color.green()
    )

    embed.add_field(
        name="Confirmed by",
        value=f"<@{author_id}>",
        inline=False
    )

    embed.set_footer(
        text="Trade History"
    )

    await channel.send(embed=embed)

async def post_audit_log(
    guild: discord.Guild,
    user_id: int,
    action: str,
    details: str
) -> None:

    channel_id = display.get_audit_channel_id(guild.id)

    if not channel_id:
        return

    channel = bot.get_channel(channel_id)

    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except (discord.NotFound, discord.Forbidden):
            return

    embed = discord.Embed(
        title="📝 Inventory Audit",
        description=details,
        color=discord.Color.orange()
    )

    embed.add_field(
        name="Action",
        value=action,
        inline=False
    )

    embed.add_field(
        name="Changed by",
        value=f"<@{user_id}>",
        inline=False
    )

    embed.set_footer(
        text="Inventory Audit Log"
    )

    await channel.send(embed=embed)

def is_admin(member: discord.Member) -> bool:
    if member.guild_permissions.manage_guild:
        return True
    return any(role.name in ADMIN_ROLE_NAMES for role in member.roles)


@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user} (id: {bot.user.id})")


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    await bot.process_commands(message)

    if not message.attachments:
        return
    if LISTEN_CHANNELS and message.channel.id not in LISTEN_CHANNELS:
        return

    image_attachments = [
        a for a in message.attachments
        if a.content_type and a.content_type.startswith("image/")
    ]
    if not image_attachments:
        return

    for attachment in image_attachments:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            await attachment.save(tmp.name)
            tmp_path = tmp.name

        try:
            text = ocr_utils.image_to_text(tmp_path)
            print("OCR TEXT:", repr(text))
        finally:
            os.unlink(tmp_path)

        changes = parser.extract_trade_items(text)

        if not changes:
            return

        lines = []

        for change in changes:
            if change["action"] == "sell":
                lines.append(
                    f"REMOVE {change['qty']} x {change['item']}"
                )
            else:
                lines.append(
                    f"ADD {change['qty']} x {change['item']}"
                )

        embed = discord.Embed(
            title="Trade detected",
            description="\n".join(lines),
            color=discord.Color.blue()
        )

        reply = await message.reply(
            embed=embed,
            mention_author=False
        )

        await reply.add_reaction(CONFIRM_EMOJI)
        await reply.add_reaction(CANCEL_EMOJI)
        pending_actions[reply.id] = {
            "guild_id": message.guild.id,
            "changes": changes,
            "author_id": message.author.id,
            "fingerprint": text.strip()
        }


@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):

    if payload.user_id == bot.user.id:
        return

    pending = pending_actions.get(payload.message_id)

    if not pending:
        return

    guild = bot.get_guild(payload.guild_id)

    if guild is None:
        return

    member = guild.get_member(payload.user_id)

    if member is None:
        try:
            member = await guild.fetch_member(payload.user_id)
        except discord.NotFound:
            print("REACTION TEST: member could not be found")
            return

    print("REACTION TEST: member =", member)

    authorized = is_authorized(member, pending["author_id"])

    print("REACTION TEST: authorized =", authorized)

    if not authorized:
        return

    channel = bot.get_channel(payload.channel_id)

    if channel is None:
        return

    msg = await channel.fetch_message(payload.message_id)

    emoji = str(payload.emoji)

    print("REACTION RECEIVED:", emoji)

    # =========================
    # CONFIRM
    # =========================

    if emoji == CONFIRM_EMOJI:

        # -------------------------
        # RESET INVENTORY
        # -------------------------

        if pending.get("type") == "reset_inventory":

            # Save what existed before the reset
            old_items = inventory.get_inventory(
                pending["guild_id"]
            )

            old_currency = inventory.get_currency(
                pending["guild_id"]
            )

            old_bgl = old_currency.get("BGL", 0)
            old_dl = old_currency.get("DL", 0)
            old_wl = old_currency.get("WL", 0)

            # Reset everything
            inventory.reset_inventory(
                pending["guild_id"]
            )

            embed = discord.Embed(
                title="🗑️ Inventory Reset",
                description="The entire inventory has been reset.",
                color=discord.Color.red()
            )

            await msg.edit(embed=embed)
            await msg.clear_reactions()

            pending_actions.pop(
                payload.message_id,
                None
            )

            await refresh_inventory_display(guild)

            # Build a summary of what was deleted
            if old_items:
                item_summary = "\n".join(
                    f"• {name}: {qty}"
                    for name, qty in old_items.items()
                )
            else:
                item_summary = "*No items*"

            await post_audit_log(
                guild,
                payload.user_id,
                "!resetinventory",
                f"**Entire inventory reset**\n\n"
                f"Items removed:\n{item_summary}\n\n"
                f"Currency removed: "
                f"**{old_bgl} BGL, {old_dl} DL, {old_wl} WL**"
            )

        # -------------------------
        # NORMAL TRADE
        # -------------------------

        else:
            fingerprint = pending.get("fingerprint")

            if history.is_duplicate_trade(
                pending["guild_id"],
                fingerprint
            ):
                duplicate_embed = discord.Embed(
                    title="⚠️ Duplicate Trade",
                    description=(
                        "This trade has already been confirmed before.\n"
                        "No inventory changes were made."
                    ),
                    color=discord.Color.orange()
                )

                await msg.edit(embed=duplicate_embed)
                await msg.clear_reactions()

                pending_actions.pop(
                    payload.message_id,
                    None
                )

                return
                            # Validate the trade before changing inventory
            validation_errors = []

            current_items = inventory.get_inventory(
                pending["guild_id"]
            )

            total_wls = inventory.get_total_wls(
                pending["guild_id"]
            )

            currency_values = {
                "WL": 1,
                "DL": 100,
                "BGL": 10000
            }

            required_currency_wls = 0

            for change in pending["changes"]:

                if change["action"] != "sell":
                    continue

                if change.get("currency", False):
                    required_currency_wls += (
                        change["qty"]
                        * currency_values[change["item"]]
                    )
                else:
                    current_qty = current_items.get(
                        change["item"],
                        0
                    )

                    if current_qty < change["qty"]:
                        validation_errors.append(
                            f"Not enough **{change['item']}** "
                            f"(have {current_qty}, need {change['qty']})"
                        )

            if required_currency_wls > total_wls:
                validation_errors.append(
                    "Not enough currency "
                    f"(have {total_wls} WL value, "
                    f"need {required_currency_wls} WL value)"
                )

            if validation_errors:
                invalid_embed = discord.Embed(
                    title="❌ Trade Cannot Be Confirmed",
                    description="\n".join(validation_errors),
                    color=discord.Color.red()
                )

                await msg.edit(embed=invalid_embed)
                await msg.clear_reactions()

                pending_actions.pop(
                    payload.message_id,
                    None
                )

                return

            result_lines = []

            for change in pending["changes"]:

                # CURRENCY
                if change.get("currency", False):

                    if change["action"] == "sell":

                        new_qty = inventory.remove_currency(
                            pending["guild_id"],
                            change["item"],
                            change["qty"]
                        )

                        result_lines.append(
                            f"Removed **{change['item']}** "
                            f"x{change['qty']} -> {new_qty}"
                        )

                    else:

                        new_qty = inventory.add_currency(
                            pending["guild_id"],
                            change["item"],
                            change["qty"]
                        )

                        result_lines.append(
                            f"Added **{change['item']}** "
                            f"x{change['qty']} -> {new_qty}"
                        )

                # NORMAL ITEMS
                else:

                    if change["action"] == "sell":

                        new_qty = inventory.remove_item(
                            pending["guild_id"],
                            change["item"],
                            change["qty"]
                        )

                        result_lines.append(
                            f"Removed **{change['item']}** "
                            f"x{change['qty']} -> {new_qty}"
                        )

                    else:

                        new_qty = inventory.add_item(
                            pending["guild_id"],
                            change["item"],
                            change["qty"]
                        )

                        result_lines.append(
                            f"Added **{change['item']}** "
                            f"x{change['qty']} -> {new_qty}"
                        )

            embed = discord.Embed(
                title="Trade confirmed",
                description="\n".join(result_lines),
                color=discord.Color.green()
            )

            await msg.edit(embed=embed)
            await msg.clear_reactions()

            await refresh_inventory_display(guild)



            history.add_trade(
                pending["guild_id"],
                payload.user_id,
                pending["changes"],
                fingerprint
            )

            await post_trade_history(
                guild,
                payload.user_id,
                pending["changes"]
            )

            pending_actions.pop(
                payload.message_id,
                None
            )

    # =========================
    # CANCEL
    # =========================

    elif emoji == CANCEL_EMOJI:

        if pending.get("type") == "reset_inventory":

            embed = discord.Embed(
                title="Reset cancelled",
                description="No inventory changes were made.",
                color=discord.Color.green()
            )

        else:

            embed = discord.Embed(
                title="Trade cancelled",
                description="No inventory changes were made.",
                color=discord.Color.red()
            )

        await msg.edit(embed=embed)
        await msg.clear_reactions()

        pending_actions.pop(
            payload.message_id,
            None
        )

@bot.command(name="additem")
async def additem_cmd(ctx: commands.Context, qty: int, *, item: str):

    old_inventory = inventory.get_inventory(ctx.guild.id)
    old_qty = old_inventory.get(item, 0)

    new_qty = inventory.add_item(
        ctx.guild.id,
        item,
        qty
    )

    await ctx.reply(
        f"Added **{item}** x{qty}. New total: {new_qty}"
    )

    await refresh_inventory_display(ctx.guild)

    await post_audit_log(
        ctx.guild,
        ctx.author.id,
        "!additem",
        f"**{item}**: {old_qty} → {new_qty}\n"
        f"Added: **{qty}**"
    )

@bot.command(name="addcurrency")
async def addcurrency_cmd(ctx: commands.Context, qty: int, currency: str):

    currency = currency.upper()

    if currency not in ("WL", "DL", "BGL"):
        await ctx.reply("Currency must be WL, DL, or BGL.")
        return

    old_currency = inventory.get_currency(ctx.guild.id)
    old_bgl = old_currency.get("BGL", 0)
    old_dl = old_currency.get("DL", 0)
    old_wl = old_currency.get("WL", 0)

    inventory.add_currency(
        ctx.guild.id,
        currency,
        qty
    )

    new_currency = inventory.get_currency(ctx.guild.id)
    new_bgl = new_currency.get("BGL", 0)
    new_dl = new_currency.get("DL", 0)
    new_wl = new_currency.get("WL", 0)

    await ctx.reply(
        f"Added **{currency}** x{qty}."
    )

    await refresh_inventory_display(ctx.guild)

    await post_audit_log(
        ctx.guild,
        ctx.author.id,
        "!addcurrency",
        f"Added: **{qty} {currency}**\n\n"
        f"Before: **{old_bgl} BGL, {old_dl} DL, {old_wl} WL**\n"
        f"After: **{new_bgl} BGL, {new_dl} DL, {new_wl} WL**"
    )

@bot.command(name="setcurrency")
async def setcurrency_cmd(ctx: commands.Context, qty: int, currency: str):

    currency = currency.upper()

    if currency not in ("WL", "DL", "BGL"):
        await ctx.reply("Currency must be WL, DL, or BGL.")
        return

    if qty < 0:
        await ctx.reply("Currency quantity cannot be negative.")
        return

    # Save the old balance for the audit log
    old_currency = inventory.get_currency(ctx.guild.id)
    old_bgl = old_currency.get("BGL", 0)
    old_dl = old_currency.get("DL", 0)
    old_wl = old_currency.get("WL", 0)

    inventory.set_currency(
        ctx.guild.id,
        currency,
        qty
    )

    # Get the new balance after conversion
    currency_state = inventory.get_currency(ctx.guild.id)

    bgl = currency_state.get("BGL", 0)
    dl = currency_state.get("DL", 0)
    wl = currency_state.get("WL", 0)

    await ctx.reply(
        f"Set currency to **{qty} {currency}**.\n"
        f"Result: **{bgl} BGL, {dl} DL, {wl} WL**"
    )

    await refresh_inventory_display(ctx.guild)

    await post_audit_log(
        ctx.guild,
        ctx.author.id,
        "!setcurrency",
        f"Set currency to: **{qty} {currency}**\n\n"
        f"Before: **{old_bgl} BGL, {old_dl} DL, {old_wl} WL**\n"
        f"After: **{bgl} BGL, {dl} DL, {wl} WL**"
    )

class SearchModal(discord.ui.Modal, title="Search Inventory"):

    search = discord.ui.TextInput(
        label="Search for an item",
        placeholder="Type an item name...",
        required=True,
        max_length=100
    )

    async def on_submit(self, interaction: discord.Interaction):

        query = self.search.value.strip()

        inv = inventory.get_inventory(interaction.guild.id)

        matches = []

        for item_name, qty in inv.items():

            if query.lower() in item_name.lower():

                matches.append(
                    f"**{item_name}**: {qty}"
                )

        if not matches:

            await interaction.response.send_message(
                f"❌ No items found for **{query}**.",
                ephemeral=True
            )

            return

        embed = discord.Embed(
            title=f"🔎 Search: {query}",
            description="\n".join(matches),
            color=discord.Color.blue()
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )


class SearchView(discord.ui.View):

    def __init__(self):

        super().__init__(timeout=None)

    @discord.ui.button(
        label="Search",
        emoji="🔎",
        style=discord.ButtonStyle.primary
    )
    async def search_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.send_modal(
            SearchModal()
        )


@bot.command(name="search")
async def search_cmd(ctx: commands.Context):

    embed = discord.Embed(
        title="🔎 Search Inventory",
        description="Click the **Search** button below to search the inventory.",
        color=discord.Color.blue()
    )

    await ctx.reply(
        embed=embed,
        view=SearchView()
    )

@bot.command(name="removecurrency")
async def removecurrency_cmd(
    ctx: commands.Context,
    qty: int,
    currency: str
):

    currency = currency.upper()

    if currency not in ("WL", "DL", "BGL"):
        await ctx.reply("Currency must be WL, DL, or BGL.")
        return

    # Check total currency before removing anything
    total_wls = inventory.get_total_wls(ctx.guild.id)

    values = {
        "WL": 1,
        "DL": 100,
        "BGL": 10000
    }

    requested_wls = qty * values[currency]

    if requested_wls > total_wls:
        available = total_wls // values[currency]

        await ctx.reply(
            f"❌ Not enough currency.\n"
            f"You have **{available} {currency}** available, "
            f"but tried to remove **{qty} {currency}**."
        )
        return

    # Save balance before the change for the audit log
    old_currency = inventory.get_currency(ctx.guild.id)
    old_bgl = old_currency.get("BGL", 0)
    old_dl = old_currency.get("DL", 0)
    old_wl = old_currency.get("WL", 0)

    inventory.remove_currency(
        ctx.guild.id,
        currency,
        qty
    )

    # Get the complete balance after conversion/removal
    new_currency = inventory.get_currency(ctx.guild.id)
    new_bgl = new_currency.get("BGL", 0)
    new_dl = new_currency.get("DL", 0)
    new_wl = new_currency.get("WL", 0)

    await ctx.reply(
        f"Removed **{currency}** x{qty}.\n"
        f"Balance: **{new_bgl} BGL, {new_dl} DL, {new_wl} WL**"
    )

    await refresh_inventory_display(ctx.guild)

    await post_audit_log(
        ctx.guild,
        ctx.author.id,
        "!removecurrency",
        f"Removed: **{qty} {currency}**\n\n"
        f"Before: **{old_bgl} BGL, {old_dl} DL, {old_wl} WL**\n"
        f"After: **{new_bgl} BGL, {new_dl} DL, {new_wl} WL**"
    )

@bot.command(name="export")
async def export_cmd(ctx: commands.Context):

    guild_id = ctx.guild.id

    inv = inventory.get_inventory(guild_id)
    currency = inventory.get_currency(guild_id)

    backup = {
        "items": inv,
        "currency": currency
    }

    filename = f"inventory_backup_{guild_id}.json"

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(
            backup,
            f,
            indent=2,
            ensure_ascii=False
        )

    await ctx.reply(
        "📦 Inventory backup created.",
        file=discord.File(filename)
    )

@bot.command(name="import")
async def import_cmd(ctx: commands.Context):

    if not ctx.message.attachments:
        await ctx.reply(
            "❌ Please attach an inventory backup JSON file."
        )
        return

    attachment = ctx.message.attachments[0]

    if not attachment.filename.lower().endswith(".json"):
        await ctx.reply(
            "❌ The backup file must be a `.json` file."
        )
        return

    try:
        data = await attachment.read()
        backup = json.loads(data.decode("utf-8"))

        items = backup.get("items", {})
        currency = backup.get("currency", {})

        if not isinstance(items, dict):
            raise ValueError("Invalid items data.")

        if not isinstance(currency, dict):
            raise ValueError("Invalid currency data.")

        guild_id = ctx.guild.id

        # Save old inventory for the audit log
        old_items = inventory.get_inventory(guild_id)
        old_currency = inventory.get_currency(guild_id)

        old_bgl = old_currency.get("BGL", 0)
        old_dl = old_currency.get("DL", 0)
        old_wl = old_currency.get("WL", 0)

        # Clear the current inventory
        inventory.reset_inventory(guild_id)

        # Restore normal items
        for item_name, qty in items.items():
            inventory.set_item(
                guild_id,
                item_name,
                int(qty)
            )

        # Restore currency correctly.
        # add_currency is used because set_currency would erase
        # the other denominations on every loop.
        for currency_name, qty in currency.items():

            currency_name = currency_name.upper()

            if currency_name not in ("WL", "DL", "BGL"):
                raise ValueError("Invalid currency name.")

            qty = int(qty)

            if qty < 0:
                raise ValueError("Invalid currency quantity.")

            inventory.add_currency(
                guild_id,
                currency_name,
                qty
            )

        # Get the final restored state
        new_items = inventory.get_inventory(guild_id)
        new_currency = inventory.get_currency(guild_id)

        new_bgl = new_currency.get("BGL", 0)
        new_dl = new_currency.get("DL", 0)
        new_wl = new_currency.get("WL", 0)

        await ctx.reply(
            "✅ Inventory imported successfully."
        )

        await refresh_inventory_display(ctx.guild)

        if old_items:
            old_item_summary = "\n".join(
                f"• {name}: {qty}"
                for name, qty in old_items.items()
            )
        else:
            old_item_summary = "*No items*"

        if new_items:
            new_item_summary = "\n".join(
                f"• {name}: {qty}"
                for name, qty in new_items.items()
            )
        else:
            new_item_summary = "*No items*"

        await post_audit_log(
            ctx.guild,
            ctx.author.id,
            "!import",
            f"Imported backup: **{attachment.filename}**\n\n"
            f"**Items before:**\n"
            f"{old_item_summary}\n\n"
            f"**Items after:**\n"
            f"{new_item_summary}\n\n"
            f"**Currency before:** "
            f"{old_bgl} BGL, {old_dl} DL, {old_wl} WL\n"
            f"**Currency after:** "
            f"{new_bgl} BGL, {new_dl} DL, {new_wl} WL"
        )

    except Exception:
        await ctx.reply(
            "❌ Could not import that backup file."
        )

@bot.command(name="removeitem")
async def removeitem_cmd(ctx: commands.Context, qty: int, *, item: str):

    key = inventory.find_item_key(ctx.guild.id, item) or item

    old_inventory = inventory.get_inventory(ctx.guild.id)
    old_qty = old_inventory.get(key, 0)

    new_qty = inventory.remove_item(
        ctx.guild.id,
        key,
        qty
    )

    await ctx.reply(
        f"Removed **{key}** x{qty}. New total: {new_qty}"
    )

    await refresh_inventory_display(ctx.guild)

    await post_audit_log(
        ctx.guild,
        ctx.author.id,
        "!removeitem",
        f"**{key}**: {old_qty} → {new_qty}\n"
        f"Removed: **{qty}**"
    )

@bot.command(name="setitem")
async def setitem_cmd(ctx: commands.Context, qty: int, *, item: str):

    key = inventory.find_item_key(ctx.guild.id, item) or item

    old_inventory = inventory.get_inventory(ctx.guild.id)
    old_qty = old_inventory.get(key, 0)

    new_qty = inventory.set_item(
        ctx.guild.id,
        key,
        qty
    )

    await ctx.reply(
        f"Set **{key}** to x{new_qty}."
    )

    await refresh_inventory_display(ctx.guild)

    await post_audit_log(
        ctx.guild,
        ctx.author.id,
        "!setitem",
        f"**{key}**: {old_qty} → {new_qty}\n"
        f"Set quantity to: **{new_qty}**"
    )

@bot.command(name="resetinventory")
async def resetinventory_cmd(ctx: commands.Context):

    if not is_authorized(ctx.author, ctx.author.id):
        await ctx.reply("You are not authorized to reset the inventory.")
        return

    embed = discord.Embed(
        title="⚠️ Reset Inventory?",
        description=(
            "This will permanently remove **ALL items and currency** "
            "from the inventory.\n\n"
            "React with ✅ to confirm or ❌ to cancel."
        ),
        color=discord.Color.red()
    )

    message = await ctx.reply(embed=embed)

    await message.add_reaction(CONFIRM_EMOJI)
    await message.add_reaction(CANCEL_EMOJI)

    pending_actions[message.id] = {
        "type": "reset_inventory",
        "guild_id": ctx.guild.id,
        "author_id": ctx.author.id,
    }

@bot.command(name="inventory")
async def inventory_cmd(ctx: commands.Context):
    inv = inventory.get_inventory(ctx.guild.id)
    currency = inventory.get_currency(ctx.guild.id)

    embed = build_inventory_embed(inv, currency)

    await ctx.reply(embed=embed)


@bot.command(name="setinventorychannel")
async def setinventorychannel_cmd(
    ctx: commands.Context,
    channel: discord.TextChannel = None
):

    """Admins only: set the channel that holds the live inventory board."""

    if not is_admin(ctx.author):

        await ctx.reply(
            "You need `Manage Server` or an admin role to do that."
        )

        return

    target = channel or ctx.channel

    display.set_channel_id(
        ctx.guild.id,
        target.id
    )

    await ctx.reply(
        f"Inventory board will now be kept up to date in {target.mention}."
    )

    await refresh_inventory_display(
        ctx.guild
    )

@bot.command(name="sethistorychannel")
async def sethistorychannel_cmd(
    ctx: commands.Context,
    channel: discord.TextChannel = None
):

    """Admins only: set the channel that holds trade history."""

    if not is_admin(ctx.author):

        await ctx.reply(
            "You need `Manage Server` or an admin role to do that."
        )

        return

    target = channel or ctx.channel

    display.set_history_channel_id(
        ctx.guild.id,
        target.id
    )

    await ctx.reply(
        f"Trade history will now be posted in {target.mention}."
    )

@bot.command(name="setauditchannel")
async def setauditchannel_cmd(
    ctx: commands.Context,
    channel: discord.TextChannel = None
):

    """Admins only: set the channel that holds the audit log."""

    if not is_admin(ctx.author):

        await ctx.reply(
            "You need `Manage Server` or an admin role to do that."
        )

        return

    target = channel or ctx.channel

    display.set_audit_channel_id(
        ctx.guild.id,
        target.id
    )

    await ctx.reply(
        f"Audit log will now be posted in {target.mention}."
    )

@bot.command(name="undo")
async def undo_cmd(ctx: commands.Context):

    if not is_authorized(ctx.author, ctx.author.id):
        await ctx.reply(
            "You are not authorized to undo trades."
        )
        return

    trade = history.get_last_active_trade(ctx.guild.id)

    if trade is None:
        await ctx.reply(
            "❌ There are no confirmed trades to undo."
        )
        return

    changes = trade.get("changes", [])

    if not changes:
        await ctx.reply(
            "❌ That trade has no changes to undo."
        )
        return

    result_lines = []

    for change in reversed(changes):

        item = change["item"]
        qty = change["qty"]
        currency = change.get("currency", False)

        if change["action"] == "sell":

            if currency:
                inventory.add_currency(
                    ctx.guild.id,
                    item,
                    qty
                )
            else:
                inventory.add_item(
                    ctx.guild.id,
                    item,
                    qty
                )

            result_lines.append(
                f"🟢 Restored **{qty} × {item}**"
            )

        else:

            if currency:
                inventory.remove_currency(
                    ctx.guild.id,
                    item,
                    qty
                )
            else:
                inventory.remove_item(
                    ctx.guild.id,
                    item,
                    qty
                )

            result_lines.append(
                f"🔴 Removed **{qty} × {item}**"
            )

    marked = history.mark_trade_undone(
        ctx.guild.id,
        trade["timestamp"]
    )

    if not marked:
        await ctx.reply(
            "❌ That trade was already undone."
        )
        return

    await refresh_inventory_display(ctx.guild)

    embed = discord.Embed(
        title="↩️ Trade Undone",
        description="\n".join(result_lines),
        color=discord.Color.orange()
    )

    await ctx.reply(embed=embed)

    await post_audit_log(
        ctx.guild,
        ctx.author.id,
        "!undo",
        "Reversed the most recent confirmed trade.\n\n"
        + "\n".join(result_lines)
    )

@bot.command(name="commands")
async def commands_cmd(ctx: commands.Context):

    embed = discord.Embed(
        title="📘 Bot Commands",
        description="Available inventory bot commands:",
        color=discord.Color.blue()
    )

    embed.add_field(
        name="📦 Inventory",
        value=(
            "`!inventory` — Show the current inventory.\n"
            "`!search` — Search the inventory.\n"
            "`!export` — Export inventory to a JSON backup.\n"
            "`!import` — Restore inventory from a JSON backup.\n"
            "`!resetinventory` — Remove all items and currency."
        ),
        inline=False
    )

    embed.add_field(
        name="🧰 Items",
        value=(
            "`!additem <qty> <item>` — Add items.\n"
            "`!removeitem <qty> <item>` — Remove items.\n"
            "`!setitem <qty> <item>` — Set an item's exact quantity."
        ),
        inline=False
    )

    embed.add_field(
        name="💰 Currency",
        value=(
            "`!addcurrency <qty> <WL/DL/BGL>` — Add currency.\n"
            "`!removecurrency <qty> <WL/DL/BGL>` — Remove currency.\n"
            "`!setcurrency <qty> <WL/DL/BGL>` — Set the currency balance."
        ),
        inline=False
    )

    embed.add_field(
        name="🔄 Trades",
        value=(
            "`!undo` — Undo the most recent active confirmed trade."
        ),
        inline=False
    )

    embed.add_field(
        name="⚙️ Channel Setup",
        value=(
            "`!setinventorychannel` — Set the permanent inventory channel.\n"
            "`!sethistorychannel` — Set the trade-history channel.\n"
            "`!setauditchannel` — Set the audit-log channel."
        ),
        inline=False
    )

    embed.set_footer(
        text="Inventory Tracker"
    )

    await ctx.reply(embed=embed)

@bot.command(name="restarthelp")
async def restarthelp_cmd(ctx: commands.Context):

    embed = discord.Embed(
        title="🖥️ Restarting the Bot After a PC Restart",
        color=discord.Color.blue()
    )

    embed.description = (
        "Open **PowerShell** and run these commands:\n\n"
        "`cd C:\\Users\\Elmer\\Desktop\\files2`\n\n"
        "`.\\venv\\Scripts\\Activate.ps1`\n\n"
        "`python bot.py`\n\n"
        "When you see the bot log in, keep the PowerShell window open.\n\n"
        "To stop the bot, press `Ctrl + C`."
    )

    await ctx.reply(embed=embed)

if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("Set DISCORD_BOT_TOKEN in a .env file (see .env.example).")

    bot.run(TOKEN)