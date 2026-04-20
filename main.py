# audioop shim MUST be first — fixes Python 3.13 compatibility
import audioop  # noqa: F401

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
#  CONFIG
# ============================================================
TOKEN                 = os.getenv("DISCORD_TOKEN", "")
GUILD_ID              = int(os.getenv("GUILD_ID", 0))
TICKET_CATEGORY_ID    = int(os.getenv("TICKET_CATEGORY_ID", 0))
TRANSCRIPT_CHANNEL_ID = int(os.getenv("TRANSCRIPT_CHANNEL_ID", 0))
STAFF_ROLE_IDS        = [int(x) for x in os.getenv("STAFF_ROLE_IDS", "").split(",") if x.strip().isdigit()]
ADMIN_ROLE_IDS        = [int(x) for x in os.getenv("ADMIN_ROLE_IDS", "").split(",") if x.strip().isdigit()]
AUTO_CLOSE_HOURS      = int(os.getenv("AUTO_CLOSE_HOURS", 24))
VALORA_LOGO           = os.getenv("VALORA_LOGO", "")
VALORA_WEBSITE        = "https://valora-store.mysellauth.com/"
VALORA_COLOR          = 0x00BFFF

# Verification
VERIFIED_ROLE_ID      = int(os.getenv("VERIFIED_ROLE_ID", 0))   # Role given after verify
VERIFY_CHANNEL_ID     = int(os.getenv("VERIFY_CHANNEL_ID", 0))  # Channel where panel is posted
VERIFY_LOG_CHANNEL_ID = int(os.getenv("VERIFY_LOG_CHANNEL_ID", 0))  # Log channel for verifications

# Discord OAuth2 App credentials (from discord.com/developers)
CLIENT_ID             = os.getenv("DISCORD_CLIENT_ID", "")
CLIENT_SECRET         = os.getenv("DISCORD_CLIENT_SECRET", "")
# The URL where your webserver (web.py) is running, e.g. https://yourapp.railway.app
WEB_BASE_URL          = os.getenv("WEB_BASE_URL", "http://localhost:5000")

TICKET_CATEGORIES = {
    "purchase": {"label": "Purchase",               "description": "Request help with a purchase.",       "emoji": "🛒", "color": 0x00BFFF},
    "reseller": {"label": "Apply to be a Reseller", "description": "Apply to Valora's Reseller Program.", "emoji": "💰", "color": 0xFFD700},
    "claim":    {"label": "Claim Role / Key",        "description": "Claim your role or product key.",     "emoji": "🔑", "color": 0x00FF88},
    "hwid":     {"label": "HWID Reset",              "description": "Request a reset for your key.",       "emoji": "🔒", "color": 0xFF6B35},
    "support":  {"label": "Get Support",             "description": "Request support from our staff.",     "emoji": "🎫", "color": 0x9B59B6},
}

# ============================================================
#  STORAGE
# ============================================================
TICKETS_FILE   = "tickets.json"
VERIFIED_FILE  = "verified.json"

def load_json(path):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

tickets_data  = load_json(TICKETS_FILE)
verified_data = load_json(VERIFIED_FILE)

# ============================================================
#  PERMISSION HELPERS
# ============================================================
def is_staff(member: discord.Member) -> bool:
    if member.guild_permissions.administrator:
        return True
    return any(r.id in STAFF_ROLE_IDS + ADMIN_ROLE_IDS for r in member.roles)

def is_admin(member: discord.Member) -> bool:
    if member.guild_permissions.administrator:
        return True
    return any(r.id in ADMIN_ROLE_IDS for r in member.roles)

