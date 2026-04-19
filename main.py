import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
import asyncio
import re
import io
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

# ============================================================
#  CONFIG — fill these in or set as environment variables
# ============================================================
TOKEN                = os.getenv("DISCORD_TOKEN", "")
GUILD_ID             = int(os.getenv("GUILD_ID", 0))
TICKET_CATEGORY_ID   = int(os.getenv("TICKET_CATEGORY_ID", 0))
TRANSCRIPT_CHANNEL_ID= int(os.getenv("TRANSCRIPT_CHANNEL_ID", 0))
STAFF_ROLE_IDS       = [int(x) for x in os.getenv("STAFF_ROLE_IDS", "0").split(",") if x.strip()]
ADMIN_ROLE_IDS       = [int(x) for x in os.getenv("ADMIN_ROLE_IDS", "0").split(",") if x.strip()]
AUTO_CLOSE_HOURS     = int(os.getenv("AUTO_CLOSE_HOURS", 24))

VALORA_LOGO    = os.getenv("VALORA_LOGO", "https://i.imgur.com/placeholder.png")  # <-- Replace with your logo URL
VALORA_WEBSITE = "https://valora-store.mysellauth.com/"
VALORA_COLOR   = 0x00BFFF

TICKET_CATEGORIES = {
    "purchase": {"label": "Purchase",              "description": "Request help with a purchase.",         "emoji": "🛒", "color": 0x00BFFF},
    "reseller": {"label": "Apply to be a Reseller","description": "Apply to Valora's Reseller Program.",   "emoji": "💰", "color": 0xFFD700},
    "claim":    {"label": "Claim Role / Key",       "description": "Claim your role or product key.",       "emoji": "🔑", "color": 0x00FF88},
    "hwid":     {"label": "HWID Reset",             "description": "Request a reset for your key.",         "emoji": "🔒", "color": 0xFF6B35},
    "support":  {"label": "Get Support",            "description": "Request support from our staff.",       "emoji": "🎫", "color": 0x9B59B6},
}

TICKETS_FILE = "tickets.json"

# ============================================================
#  TICKET STORAGE
# ============================================================
def load_tickets():
    if os.path.exists(TICKETS_FILE):
        with open(TICKETS_FILE) as f:
            return json.load(f)
    return {}

def save_tickets(data):
    with open(TICKETS_FILE, "w") as f:
        json.dump(data, f, indent=2)

tickets_data = load_tickets()

# ============================================================
#  PERMISSION HELPERS
# ============================================================
def member_is_staff(member: discord.Member) -> bool:
    if member.guild_permissions.administrator:
        return True
    return any(r.id in STAFF_ROLE_IDS + ADMIN_ROLE_IDS for r in member.roles)

def member_is_admin(member: discord.Member) -> bool:
    if member.guild_permissions.administrator:
        return True
    return any(r.id in ADMIN_ROLE_IDS for r in member.roles)