# ============================================================
#  HTML TRANSCRIPT GENERATOR
# ============================================================
def generate_transcript(channel, messages, guild):
    cat_key = ""
    if channel.topic and " | " in channel.topic:
        parts = channel.topic.split(" | ")
        if len(parts) > 1:
            cat_key = parts[1].strip()
    cat = TICKET_CATEGORIES.get(cat_key, {"label": "Support", "emoji": "🎫"})

    msgs_html = ""
    prev_id   = None
    for msg in messages:
        av  = str(msg.author.display_avatar.url) if msg.author.display_avatar else ""
        stf = any(r.id in STAFF_ROLE_IDS + ADMIN_ROLE_IDS for r in getattr(msg.author, "roles", []))
        if msg.author.id == guild.owner_id:
            bdg = '<span class="badge owner">Owner</span>'
        elif stf:
            bdg = '<span class="badge staff">Staff</span>'
        elif msg.author.bot:
            bdg = '<span class="badge bot">BOT</span>'
        else:
            bdg = ""
        att = ""
        for a in msg.attachments:
            if a.content_type and a.content_type.startswith("image"):
                att += f'<img src="{a.url}" class="att-img" alt="img">'
            else:
                att += f'<a href="{a.url}" class="att-file" target="_blank">📎 {a.filename}</a>'
        emb = ""
        for e in msg.embeds:
            ec  = f"#{e.color.value:06x}" if e.color else "#00BFFF"
            et  = f"<div class='et'>{e.title}</div>" if e.title else ""
            ed  = f"<div class='ed'>{e.description}</div>" if e.description else ""
            emb += f'<div class="emb" style="border-left-color:{ec}">{et}{ed}</div>'
        txt = msg.content or ""
        txt = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', txt)
        txt = re.sub(r'\*(.+?)\*',     r'<em>\1</em>',         txt)
        txt = re.sub(r'`(.+?)`',       r'<code>\1</code>',     txt)
        txt = re.sub(r'https?://\S+',  lambda m: f'<a href="{m.group()}" target="_blank">{m.group()}</a>', txt)
        ts   = msg.created_at.strftime("%d/%m/%Y %H:%M")
        same = prev_id == msg.author.id
        prev_id = msg.author.id
        av_html  = f'<img src="{av}" class="av" alt="av">' if not same else '<div class="avs"></div>'
        hdr_html = f'<div class="mh"><span class="un">{msg.author.display_name}</span>{bdg}<span class="ts">{ts}</span></div>' if not same else ""
        msgs_html += f'<div class="mg{"" if not same else " sa"}">{av_html}<div class="mc">{hdr_html}<div class="mt">{txt}</div>{att}{emb}</div></div>'

    logo_html = f'<img src="{VALORA_LOGO}" class="hl" alt="Valora" onerror="this.style.display=\'none\'">' if VALORA_LOGO else ""
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>Transcript — {channel.name}</title>
<style>:root{{--bg:#0d0f14;--s1:#13161e;--s2:#1a1e2a;--br:#1e2333;--bl:#00BFFF;--tx:#e0e6f0;--mu:#6b7590;--sg:#00e5a0;--ow:#FFD700;--bt:#5865F2}}
*{{box-sizing:border-box;margin:0;padding:0}}body{{background:var(--bg);color:var(--tx);font-family:'Inter',sans-serif;font-size:14px;line-height:1.6}}
.hd{{background:linear-gradient(135deg,#0a0c14,#0d1220);border-bottom:1px solid var(--br);padding:24px 40px;display:flex;align-items:center;gap:20px}}
.hl{{width:60px;height:60px;border-radius:50%;border:2px solid var(--bl)}}.hi h1{{font-size:24px;color:var(--bl)}}.hi p{{color:var(--mu);font-size:12px}}
.hm{{margin-left:auto;font-size:11px;color:var(--mu)}}.hm strong{{color:var(--tx)}}
.ms{{max-width:880px;margin:0 auto;padding:20px 40px}}.mg{{display:flex;gap:12px;padding:5px 8px;border-radius:8px;margin:1px -8px}}
.av{{width:38px;height:38px;border-radius:50%;flex-shrink:0;border:1px solid var(--br)}}.avs{{width:38px;flex-shrink:0}}.mc{{flex:1}}
.mh{{display:flex;align-items:center;gap:6px;margin-bottom:2px}}.un{{font-weight:600}}.ts{{font-size:10px;color:var(--mu)}}
.badge{{font-size:9px;font-weight:700;padding:1px 5px;border-radius:3px}}.badge.staff{{background:rgba(0,229,160,.15);color:var(--sg)}}
.badge.owner{{background:rgba(255,215,0,.15);color:var(--ow)}}.badge.bot{{background:rgba(88,101,242,.15);color:var(--bt)}}
.mt{{color:#c9d1e0;word-break:break-word}}.att-img{{max-width:380px;border-radius:8px;margin-top:6px;display:block}}
.emb{{margin-top:6px;background:var(--s2);border-left:4px solid var(--bl);border-radius:4px;padding:8px 12px}}
.ft{{text-align:center;padding:36px;border-top:1px solid var(--br);color:var(--mu);font-size:11px}}</style></head>
<body><div class="hd">{logo_html}<div class="hi"><h1>VALORA STORE</h1><p>{cat["emoji"]} {cat["label"]} • #{channel.name}</p></div>
<div class="hm">Generated: <strong>{datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M")} UTC</strong></div></div>
<div class="ms">{msgs_html}</div>
<div class="ft"><p><a href="{VALORA_WEBSITE}" style="color:var(--bl)">valora-store.mysellauth.com</a> • Transcript generated automatically</p></div>
</body></html>"""

# ============================================================
#  CLOSE TICKET LOGIC
# ============================================================
async def close_ticket(channel, guild, closed_by=None):
    info = tickets_data.get(str(channel.id))
    if not info:
        try: await channel.delete()
        except: pass
        return
    messages = [m async for m in channel.history(limit=500, oldest_first=True)]
    html     = generate_transcript(channel, messages, guild)
    tr_ch    = guild.get_channel(TRANSCRIPT_CHANNEL_ID)
    if tr_ch:
        user      = guild.get_member(info["user_id"])
        cat       = TICKET_CATEGORIES.get(info.get("category", ""), {"label": "Support", "emoji": "🎫"})
        user_str  = user.mention if user else f"<@{info['user_id']}>"
        opened_ts = int(datetime.fromisoformat(info["created_at"]).timestamp())
        closed_str = closed_by.mention if closed_by else "Auto-Close ⏰"
        embed = discord.Embed(
            title=f"📋 Transcript — #{channel.name}",
            description=(f"**User:** {user_str}\n**Category:** {cat['emoji']} {cat['label']}\n"
                         f"**Opened:** <t:{opened_ts}:F>\n**Closed by:** {closed_str}\n**Messages:** {len(messages)}"),
            color=VALORA_COLOR, timestamp=datetime.now(timezone.utc)
        )
        embed.set_footer(text="Valora Store • Ticket System")
        try:
            await tr_ch.send(embed=embed, file=discord.File(io.BytesIO(html.encode()), filename=f"transcript-{channel.name}.html"))
        except Exception as e:
            print(f"Transcript send error: {e}")
    tickets_data[str(channel.id)]["status"] = "closed"
    save_json(TICKETS_FILE, tickets_data)
    try: await channel.delete()
    except Exception as e: print(f"Channel delete error: {e}")

# ============================================================
#  VIEWS — TICKET
# ============================================================
class TicketSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(
            placeholder="Select a category to open a ticket...",
            min_values=1, max_values=1,
            custom_id="valora_ticket_select",
            options=[discord.SelectOption(label=v["label"], description=v["description"], emoji=v["emoji"], value=k)
                     for k, v in TICKET_CATEGORIES.items()]
        )

    async def callback(self, interaction: discord.Interaction):
        cat_key = self.values[0]
        cat     = TICKET_CATEGORIES[cat_key]
        guild   = interaction.guild
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
        cat_channel = guild.get_channel(TICKET_CATEGORY_ID)
        num = len([c for c in guild.text_channels if c.name.startswith("ticket-")]) + 1
        try:
            channel = await guild.create_text_channel(
                name=f"ticket-{num:04d}", overwrites=overwrites, category=cat_channel,
                topic=f"uid-{interaction.user.id} | {cat_key} | open"
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ Could not create ticket: {e}", ephemeral=True)
            return
        tickets_data[str(channel.id)] = {
            "user_id": interaction.user.id, "category": cat_key,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_activity": datetime.now(timezone.utc).isoformat(),
            "auto_close": True, "status": "open"
        }
        save_json(TICKETS_FILE, tickets_data)
        await interaction.response.send_message(f"✅ Ticket created: {channel.mention}", ephemeral=True)
        embed = discord.Embed(
            title=f"{cat['emoji']} {cat['label']} — Ticket #{num:04d}",
            description=(f"Welcome, {interaction.user.mention}! 👋\n\n**Our support team will be with you shortly.**\n\n"
                         f"🌐 **Website:** [valora-store.mysellauth.com]({VALORA_WEBSITE})\n\n"
                         "Please describe your issue and we'll get back to you as soon as possible."),
            color=cat["color"], timestamp=datetime.now(timezone.utc)
        )
        if VALORA_LOGO: embed.set_thumbnail(url=VALORA_LOGO)
        embed.set_footer(text="Valora Store • Premium Products")
        await channel.send(content=interaction.user.mention, embed=embed, view=TicketControlView())

class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())

class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="valora_close_ticket")
    async def close_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        info = tickets_data.get(str(interaction.channel.id))
        if not info:
            await interaction.response.send_message("❌ Not a ticket channel.", ephemeral=True); return
        if not is_staff(interaction.user) and info["user_id"] != interaction.user.id:
            await interaction.response.send_message("❌ Only staff or the ticket owner can close this.", ephemeral=True); return
        await interaction.response.send_message("🔒 Closing in 5 seconds...")
        await asyncio.sleep(5)
        await close_ticket(interaction.channel, interaction.guild, closed_by=interaction.user)

    @discord.ui.button(label="Claim Ticket", style=discord.ButtonStyle.success, emoji="✋", custom_id="valora_claim_ticket")
    async def claim_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_staff(interaction.user):
            await interaction.response.send_message("❌ Only staff can claim tickets.", ephemeral=True); return
        embed = discord.Embed(description=f"✋ **{interaction.user.mention}** has claimed this ticket!", color=VALORA_COLOR)
        await interaction.response.send_message(embed=embed)

class StoreView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label="Visit Store", style=discord.ButtonStyle.link, url=VALORA_WEBSITE, emoji="🌐", row=0))

    @discord.ui.button(label="Open Purchase Ticket", style=discord.ButtonStyle.primary, emoji="🛒", custom_id="valora_store_ticket", row=1)
    async def store_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        view   = discord.ui.View(timeout=60)
        select = TicketSelect()
        select.options = [o for o in select.options if o.value == "purchase"]
        view.add_item(select)
        await interaction.response.send_message("Select ticket type:", view=view, ephemeral=True)

# ============================================================
#  VIEWS — VERIFY
# ============================================================
class VerifyView(discord.ui.View):
    def __init__(self, oauth_url: str):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(
            label="✅  Verify with Discord",
            style=discord.ButtonStyle.link,
            url=oauth_url,
            emoji="🔐"
        ))

# ============================================================
#  BOT
# ============================================================
intents = discord.Intents.default()
intents.message_content = True
intents.members          = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# ============================================================
#  AUTO-CLOSE TASK
# ============================================================
@tasks.loop(seconds=300)
async def auto_close_task():
    now = datetime.now(timezone.utc)
    for channel_id, info in list(tickets_data.items()):
        if info.get("status") != "open" or not info.get("auto_close", True): continue
        last = datetime.fromisoformat(info["last_activity"])
        if last.tzinfo is None: last = last.replace(tzinfo=timezone.utc)
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
    print(f"✅ Valora Bot online — {bot.user}")
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
    print("✅ All systems ready!")

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot: return
    cid = str(message.channel.id)
    if cid in tickets_data and tickets_data[cid]["status"] == "open":
        tickets_data[cid]["last_activity"] = datetime.now(timezone.utc).isoformat()
        save_json(TICKETS_FILE, tickets_data)
    await bot.process_commands(message)

# ============================================================
#  SLASH COMMANDS — TICKETS
# ============================================================
@bot.tree.command(name="panel", description="Send the Valora ticket panel (Admin only)")
@app_commands.guild_only()
async def cmd_panel(interaction: discord.Interaction):
    if not is_admin(interaction.user):
        await interaction.response.send_message("❌ Admin only.", ephemeral=True); return
    embed = discord.Embed(
        title="🎫 Valora Support Tickets",
        description=("**Need help? Open a ticket below!**\n\n"
                     "🛒 **Purchase** — Help with buying a product\n"
                     "💰 **Reseller** — Apply to our reseller program\n"
                     "🔑 **Claim Key** — Claim your role or product key\n"
                     "🔒 **HWID Reset** — Reset your hardware ID\n"
                     "🎫 **Support** — General support\n\n"
                     f"🌐 **Shop:** [valora-store.mysellauth.com]({VALORA_WEBSITE})\n\n"
                     "━━━━━━━━━━━━━━━━━━━━━━━\n*Select a category from the dropdown below.*"),
        color=VALORA_COLOR, timestamp=datetime.now(timezone.utc)
    )
    if VALORA_LOGO: embed.set_thumbnail(url=VALORA_LOGO)
    embed.set_footer(text="Valora Store • Premium Products 💎")
    await interaction.response.send_message("✅ Panel sent!", ephemeral=True)
    await interaction.channel.send(embed=embed, view=TicketPanelView())

@bot.tree.command(name="store", description="Send the Valora store panel (Admin only)")
@app_commands.guild_only()
async def cmd_store(interaction: discord.Interaction):
    if not is_admin(interaction.user):
        await interaction.response.send_message("❌ Admin only.", ephemeral=True); return
    embed = discord.Embed(
        title="💎 VALORA STORE",
        description=("**Welcome to Valora — Premium Products & Services**\n\n"
                     "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                     f"🌐 **Website (Instant Delivery):**\n[**valora-store.mysellauth.com**]({VALORA_WEBSITE})\n\n"
                     "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                     "💳 **Payment Methods**\n\n**🖥️ Website**\n"
                     "├ 💳 Credit / Debit Card\n├  Apple Pay\n├ 🔷 iDEAL\n└ 🪙 Cryptocurrency\n\n"
                     "**🎫 Ticket Orders**\n"
                     "├ 💵 Cash App\n├ 🅿️ PayPal F&F\n├ 🎟️ Crypto Voucher\n└ 🟡 Binance Giftcards\n\n"
                     "━━━━━━━━━━━━━━━━━━━━━━━\n*Questions? Open a support ticket!*"),
        color=VALORA_COLOR, timestamp=datetime.now(timezone.utc)
    )
    if VALORA_LOGO: embed.set_thumbnail(url=VALORA_LOGO)
    embed.set_footer(text="Valora Store • Premium Products 💎")
    await interaction.response.send_message("✅ Store panel sent!", ephemeral=True)
    await interaction.channel.send(embed=embed, view=StoreView())

@bot.tree.command(name="close", description="Close the current ticket (Staff only)")
@app_commands.guild_only()
async def cmd_close(interaction: discord.Interaction):
    if not is_staff(interaction.user):
        await interaction.response.send_message("❌ Staff only.", ephemeral=True); return
    if str(interaction.channel.id) not in tickets_data:
        await interaction.response.send_message("❌ This is not a ticket channel.", ephemeral=True); return
    await interaction.response.send_message("🔒 Closing in 5 seconds...")
    await asyncio.sleep(5)
    await close_ticket(interaction.channel, interaction.guild, closed_by=interaction.user)

@bot.tree.command(name="add", description="Add a user to the current ticket (Staff only)")
@app_commands.describe(user="User to add")
@app_commands.guild_only()
async def cmd_add(interaction: discord.Interaction, user: discord.Member):
    if not is_staff(interaction.user):
        await interaction.response.send_message("❌ Staff only.", ephemeral=True); return
    if str(interaction.channel.id) not in tickets_data:
        await interaction.response.send_message("❌ Not a ticket channel.", ephemeral=True); return
    await interaction.channel.set_permissions(user, view_channel=True, send_messages=True, read_message_history=True)
    await interaction.response.send_message(embed=discord.Embed(description=f"✅ {user.mention} added to the ticket.", color=discord.Color.green()))

@bot.tree.command(name="remove", description="Remove a user from the current ticket (Staff only)")
@app_commands.describe(user="User to remove")
@app_commands.guild_only()
async def cmd_remove(interaction: discord.Interaction, user: discord.Member):
    if not is_staff(interaction.user):
        await interaction.response.send_message("❌ Staff only.", ephemeral=True); return
    if str(interaction.channel.id) not in tickets_data:
        await interaction.response.send_message("❌ Not a ticket channel.", ephemeral=True); return
    await interaction.channel.set_permissions(user, overwrite=None)
    await interaction.response.send_message(embed=discord.Embed(description=f"✅ {user.mention} removed from the ticket.", color=discord.Color.red()))

@bot.tree.command(name="autoclose", description="Enable or disable auto-close for this ticket (Staff only)")
@app_commands.describe(enabled="True = on  |  False = off")
@app_commands.guild_only()
async def cmd_autoclose(interaction: discord.Interaction, enabled: bool):
    if not is_staff(interaction.user):
        await interaction.response.send_message("❌ Staff only.", ephemeral=True); return
    if str(interaction.channel.id) not in tickets_data:
        await interaction.response.send_message("❌ Not a ticket channel.", ephemeral=True); return
    tickets_data[str(interaction.channel.id)]["auto_close"] = enabled
    save_json(TICKETS_FILE, tickets_data)
    status = "✅ enabled" if enabled else "❌ disabled"
    await interaction.response.send_message(embed=discord.Embed(description=f"Auto-close is now **{status}** for this ticket.", color=VALORA_COLOR))

# ============================================================
#  SLASH COMMANDS — VERIFY
# ============================================================
@bot.tree.command(name="verifypanel", description="Send the verification panel (Admin only)")
@app_commands.guild_only()
async def cmd_verifypanel(interaction: discord.Interaction):
    if not is_admin(interaction.user):
        await interaction.response.send_message("❌ Admin only.", ephemeral=True)
        return

    import urllib.parse

    # Redirect URL (MUSS encoded sein)
    redirect_uri = urllib.parse.quote(f"{WEB_BASE_URL}/callback", safe="")

    # OAuth URL (correct Discord format)
    oauth_url = (
        f"https://discord.com/oauth2/authorize"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope=identify%20guilds.join"
    )

    embed = discord.Embed(
        title="🔐 Valora Verification",
        description=(
            "**Verify your Discord account to gain access to the server.**\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🔒 Why verify?\n"
            "Keeps the server safe from bots.\n\n"
            "✅ What happens?\n"
            "You get the Verified role.\n\n"
            "👉 Click the button below to continue."
        ),
        color=VALORA_COLOR,
        timestamp=datetime.now(timezone.utc)
    )

    if VALORA_LOGO:
        embed.set_thumbnail(url=VALORA_LOGO)

    embed.set_footer(text="Valora Store • Secure Verification 🔐")

    await interaction.response.send_message("✅ Verify panel sent!", ephemeral=True)
    await interaction.channel.send(embed=embed, view=VerifyView(oauth_url))@bot.tree.command(name="verifypanel", description="Send the verification panel (Admin only)")
@app_commands.guild_only()
async def cmd_verifypanel(interaction: discord.Interaction):
    if not is_admin(interaction.user):
        await interaction.response.send_message("❌ Admin only.", ephemeral=True); return

    redirect_uri = f"{WEB_BASE_URL}/callback"
    # Scopes: identify (read user info) + guilds.join (add user to servers)
    oauth_url = (
        f"https://discord.com/oauth2/authorize"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope=identify%20guilds.join"
    )

    embed = discord.Embed(
        title="🔐 Valora Verification",
        description=(
            "**Verify your Discord account to gain access to the server.**\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🔒 **Why verify?**\n"
            "Verification keeps our community safe and free from bots & raiders.\n\n"
            "✅ **What happens when I verify?**\n"
            "You'll be granted the **Verified** role and gain access to all channels.\n\n"
            "🌐 **How?**\n"
            "Click the button below — you'll be taken to a secure page where you log in with Discord.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            "*Your data is only used to verify your identity. We do not store passwords.*"
        ),
        color=VALORA_COLOR,
        timestamp=datetime.now(timezone.utc)
    )
    if VALORA_LOGO: embed.set_thumbnail(url=VALORA_LOGO)
    embed.set_footer(text="Valora Store • Secure Verification 🔐")

    await interaction.response.send_message("✅ Verify panel sent!", ephemeral=True)
    await interaction.channel.send(embed=embed, view=VerifyView(oauth_url))

# ============================================================
#  RUN
# ============================================================
bot.run(TOKEN)