# ============================================================
#  HTML TRANSCRIPT GENERATOR
# ============================================================
def generate_transcript(channel: discord.TextChannel, messages: list, guild: discord.Guild) -> str:
    cat_key = ""
    if channel.topic and " | " in channel.topic:
        parts = channel.topic.split(" | ")
        if len(parts) > 1:
            cat_key = parts[1]
    cat_info = TICKET_CATEGORIES.get(cat_key, {"label": "Support", "emoji": "🎫"})

    messages_html = ""
    prev_author_id = None

    for msg in messages:
        avatar_url = str(msg.author.display_avatar.url) if msg.author.display_avatar else ""
        is_staff_member = any(r.id in STAFF_ROLE_IDS + ADMIN_ROLE_IDS for r in getattr(msg.author, "roles", []))

        if msg.author.id == guild.owner_id:
            role_badge = '<span class="badge owner">Owner</span>'
        elif is_staff_member:
            role_badge = '<span class="badge staff">Staff</span>'
        elif msg.author.bot:
            role_badge = '<span class="badge bot">BOT</span>'
        else:
            role_badge = ""

        attachments_html = ""
        for att in msg.attachments:
            if att.content_type and att.content_type.startswith("image"):
                attachments_html += f'<img src="{att.url}" class="attachment-img" alt="attachment">'
            else:
                attachments_html += f'<a href="{att.url}" class="attachment-file" target="_blank">📎 {att.filename}</a>'

        embeds_html = ""
        for embed in msg.embeds:
            ec = f"#{embed.color.value:06x}" if embed.color else "#00BFFF"
            et = f"<div class='embed-title'>{embed.title}</div>" if embed.title else ""
            ed = f"<div class='embed-desc'>{embed.description}</div>" if embed.description else ""
            embeds_html += f'<div class="embed" style="border-left-color:{ec}">{et}{ed}</div>'

        content = msg.content or ""
        content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', content)
        content = re.sub(r'\*(.+?)\*', r'<em>\1</em>', content)
        content = re.sub(r'`(.+?)`', r'<code>\1</code>', content)
        content = re.sub(r'https?://\S+', lambda m: f'<a href="{m.group()}" target="_blank">{m.group()}</a>', content)

        timestamp = msg.created_at.strftime("%d/%m/%Y %H:%M")
        same = prev_author_id == msg.author.id
        prev_author_id = msg.author.id

        avatar_html = f'<img src="{avatar_url}" class="avatar" alt="av">' if not same else '<div class="avatar-spacer"></div>'
        header_html  = f'<div class="msg-header"><span class="username">{msg.author.display_name}</span>{role_badge}<span class="timestamp">{timestamp}</span></div>' if not same else ""

        messages_html += f'''
        <div class="msg-group{"" if not same else " same-author"}">
            {avatar_html}
            <div class="msg-content">
                {header_html}
                <div class="msg-text">{content}</div>
                {attachments_html}
                {embeds_html}
            </div>
        </div>'''

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Transcript — {channel.name} | Valora Store</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Rajdhani:wght@600;700&display=swap');
:root{{--bg:#0d0f14;--surface:#13161e;--surface2:#1a1e2a;--border:#1e2333;--blue:#00BFFF;--text:#e0e6f0;--muted:#6b7590;--staff:#00e5a0;--owner:#FFD700;--bot:#5865F2}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--text);font-family:'Inter',sans-serif;font-size:14px;line-height:1.6}}
.header{{background:linear-gradient(135deg,#0a0c14,#0d1220,#0a0c14);border-bottom:1px solid var(--border);padding:28px 40px;display:flex;align-items:center;gap:24px;position:sticky;top:0;z-index:100;backdrop-filter:blur(20px)}}
.header-logo{{width:64px;height:64px;border-radius:50%;border:2px solid var(--blue);box-shadow:0 0 20px rgba(0,191,255,.3)}}
.header-info h1{{font-family:'Rajdhani',sans-serif;font-size:26px;font-weight:700;color:var(--blue);letter-spacing:2px;text-shadow:0 0 20px rgba(0,191,255,.4)}}
.header-info p{{color:var(--muted);font-size:13px;margin-top:2px}}
.header-meta{{margin-left:auto;display:flex;flex-direction:column;align-items:flex-end;gap:4px;font-size:12px;color:var(--muted)}}
.header-meta strong{{color:var(--text)}}
.stats-bar{{background:var(--surface);border-bottom:1px solid var(--border);padding:12px 40px;display:flex;gap:32px}}
.stat-label{{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.8px}}
.stat-value{{font-size:15px;font-weight:600;color:var(--blue)}}
.messages{{max-width:900px;margin:0 auto;padding:24px 40px}}
.day-divider{{display:flex;align-items:center;gap:12px;margin:24px 0}}
.day-divider::before,.day-divider::after{{content:'';flex:1;height:1px;background:var(--border)}}
.day-divider span{{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;padding:4px 12px;background:var(--surface);border-radius:20px;border:1px solid var(--border)}}
.msg-group{{display:flex;gap:14px;padding:6px 10px;border-radius:8px;margin:2px -10px;transition:background .15s}}
.msg-group:hover{{background:var(--surface2)}}
.avatar{{width:40px;height:40px;border-radius:50%;flex-shrink:0;margin-top:2px;border:1px solid var(--border)}}
.avatar-spacer{{width:40px;flex-shrink:0}}
.msg-content{{flex:1;min-width:0}}
.msg-header{{display:flex;align-items:center;gap:8px;margin-bottom:3px}}
.username{{font-weight:600;font-size:15px}}
.timestamp{{font-size:11px;color:var(--muted)}}
.badge{{font-size:10px;font-weight:700;padding:2px 6px;border-radius:4px;letter-spacing:.5px}}
.badge.staff{{background:rgba(0,229,160,.15);color:var(--staff);border:1px solid rgba(0,229,160,.3)}}
.badge.owner{{background:rgba(255,215,0,.15);color:var(--owner);border:1px solid rgba(255,215,0,.3)}}
.badge.bot{{background:rgba(88,101,242,.15);color:var(--bot);border:1px solid rgba(88,101,242,.3)}}
.msg-text{{color:#c9d1e0;word-break:break-word}}
.msg-text a{{color:var(--blue);text-decoration:none}}
.msg-text code{{background:#1e2333;padding:1px 5px;border-radius:4px;font-family:monospace;font-size:13px}}
.attachment-img{{max-width:400px;max-height:300px;border-radius:8px;margin-top:8px;display:block;border:1px solid var(--border)}}
.attachment-file{{display:inline-block;margin-top:6px;padding:6px 12px;background:var(--surface2);border:1px solid var(--border);border-radius:6px;color:var(--blue);text-decoration:none;font-size:13px}}
.embed{{margin-top:8px;background:var(--surface2);border-left:4px solid var(--blue);border-radius:4px;padding:10px 14px;max-width:520px}}
.embed-title{{font-weight:600;color:var(--text);margin-bottom:4px}}
.embed-desc{{color:var(--muted);font-size:13px;white-space:pre-line}}
.footer{{text-align:center;padding:40px;border-top:1px solid var(--border);color:var(--muted);font-size:12px;margin-top:40px}}
.footer a{{color:var(--blue);text-decoration:none}}
.footer-logo{{font-family:'Rajdhani',sans-serif;font-size:22px;font-weight:700;color:var(--blue);letter-spacing:2px;margin-bottom:8px;text-shadow:0 0 15px rgba(0,191,255,.3)}}
</style>
</head>
<body>
<div class="header">
  <img src="{VALORA_LOGO}" class="header-logo" alt="Valora" onerror="this.style.display='none'">
  <div class="header-info">
    <h1>VALORA STORE</h1>
    <p>{cat_info["emoji"]} {cat_info["label"]} • #{channel.name}</p>
  </div>
  <div class="header-meta">
    <span>Generated: <strong>{datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M")} UTC</strong></span>
    <span>Server: <strong>{guild.name}</strong></span>
  </div>
</div>
<div class="stats-bar">
  <div class="stat"><div class="stat-label">Messages</div><div class="stat-value">{len(messages)}</div></div>
  <div class="stat"><div class="stat-label">Channel</div><div class="stat-value">#{channel.name}</div></div>
  <div class="stat"><div class="stat-label">Category</div><div class="stat-value">{cat_info["label"]}</div></div>
</div>
<div class="messages">
  <div class="day-divider"><span>Ticket Opened</span></div>
  {messages_html}
  <div class="day-divider"><span>Ticket Closed</span></div>
</div>
<div class="footer">
  <div class="footer-logo">💎 VALORA</div>
  <p><a href="{VALORA_WEBSITE}" target="_blank">valora-store.mysellauth.com</a> • Transcript generated automatically</p>
</div>
</body>
</html>'''

# ============================================================
#  CLOSE TICKET LOGIC
# ============================================================
async def close_ticket(channel: discord.TextChannel, guild: discord.Guild, closed_by=None):
    info = tickets_data.get(str(channel.id))
    if not info:
        await channel.delete()
        return

    messages = [m async for m in channel.history(limit=500, oldest_first=True)]
    html = generate_transcript(channel, messages, guild)

    transcript_ch = guild.get_channel(TRANSCRIPT_CHANNEL_ID)
    if transcript_ch:
        user = guild.get_member(info["user_id"])
        cat  = TICKET_CATEGORIES.get(info.get("category", ""), {"label": "Support", "emoji": "🎫"})
        user_str = user.mention if user else "<@" + str(info["user_id"]) + ">"
        opened_ts = int(datetime.fromisoformat(info["created_at"]).timestamp())
        closed_str = closed_by.mention if closed_by else "Auto-Close ⏰"
        embed = discord.Embed(
            title=f"📋 Transcript — #{channel.name}",
            description=(
                f"**User:** {user_str}\n"
                f"**Category:** {cat['emoji']} {cat['label']}\n"
                f"**Opened:** <t:{opened_ts}:F>\n"
                f"**Closed by:** {closed_str}\n"
                f"**Messages:** {len(messages)}"
            ),
            color=VALORA_COLOR,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_footer(text="Valora Store • Ticket System", icon_url=VALORA_LOGO)
        await transcript_ch.send(
            embed=embed,
            file=discord.File(io.BytesIO(html.encode()), filename=f"transcript-{channel.name}.html")
        )

    tickets_data[str(channel.id)]["status"] = "closed"
    save_tickets(tickets_data)
    await channel.delete()

# ============================================================
#  VIEWS & SELECTS
# ============================================================
class TicketSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(
            placeholder="Select a category to open a ticket...",
            min_values=1, max_values=1,
            custom_id="valora_ticket_select",
            options=[
                discord.SelectOption(label=v["label"], description=v["description"], emoji=v["emoji"], value=k)
                for k, v in TICKET_CATEGORIES.items()
            ]
        )

    async def callback(self, interaction: discord.Interaction):
        cat_key = self.values[0]
        cat     = TICKET_CATEGORIES[cat_key]
        guild   = interaction.guild

        # Duplicate check
        for ch in guild.text_channels:
            if ch.topic and f"uid-{interaction.user.id}" in ch.topic:
                await interaction.response.send_message(f"❌ You already have an open ticket: {ch.mention}", ephemeral=True)
                return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user:   discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me:           discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True, read_message_history=True),
        }
        for rid in STAFF_ROLE_IDS + ADMIN_ROLE_IDS:
            role = guild.get_role(rid)
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

        ticket_cat = guild.get_channel(TICKET_CATEGORY_ID)
        num        = len([c for c in guild.text_channels if c.name.startswith("ticket-")]) + 1
        channel    = await guild.create_text_channel(
            name=f"ticket-{num:04d}",
            overwrites=overwrites,
            category=ticket_cat,
            topic=f"uid-{interaction.user.id} | {cat_key} | open"
        )

        tickets_data[str(channel.id)] = {
            "user_id": interaction.user.id,
            "category": cat_key,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_activity": datetime.now(timezone.utc).isoformat(),
            "auto_close": True,
            "status": "open"
        }
        save_tickets(tickets_data)

        await interaction.response.send_message(f"✅ Ticket created: {channel.mention}", ephemeral=True)

        embed = discord.Embed(
            title=f"{cat['emoji']} {cat['label']} — Ticket #{num:04d}",
            description=(
                f"Welcome, {interaction.user.mention}! 👋\n\n"
                "**Our support team will be with you shortly.**\n\n"
                f"🌐 **Website:** [valora-store.mysellauth.com]({VALORA_WEBSITE})\n\n"
                "Please describe your issue and we'll get back to you as soon as possible."
            ),
            color=cat["color"],
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_thumbnail(url=VALORA_LOGO)
        embed.set_footer(text="Valora Store • Premium Products", icon_url=VALORA_LOGO)
        await channel.send(content=interaction.user.mention, embed=embed, view=TicketControlView())


class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())


class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger,   emoji="🔒", custom_id="valora_close_ticket")
    async def close_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        info = tickets_data.get(str(interaction.channel.id))
        if not info:
            await interaction.response.send_message("❌ Not a ticket channel.", ephemeral=True)
            return
        is_owner = info["user_id"] == interaction.user.id
        if not member_is_staff(interaction.user) and not is_owner:
            await interaction.response.send_message("❌ Only staff or the ticket owner can close this.", ephemeral=True)
            return
        await interaction.response.send_message("🔒 Closing in 5 seconds...")
        await asyncio.sleep(5)
        await close_ticket(interaction.channel, interaction.guild, closed_by=interaction.user)

    @discord.ui.button(label="Claim Ticket", style=discord.ButtonStyle.success, emoji="✋", custom_id="valora_claim_ticket")
    async def claim_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not member_is_staff(interaction.user):
            await interaction.response.send_message("❌ Only staff can claim tickets.", ephemeral=True)
            return
        embed = discord.Embed(description=f"✋ **{interaction.user.mention}** has claimed this ticket!", color=VALORA_COLOR)
        await interaction.response.send_message(embed=embed)


class StoreView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label="Visit Store", style=discord.ButtonStyle.link, url=VALORA_WEBSITE, emoji="🌐", row=0))

    @discord.ui.button(label="Open Purchase Ticket", style=discord.ButtonStyle.primary, emoji="🛒", custom_id="valora_store_ticket", row=1)
    async def store_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = discord.ui.View(timeout=60)
        select = TicketSelect()
        select.options = [o for o in select.options if o.value == "purchase"]
        view.add_item(select)
        await interaction.response.send_message("Select ticket type:", view=view, ephemeral=True)

# ============================================================
#  BOT SETUP
# ============================================================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# ============================================================
#  AUTO-CLOSE TASK
# ============================================================
@tasks.loop(seconds=300)
async def auto_close_task():
    now = datetime.now(timezone.utc)
    for channel_id, info in list(tickets_data.items()):
        if info.get("status") != "open" or not info.get("auto_close", True):
            continue
        last = datetime.fromisoformat(info["last_activity"])
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if now - last >= timedelta(hours=AUTO_CLOSE_HOURS):
            for guild in bot.guilds:
                ch = guild.get_channel(int(channel_id))
                if ch:
                    try:
                        await ch.send("⏰ This ticket has been automatically closed due to inactivity.")
                        await asyncio.sleep(3)
                        await close_ticket(ch, guild, closed_by=None)
                    except Exception as e:
                        print(f"Auto-close error {channel_id}: {e}")

@auto_close_task.before_loop
async def before_auto_close():
    await bot.wait_until_ready()

# ============================================================
#  EVENTS
# ============================================================
@bot.event
async def on_ready():
    print(f"✅ Valora Bot online as {bot.user}")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="Valora Store 💎"))
    bot.add_view(TicketPanelView())
    bot.add_view(TicketControlView())
    bot.add_view(StoreView())
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"❌ Sync error: {e}")
    auto_close_task.start()

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    cid = str(message.channel.id)
    if cid in tickets_data and tickets_data[cid]["status"] == "open":
        tickets_data[cid]["last_activity"] = datetime.now(timezone.utc).isoformat()
        save_tickets(tickets_data)
    await bot.process_commands(message)

# ============================================================
#  SLASH COMMANDS
# ============================================================
@bot.tree.command(name="panel", description="Send the Valora ticket panel (Admin only)")
@app_commands.guild_only()
async def cmd_panel(interaction: discord.Interaction):
    if not member_is_admin(interaction.user):
        await interaction.response.send_message("❌ Admin only.", ephemeral=True)
        return
    embed = discord.Embed(
        title="🎫 Valora Support Tickets",
        description=(
            "**Need help? Open a ticket below!**\n\n"
            "🛒 **Purchase** — Help with buying a product\n"
            "💰 **Reseller** — Apply to our reseller program\n"
            "🔑 **Claim Key** — Claim your role or product key\n"
            "🔒 **HWID Reset** — Reset your hardware ID\n"
            "🎫 **Support** — General support\n\n"
            f"🌐 **Shop:** [valora-store.mysellauth.com]({VALORA_WEBSITE})\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            "*Select a category from the dropdown below to open a ticket.*"
        ),
        color=VALORA_COLOR,
        timestamp=datetime.now(timezone.utc)
    )
    embed.set_thumbnail(url=VALORA_LOGO)
    embed.set_footer(text="Valora Store • Premium Products 💎", icon_url=VALORA_LOGO)
    await interaction.response.send_message("✅ Panel sent!", ephemeral=True)
    await interaction.channel.send(embed=embed, view=TicketPanelView())


@bot.tree.command(name="store", description="Send the Valora store panel (Admin only)")
@app_commands.guild_only()
async def cmd_store(interaction: discord.Interaction):
    if not member_is_admin(interaction.user):
        await interaction.response.send_message("❌ Admin only.", ephemeral=True)
        return
    embed = discord.Embed(
        title="💎 VALORA STORE",
        description=(
            "**Welcome to Valora — Premium Products & Services**\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🌐 **Visit our website for instant delivery:**\n"
            f"[**valora-store.mysellauth.com**]({VALORA_WEBSITE})\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "💳 **Payment Methods**\n\n"
            "**🖥️ Website (Instant Delivery)**\n"
            "├ 💳 Credit / Debit Card\n"
            "├  Apple Pay\n"
            "├ 🔷 iDEAL\n"
            "└ 🪙 Cryptocurrency\n\n"
            "**🎫 Ticket Orders**\n"
            "├ 💵 Cash App\n"
            "├ 🅿️ PayPal F&F\n"
            "├ 🎟️ Crypto Voucher\n"
            "└ 🟡 Binance Giftcards\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📦 **How to Order**\n"
            "**Option 1:** Visit our website for **instant delivery**\n"
            "**Option 2:** Open a 🛒 **Purchase Ticket** for manual orders\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            "*Questions? Open a support ticket!*"
        ),
        color=VALORA_COLOR,
        timestamp=datetime.now(timezone.utc)
    )
    embed.set_thumbnail(url=VALORA_LOGO)
    embed.set_footer(text="Valora Store • Premium Products 💎", icon_url=VALORA_LOGO)
    await interaction.response.send_message("✅ Store panel sent!", ephemeral=True)
    await interaction.channel.send(embed=embed, view=StoreView())


@bot.tree.command(name="close", description="Close the current ticket (Staff only)")
@app_commands.guild_only()
async def cmd_close(interaction: discord.Interaction):
    if not member_is_staff(interaction.user):
        await interaction.response.send_message("❌ Staff only.", ephemeral=True)
        return
    if str(interaction.channel.id) not in tickets_data:
        await interaction.response.send_message("❌ This is not a ticket channel.", ephemeral=True)
        return
    await interaction.response.send_message("🔒 Closing in 5 seconds...")
    await asyncio.sleep(5)
    await close_ticket(interaction.channel, interaction.guild, closed_by=interaction.user)


@bot.tree.command(name="add", description="Add a user to the current ticket (Staff only)")
@app_commands.describe(user="User to add")
@app_commands.guild_only()
async def cmd_add(interaction: discord.Interaction, user: discord.Member):
    if not member_is_staff(interaction.user):
        await interaction.response.send_message("❌ Staff only.", ephemeral=True)
        return
    if str(interaction.channel.id) not in tickets_data:
        await interaction.response.send_message("❌ Not a ticket channel.", ephemeral=True)
        return
    await interaction.channel.set_permissions(user, view_channel=True, send_messages=True, read_message_history=True)
    embed = discord.Embed(description=f"✅ {user.mention} has been added to the ticket.", color=discord.Color.green())
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="remove", description="Remove a user from the current ticket (Staff only)")
@app_commands.describe(user="User to remove")
@app_commands.guild_only()
async def cmd_remove(interaction: discord.Interaction, user: discord.Member):
    if not member_is_staff(interaction.user):
        await interaction.response.send_message("❌ Staff only.", ephemeral=True)
        return
    if str(interaction.channel.id) not in tickets_data:
        await interaction.response.send_message("❌ Not a ticket channel.", ephemeral=True)
        return
    await interaction.channel.set_permissions(user, overwrite=None)
    embed = discord.Embed(description=f"✅ {user.mention} has been removed from the ticket.", color=discord.Color.red())
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="autoclose", description="Enable or disable auto-close for this ticket (Staff only)")
@app_commands.describe(enabled="True = on, False = off")
@app_commands.guild_only()
async def cmd_autoclose(interaction: discord.Interaction, enabled: bool):
    if not member_is_staff(interaction.user):
        await interaction.response.send_message("❌ Staff only.", ephemeral=True)
        return
    if str(interaction.channel.id) not in tickets_data:
        await interaction.response.send_message("❌ Not a ticket channel.", ephemeral=True)
        return
    tickets_data[str(interaction.channel.id)]["auto_close"] = enabled
    save_tickets(tickets_data)
    status = "✅ enabled" if enabled else "❌ disabled"
    embed = discord.Embed(description=f"Auto-close is now **{status}** for this ticket.", color=VALORA_COLOR)
    await interaction.response.send_message(embed=
