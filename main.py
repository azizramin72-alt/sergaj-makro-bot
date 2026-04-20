import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import os
import random
from datetime import datetime, timedelta, timezone

# ─────────────────────────────────────────────
#  BOT SETUP
# ─────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# Tracks auto-created voice channels: {channel_id: owner_id}
temp_voice_channels: dict[int, int] = {}

# The "Join to Create" channel configs per channel ID
# Format: { creator_channel_id: { "label": str, "limit": int, "category_id": int } }
voice_creators: dict[int, dict] = {}

# Active mutes: { (guild_id, user_id): asyncio.Task }
active_mutes: dict[tuple[int, int], asyncio.Task] = {}

# ─────────────────────────────────────────────
#  THEME COLORS (Purple palette)
# ─────────────────────────────────────────────
PURPLE_DARK  = 0x4b0082
PURPLE_MID   = 0x7b2fbe
PURPLE_LIGHT = 0x9b59b6
PURPLE_NEON  = 0xbf5fff
GOLD         = 0xf1c40f
RED_ERR      = 0xe74c3c
GREEN_OK     = 0x2ecc71
CYAN_INFO    = 0x00bfff

# ─────────────────────────────────────────────
#  SERVER CONFIGURATION
# ─────────────────────────────────────────────
ROLES = [
    {"name": "👑 Owner",          "color": discord.Color.from_str("#ff0000"), "hoist": True,  "perms": discord.Permissions.all()},
    {"name": "⚙️ Admin",          "color": discord.Color.from_str("#ff6600"), "hoist": True,  "perms": discord.Permissions(administrator=True)},
    {"name": "🛡️ Moderator",      "color": discord.Color.from_str("#bf5fff"), "hoist": True,  "perms": discord.Permissions(kick_members=True, ban_members=True, manage_messages=True)},
    {"name": "🔇 Muted",          "color": discord.Color.from_str("#808080"), "hoist": False, "perms": discord.Permissions.none()},
    {"name": "⭐ VIP",            "color": discord.Color.from_str("#f1c40f"), "hoist": True,  "perms": discord.Permissions.none()},
    {"name": "👑 Champion",       "color": discord.Color.from_str("#9b59b6"), "hoist": True,  "perms": discord.Permissions.none()},
    {"name": "💎 Diamond",        "color": discord.Color.from_str("#00bfff"), "hoist": True,  "perms": discord.Permissions.none()},
    {"name": "🥇 Gold",           "color": discord.Color.from_str("#f39c12"), "hoist": True,  "perms": discord.Permissions.none()},
    {"name": "🥈 Silver",         "color": discord.Color.from_str("#95a5a6"), "hoist": True,  "perms": discord.Permissions.none()},
    {"name": "🥉 Bronze",         "color": discord.Color.from_str("#cd6133"), "hoist": True,  "perms": discord.Permissions.none()},
    {"name": "🖥️ PC Player",      "color": discord.Color.from_str("#3498db"), "hoist": False, "perms": discord.Permissions.none()},
    {"name": "🎮 Console Player", "color": discord.Color.from_str("#2ecc71"), "hoist": False, "perms": discord.Permissions.none()},
    {"name": "📱 Mobile Player",  "color": discord.Color.from_str("#e67e22"), "hoist": False, "perms": discord.Permissions.none()},
    {"name": "🎮 Member",         "color": discord.Color.from_str("#7b2fbe"), "hoist": False, "perms": discord.Permissions.none()},
]

CATEGORIES = [
    {
        "name": "🏠 | WELCOME",
        "private": False,
        "channels": [
            {
                "name": "📋・rules",
                "topic": "Read the rules before doing anything else.",
                "readonly": True,
                "embed": {
                    "title": "📋  SERVER RULES",
                    "description": (
                        "**1.** Respect everyone – no toxicity, harassment or hate speech.\n"
                        "**2.** No spam or self-promotion without permission.\n"
                        "**3.** Keep discussions on-topic in each channel.\n"
                        "**4.** No cheating, hacking or exploit discussions.\n"
                        "**5.** No NSFW content of any kind.\n"
                        "**6.** Listen to staff – their word is final.\n"
                        "**7.** English only in all public channels.\n"
                        "**8.** Have fun and respect the vibe! 🎮"
                    ),
                    "color": PURPLE_NEON,
                    "footer": "Break the rules → Ban. Simple.",
                },
            },
            {
                "name": "👋・welcome",
                "topic": "New players drop here. Say hello!",
                "readonly": True,
                "embed": {
                    "title": "⚡  WELCOME TO THE BATTLE BUS!",
                    "description": (
                        "Glad you survived the bus drop! 🪂\n\n"
                        "You've just landed on the **#1 Fortnite Community Server**.\n\n"
                        "📋 Read **#rules** first\n"
                        "🎮 Head to **#looking-for-squad** to find teammates\n"
                        "📊 Check **#leaderboard** to see who's dominating\n"
                        "🗣️ Hang out in **#general-chat**\n"
                        "🎭 Grab your roles in **#roles**\n\n"
                        "*May your aim be true and your builds be fast!* 🏗️"
                    ),
                    "color": PURPLE_MID,
                },
            },
            {
                "name": "📣・announcements",
                "topic": "Official server & Fortnite announcements.",
                "readonly": True,
            },
            {
                "name": "🎭・roles",
                "topic": "Pick your platform & rank roles here!",
                "readonly": True,
                "embed": {
                    "title": "🎭  SELF-ROLES",
                    "description": (
                        "**🖥️ Platform**\n"
                        "🖥️ → PC Player\n"
                        "🎮 → Console Player\n"
                        "📱 → Mobile Player\n\n"
                        "**🏆 Skill Rank**\n"
                        "🥉 → Bronze  |  🥈 → Silver  |  🥇 → Gold\n"
                        "💎 → Diamond  |  👑 → Champion\n\n"
                        "*Ask a staff member to assign your rank!*"
                    ),
                    "color": GOLD,
                },
            },
            {
                "name": "📊・server-stats",
                "topic": "Live server statistics.",
                "readonly": True,
                "embed": {
                    "title": "📊  SERVER STATISTICS",
                    "description": (
                        "Welcome to **⚡ Fortnite HQ**!\n\n"
                        "Use `!serverstats` to refresh these stats.\n\n"
                        "🎮 **Members:** Updating...\n"
                        "🟢 **Online:** Updating...\n"
                        "🏆 **Top Rank:** Updating...\n"
                        "📅 **Server Created:** Updating..."
                    ),
                    "color": CYAN_INFO,
                },
            },
        ],
    },
    {
        "name": "💬 | GENERAL",
        "private": False,
        "channels": [
            {"name": "🗣️・general-chat",    "topic": "Talk about anything Fortnite or gaming!"},
            {"name": "🔥・memes-and-clips", "topic": "Drop your best clips, montages and memes."},
            {"name": "📸・screenshots",     "topic": "Show off your best moments and skins."},
            {"name": "🤣・off-topic",       "topic": "Anything goes (within the rules)."},
            {"name": "🤖・bot-commands",    "topic": "Use bot commands here only – keep the other channels clean!"},
            {"name": "💡・suggestions",     "topic": "Got ideas? Share them here for staff to review."},
            {"name": "🐛・bug-reports",     "topic": "Report server bugs or bot issues here."},
        ],
    },
    {
        "name": "🎮 | FORTNITE",
        "private": False,
        "channels": [
            {"name": "🗺️・battle-royale",    "topic": "Strategy and tips for BR mode."},
            {"name": "🏗️・zero-build",       "topic": "Zero Build strategies and tips."},
            {"name": "🎯・ranked-talk",       "topic": "Ranked mode discussion and progress."},
            {
                "name": "🛒・item-shop",
                "topic": "Daily item shop discussion.",
                "embed": {
                    "title": "🛒  ITEM SHOP CHANNEL",
                    "description": (
                        "Post today's item shop here!\n\n"
                        "**Use this format:**\n"
                        "```\n📅 Date:\n💎 Featured Items:\n🔵 Daily Items:\n💵 Best Value:\n⭐ Rating: /10\n```"
                    ),
                    "color": PURPLE_LIGHT,
                },
            },
            {"name": "🗞️・patch-notes",      "topic": "Official Fortnite patch notes & discussion.", "readonly": True},
            {"name": "🗓️・tournaments",       "topic": "Community & official tournament announcements."},
            {"name": "📊・stats-and-tracker", "topic": "Share your stats! Use !stats <username>"},
            {"name": "💡・tips-and-tricks",   "topic": "Best tips, combos and build techniques."},
            {"name": "🗣️・meta-discussion",   "topic": "Discuss the current meta, weapons and loadouts."},
        ],
    },
    {
        "name": "🤝 | FIND SQUAD",
        "private": False,
        "channels": [
            {
                "name": "🔍・looking-for-squad",
                "topic": "Find squadmates! Mention platform, mode and rank.",
                "embed": {
                    "title": "🔍  LOOKING FOR SQUAD",
                    "description": (
                        "Use this template to find squadmates:\n\n"
                        "```\n🎮 Platform:\n🗺️ Mode: (BR / Zero Build / Ranked)\n"
                        "👑 Rank:\n🌍 Region:\n🕐 Available:\n📝 Notes:\n```"
                    ),
                    "color": RED_ERR,
                },
            },
            {"name": "🤝・1v1-challenges", "topic": "Challenge others to 1v1s and box fights."},
            {"name": "🏆・scrims",         "topic": "Organised scrim announcements and sign-ups."},
            {
                "name": "🎓・coaching",
                "topic": "Offer or request coaching. Help the community improve!",
                "embed": {
                    "title": "🎓  COACHING CHANNEL",
                    "description": (
                        "Looking for a coach or offering coaching?\n\n"
                        "```\n📌 Type: [Looking for Coach / Offering Coaching]\n"
                        "👑 Your Rank:\n🎯 Focus: (aim / builds / game sense / rotation)\n"
                        "🕐 Availability:\n💬 Contact:\n```"
                    ),
                    "color": PURPLE_DARK,
                },
            },
        ],
    },
    {
        "name": "🏆 | COMPETITIVE",
        "private": False,
        "channels": [
            {
                "name": "📊・leaderboard",
                "topic": "Community leaderboard – updated weekly.",
                "readonly": True,
                "embed": {
                    "title": "🏆  COMMUNITY LEADERBOARD",
                    "description": (
                        "Rankings updated every **Sunday at 8 PM CET**.\n\n"
                        "```\n🥇  #1 —  ???\n🥈  #2 —  ???\n🥉  #3 —  ???\n```\n\n"
                        "Submit your stats in **#stats-and-tracker** to get on the board!"
                    ),
                    "color": GOLD,
                },
            },
            {"name": "🎯・win-counter",  "topic": "Post your W's! Include screenshot proof."},
            {"name": "🏅・hall-of-fame", "topic": "Greatest moments from our community.", "readonly": True},
            {"name": "🎲・challenges",   "topic": "Weekly community challenges – can you complete them?"},
        ],
    },
    {
        "name": "🎨 | CREATIVE",
        "private": False,
        "channels": [
            {
                "name": "🗺️・map-showcase",
                "topic": "Share Creative Mode maps with codes!",
                "embed": {
                    "title": "🗺️  MAP SHOWCASE FORMAT",
                    "description": (
                        "Share your creative maps here:\n\n"
                        "```\n🗺️ Map Name:\n📌 Island Code:\n🎮 Type:\n"
                        "📝 Description:\n📸 Screenshot:\n⭐ Recommended Players:\n```"
                    ),
                    "color": GREEN_OK,
                },
            },
            {"name": "🎭・skin-combos",  "topic": "Show off the best skin combinations."},
            {"name": "🖼️・fan-art",      "topic": "Share your Fortnite fan art and creations!"},
        ],
    },
    {
        "name": "🎁 | EVENTS",
        "private": False,
        "channels": [
            {"name": "🎁・giveaways",    "topic": "V-Bucks and skin giveaways!", "readonly": True},
            {"name": "🗓️・events",       "topic": "Upcoming community events and tournaments.", "readonly": True},
            {"name": "🎉・event-chat",   "topic": "Chat during events and tournaments."},
        ],
    },
    {
        "name": "🔊 | MAIN LOBBY",
        "private": False,
        "voice": True,
        "channels": [
            {"name": "🏠  Main Lobby",   "limit": 0, "type": "static"},
            {"name": "🎵  Music Bot",    "limit": 0, "type": "static"},
            {"name": "😴  AFK",          "limit": 0, "type": "static", "afk": True},
        ],
    },
    {
        "name": "🎮 | CREATE YOUR LOBBY",
        "private": False,
        "voice": True,
        "channels": [
            {"name": "➕  Solo  (Join to Create)",  "limit": 1, "type": "creator", "label": "🎯 Solo"},
            {"name": "➕  Duos  (Join to Create)",  "limit": 2, "type": "creator", "label": "🤝 Duos"},
            {"name": "➕  Trios  (Join to Create)", "limit": 3, "type": "creator", "label": "🔥 Trios"},
            {"name": "➕  Squad  (Join to Create)", "limit": 4, "type": "creator", "label": "🛡️ Squad"},
        ],
    },
    {
        "name": "🏆 | RANKED & SPECIAL",
        "private": False,
        "voice": True,
        "channels": [
            {"name": "➕  Ranked Solo  (Join to Create)",     "limit": 1, "type": "creator", "label": "🏆 Ranked Solo"},
            {"name": "➕  Ranked Duos  (Join to Create)",     "limit": 2, "type": "creator", "label": "🏆 Ranked Duos"},
            {"name": "➕  Ranked Trios  (Join to Create)",    "limit": 3, "type": "creator", "label": "🏆 Ranked Trios"},
            {"name": "➕  Solo w/ Coach  (Join to Create)",   "limit": 2, "type": "creator", "label": "🎓 Solo + Coach"},
            {"name": "➕  Scrim Room  (Join to Create)",      "limit": 0, "type": "creator", "label": "⚔️ Scrim Room"},
            {"name": "➕  Tournament Prep  (Join to Create)", "limit": 4, "type": "creator", "label": "🎯 Tournament Prep"},
        ],
    },
    {
        "name": "😎 | CHILL ZONE",
        "private": False,
        "voice": True,
        "channels": [
            {"name": "➕  Chill  (Join to Create)",        "limit": 0, "type": "creator", "label": "😎 Chill"},
            {"name": "➕  Watchparty  (Join to Create)",   "limit": 0, "type": "creator", "label": "📺 Watchparty"},
            {"name": "➕  Private Room  (Join to Create)", "limit": 0, "type": "creator", "label": "🔒 Private"},
        ],
    },
    {
        "name": "🛡️ | STAFF",
        "private": True,
        "channels": [
            {"name": "🛡️・staff-chat",     "topic": "Internal staff discussion."},
            {"name": "📋・moderation-log",  "topic": "Auto-mod and manual action logs.", "readonly": True},
            {"name": "🚨・reports",         "topic": "User reports forwarded here."},
            {"name": "📝・staff-notes",     "topic": "Staff notes and decisions."},
        ],
        "voice": False,
    },
]


# ─────────────────────────────────────────────
#  HELPER: RATE-LIMIT-SAFE API CALLS
#  FIX: Added proper exception handling + correct kwarg passing
# ─────────────────────────────────────────────
async def safe_create_text_channel(guild: discord.Guild, **kwargs):
    # Remove None values so discord.py doesn't reject them
    kwargs = {k: v for k, v in kwargs.items() if v is not None}
    for attempt in range(5):
        try:
            ch = await guild.create_text_channel(**kwargs)
            await asyncio.sleep(0.7)
            return ch
        except discord.HTTPException as e:
            if e.status == 429:
                retry_after = float(e.response.headers.get("Retry-After", 5))
                await asyncio.sleep(retry_after + 1)
            elif e.status in (500, 502, 503):
                await asyncio.sleep(3 * (attempt + 1))
            else:
                raise
    return None


async def safe_create_voice_channel(guild: discord.Guild, **kwargs):
    kwargs = {k: v for k, v in kwargs.items() if v is not None}
    for attempt in range(5):
        try:
            vc = await guild.create_voice_channel(**kwargs)
            await asyncio.sleep(0.7)
            return vc
        except discord.HTTPException as e:
            if e.status == 429:
                retry_after = float(e.response.headers.get("Retry-After", 5))
                await asyncio.sleep(retry_after + 1)
            elif e.status in (500, 502, 503):
                await asyncio.sleep(3 * (attempt + 1))
            else:
                raise
    return None


async def safe_create_category(guild: discord.Guild, **kwargs):
    kwargs = {k: v for k, v in kwargs.items() if v is not None}
    for attempt in range(5):
        try:
            cat = await guild.create_category(**kwargs)
            await asyncio.sleep(0.9)
            return cat
        except discord.HTTPException as e:
            if e.status == 429:
                retry_after = float(e.response.headers.get("Retry-After", 5))
                await asyncio.sleep(retry_after + 1)
            elif e.status in (500, 502, 503):
                await asyncio.sleep(3 * (attempt + 1))
            else:
                raise
    return None


# ─────────────────────────────────────────────
#  MOD LOG HELPER
# ─────────────────────────────────────────────
async def send_mod_log(guild: discord.Guild, embed: discord.Embed):
    """Send an embed to the moderation-log channel."""
    log_ch = discord.utils.get(guild.text_channels, name="📋・moderation-log")
    if log_ch:
        try:
            await log_ch.send(embed=embed)
        except Exception:
            pass


# ─────────────────────────────────────────────
#  SETUP FUNCTION
# ─────────────────────────────────────────────
async def setup_server(guild: discord.Guild, log_channel: discord.TextChannel | None = None):
    async def log(msg: str):
        print(msg)
        if log_channel:
            try:
                await log_channel.send(f"```\n{msg}\n```")
            except Exception:
                pass

    await log("🚀 Starting Fortnite HQ Server Setup...")

    # 1. DELETE ALL CHANNELS
    await log("🗑️  Deleting all existing channels...")
    deleted = 0
    for ch in list(guild.channels):
        if ch == log_channel:
            continue
        try:
            await ch.delete(reason="Server reset")
            deleted += 1
            await asyncio.sleep(0.5)
        except Exception:
            pass
    await log(f"✅ Deleted {deleted} channel(s).")

    # 2. DELETE OLD ROLES
    await log("🗑️  Cleaning up old roles...")
    removed = 0
    for role in list(guild.roles):
        if role.managed or role.name == "@everyone":
            continue
        if role.position >= guild.me.top_role.position:
            continue
        try:
            await role.delete(reason="Server reset")
            removed += 1
            await asyncio.sleep(0.4)
        except Exception:
            pass
    await log(f"✅ Removed {removed} old role(s).")

    # 3. CREATE ROLES
    await log("🎭  Creating roles...")
    created_roles: dict[str, discord.Role] = {}
    for r in ROLES:
        try:
            role = await guild.create_role(
                name=r["name"],
                color=r["color"],
                hoist=r["hoist"],
                mentionable=False,
                reason="Fortnite server setup",
            )
            created_roles[r["name"]] = role
            await log(f"  ✔ Role: {r['name']}")
            await asyncio.sleep(0.4)
        except Exception as e:
            await log(f"  ✘ Failed role '{r['name']}': {e}")

    staff_role = created_roles.get("🛡️ Moderator") or created_roles.get("⚙️ Admin")
    muted_role = created_roles.get("🔇 Muted")

    # 4. CREATE CATEGORIES & CHANNELS
    await log("📁  Creating categories and channels...")
    global voice_creators
    voice_creators = {}

    for cat_def in CATEGORIES:
        is_voice_cat = cat_def.get("voice", False)
        is_private   = cat_def.get("private", False)

        cat_overwrites: dict = {}
        if is_private:
            cat_overwrites[guild.default_role] = discord.PermissionOverwrite(view_channel=False)
            if staff_role:
                cat_overwrites[staff_role] = discord.PermissionOverwrite(view_channel=True)

        category = await safe_create_category(
            guild,
            name=cat_def["name"],
            overwrites=cat_overwrites if cat_overwrites else None,
            reason="Fortnite server setup",
        )
        if not category:
            await log(f"  ✘ Failed to create category: {cat_def['name']}")
            continue
        await log(f"  📁 Category: {cat_def['name']}")

        for ch_def in cat_def.get("channels", []):
            ch_type = ch_def.get("type", "text")

            # ── VOICE CHANNEL ──────────────────────────────────────
            if is_voice_cat:
                limit = ch_def.get("limit", 0)
                vc = await safe_create_voice_channel(
                    guild,
                    name=ch_def["name"],
                    category=category,
                    user_limit=limit,
                    reason="Fortnite server setup",
                )
                if vc:
                    await log(f"    🔊 {ch_def['name']}")
                    if ch_type == "creator":
                        voice_creators[vc.id] = {
                            "label": ch_def.get("label", ch_def["name"]),
                            "limit": limit,
                            "category_id": category.id,
                        }
                    if ch_def.get("afk"):
                        try:
                            await guild.edit(afk_channel=vc, afk_timeout=300)
                        except Exception:
                            pass

            # ── TEXT CHANNEL ───────────────────────────────────────
            else:
                ch_overwrites: dict = {}

                # Muted role: deny send_messages everywhere
                if muted_role:
                    ch_overwrites[muted_role] = discord.PermissionOverwrite(
                        send_messages=False,
                        add_reactions=False,
                        create_public_threads=False,
                        create_private_threads=False,
                    )

                if is_private:
                    ch_overwrites[guild.default_role] = discord.PermissionOverwrite(view_channel=False)
                    if staff_role:
                        ch_overwrites[staff_role] = discord.PermissionOverwrite(view_channel=True)
                elif ch_def.get("readonly"):
                    ch_overwrites[guild.default_role] = discord.PermissionOverwrite(send_messages=False)

                channel = await safe_create_text_channel(
                    guild,
                    name=ch_def["name"],
                    category=category,
                    topic=ch_def.get("topic"),
                    overwrites=ch_overwrites if ch_overwrites else None,
                    reason="Fortnite server setup",
                )
                if channel:
                    await log(f"    💬 {ch_def['name']}")
                    if "embed" in ch_def:
                        e = ch_def["embed"]
                        embed = discord.Embed(
                            title=e.get("title"),
                            description=e.get("description"),
                            color=e.get("color", PURPLE_MID),
                        )
                        footer_text = e.get("footer", "")
                        embed.set_footer(
                            text=f"⚡ Fortnite HQ  •  {footer_text}".rstrip(" •")
                        )
                        try:
                            await channel.send(embed=embed)
                            await asyncio.sleep(0.4)
                        except Exception as err:
                            await log(f"    ⚠️ Embed failed: {err}")

    # 5. RENAME SERVER
    try:
        await guild.edit(name="⚡ Fortnite HQ")
        await log('✅ Server renamed to "⚡ Fortnite HQ"')
    except Exception:
        await log("⚠️  Could not rename server (no permission).")

    # 6. SYNC SLASH COMMANDS
    try:
        await bot.tree.sync(guild=guild)
        await log("✅ Slash commands synced.")
    except Exception as e:
        await log(f"⚠️  Slash command sync failed: {e}")

    await log("\n🎉 SETUP COMPLETE! Your Fortnite HQ is ready. Drop in! 🪂⚡")


# ─────────────────────────────────────────────
#  AUTO VOICE: JOIN → CREATE / LEAVE → DELETE
# ─────────────────────────────────────────────
@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    guild = member.guild

    # ── Joined a "Join to Create" channel ─────────────────────────
    if after.channel and after.channel.id in voice_creators:
        config   = voice_creators[after.channel.id]
        label    = config["label"]
        limit    = config["limit"]
        category = guild.get_channel(config["category_id"])

        new_vc = await guild.create_voice_channel(
            name=f"{label} ◈ {member.display_name}",
            category=category,
            user_limit=limit,
            reason=f"Auto-created for {member}",
        )

        await new_vc.set_permissions(
            member,
            manage_channels=True,
            move_members=True,
            mute_members=True,
            deafen_members=True,
        )

        try:
            await member.move_to(new_vc)
        except Exception:
            pass

        temp_voice_channels[new_vc.id] = member.id

        try:
            embed = discord.Embed(
                title="🎮 Your lobby was created!",
                description=(
                    f"**{new_vc.name}** is ready.\n\n"
                    "You have full control over your channel.\n"
                    "It will be deleted automatically when everyone leaves."
                ),
                color=PURPLE_NEON,
            )
            await member.send(embed=embed)
        except Exception:
            pass

    # ── Left a temp channel → delete if empty ─────────────────────
    if before.channel and before.channel.id in temp_voice_channels:
        channel = before.channel
        if len(channel.members) == 0:
            try:
                await channel.delete(reason="Auto-delete: empty temp channel")
                del temp_voice_channels[channel.id]
            except Exception:
                pass


# ─────────────────────────────────────────────
#  AUTO ROLE ON JOIN
# ─────────────────────────────────────────────
@bot.event
async def on_member_join(member: discord.Member):
    guild = member.guild
    member_role = discord.utils.get(guild.roles, name="🎮 Member")
    if member_role:
        try:
            await member.add_roles(member_role, reason="Auto-assigned on join")
        except Exception:
            pass

    try:
        embed = discord.Embed(
            title="⚡ Welcome to Fortnite HQ!",
            description=(
                f"Hey **{member.display_name}**! 🪂\n\n"
                "You've just joined the best Fortnite community!\n\n"
                "**Get started:**\n"
                "📋 Read the rules\n"
                "🎭 Pick your roles\n"
                "🔍 Find your squad\n\n"
                "*Good luck on the bus!* 🎮"
            ),
            color=PURPLE_MID,
        )
        embed.set_footer(text="⚡ Fortnite HQ")
        await member.send(embed=embed)
    except Exception:
        pass


# ─────────────────────────────────────────────
#  MUTE SYSTEM
# ─────────────────────────────────────────────
async def _unmute_after(guild: discord.Guild, member: discord.Member, seconds: int, mod: discord.Member, reason: str):
    """Background task: remove Muted role after timeout and log it."""
    await asyncio.sleep(seconds)
    muted_role = discord.utils.get(guild.roles, name="🔇 Muted")
    if muted_role and muted_role in member.roles:
        try:
            await member.remove_roles(muted_role, reason="Mute expired")
        except Exception:
            pass

    key = (guild.id, member.id)
    active_mutes.pop(key, None)

    # Log unmute
    embed = discord.Embed(
        title="🔊 Member Unmuted (Timer)",
        color=GREEN_OK,
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name="👤 User",      value=f"{member.mention} (`{member}`)", inline=True)
    embed.add_field(name="🛡️ Muted by",  value=f"{mod.mention}",                  inline=True)
    embed.add_field(name="⏱️ Duration",  value=f"{seconds}s",                     inline=True)
    embed.add_field(name="📝 Reason",    value=reason or "No reason given",        inline=False)
    embed.set_footer(text=f"User ID: {member.id}")
    await send_mod_log(guild, embed)


@bot.command(name="mute")
@commands.has_permissions(manage_messages=True)
async def cmd_mute(ctx: commands.Context, member: discord.Member, duration: str = "10m", *, reason: str = "No reason given"):
    """
    Mute a member for a given duration.
    Duration format: 30s / 5m / 2h / 1d
    Example: !mute @user 10m Spamming
    """
    # Parse duration
    unit_map = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    try:
        unit = duration[-1].lower()
        amount = int(duration[:-1])
        seconds = amount * unit_map[unit]
    except (ValueError, KeyError):
        await ctx.send("❌ Invalid duration format. Use: `30s`, `5m`, `2h`, `1d`")
        return

    if seconds < 10 or seconds > 86400 * 28:
        await ctx.send("❌ Duration must be between 10 seconds and 28 days.")
        return

    muted_role = discord.utils.get(ctx.guild.roles, name="🔇 Muted")
    if not muted_role:
        await ctx.send("❌ Muted role not found. Run `!setup` first.")
        return

    if muted_role in member.roles:
        await ctx.send(f"⚠️ {member.mention} is already muted.")
        return

    try:
        await member.add_roles(muted_role, reason=f"Muted by {ctx.author}: {reason}")
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to mute this user.")
        return

    # Cancel existing timer if any
    key = (ctx.guild.id, member.id)
    if key in active_mutes:
        active_mutes[key].cancel()

    # Schedule unmute
    task = asyncio.create_task(_unmute_after(ctx.guild, member, seconds, ctx.author, reason))
    active_mutes[key] = task

    # Friendly duration string
    if seconds < 60:
        dur_str = f"{seconds}s"
    elif seconds < 3600:
        dur_str = f"{seconds // 60}m"
    elif seconds < 86400:
        dur_str = f"{seconds // 3600}h {(seconds % 3600) // 60}m"
    else:
        dur_str = f"{seconds // 86400}d"

    expires_at = datetime.now(timezone.utc) + timedelta(seconds=seconds)

    embed = discord.Embed(
        title="🔇 Member Muted",
        color=RED_ERR,
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name="👤 User",       value=f"{member.mention} (`{member}`)", inline=True)
    embed.add_field(name="🛡️ Moderator",  value=ctx.author.mention,               inline=True)
    embed.add_field(name="⏱️ Duration",   value=dur_str,                           inline=True)
    embed.add_field(name="🕐 Expires",    value=f"<t:{int(expires_at.timestamp())}:R>", inline=True)
    embed.add_field(name="📝 Reason",     value=reason,                            inline=False)
    embed.set_footer(text=f"User ID: {member.id}")

    await ctx.send(embed=embed)
    await send_mod_log(ctx.guild, embed)

    # Notify muted user
    try:
        dm_embed = discord.Embed(
            title="🔇 You have been muted",
            description=(
                f"You were muted in **{ctx.guild.name}**.\n\n"
                f"**Duration:** {dur_str}\n"
                f"**Reason:** {reason}\n"
                f"**Expires:** <t:{int(expires_at.timestamp())}:R>"
            ),
            color=RED_ERR,
        )
        await member.send(embed=dm_embed)
    except Exception:
        pass


@bot.command(name="unmute")
@commands.has_permissions(manage_messages=True)
async def cmd_unmute(ctx: commands.Context, member: discord.Member, *, reason: str = "Manual unmute"):
    muted_role = discord.utils.get(ctx.guild.roles, name="🔇 Muted")
    if not muted_role:
        await ctx.send("❌ Muted role not found.")
        return

    if muted_role not in member.roles:
        await ctx.send(f"⚠️ {member.mention} is not muted.")
        return

    # Cancel timer
    key = (ctx.guild.id, member.id)
    if key in active_mutes:
        active_mutes[key].cancel()
        del active_mutes[key]

    try:
        await member.remove_roles(muted_role, reason=f"Unmuted by {ctx.author}: {reason}")
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to unmute this user.")
        return

    embed = discord.Embed(
        title="🔊 Member Unmuted",
        color=GREEN_OK,
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name="👤 User",      value=f"{member.mention} (`{member}`)", inline=True)
    embed.add_field(name="🛡️ Moderator", value=ctx.author.mention,               inline=True)
    embed.add_field(name="📝 Reason",    value=reason,                            inline=False)
    embed.set_footer(text=f"User ID: {member.id}")

    await ctx.send(embed=embed)
    await send_mod_log(ctx.guild, embed)


@bot.command(name="muteinfo")
@commands.has_permissions(manage_messages=True)
async def cmd_muteinfo(ctx: commands.Context, member: discord.Member):
    """Show active mute info for a user."""
    muted_role = discord.utils.get(ctx.guild.roles, name="🔇 Muted")
    is_muted = muted_role and muted_role in member.roles
    key = (ctx.guild.id, member.id)
    has_timer = key in active_mutes

    if not is_muted:
        await ctx.send(f"✅ {member.mention} is **not muted**.")
        return

    embed = discord.Embed(
        title="🔇 Active Mute Info",
        color=RED_ERR,
    )
    embed.add_field(name="👤 User",     value=f"{member.mention} (`{member}`)", inline=True)
    embed.add_field(name="⏱️ Timer",    value="Active" if has_timer else "No timer (permanent)", inline=True)
    embed.set_footer(text=f"User ID: {member.id}")
    await ctx.send(embed=embed)


# ─────────────────────────────────────────────
#  SLASH COMMAND: /teams  (Voice Team Splitter)
# ─────────────────────────────────────────────
@bot.tree.command(name="teams", description="Split everyone in your voice channel into Team A and Team B randomly!")
@app_commands.describe(
    move="Move players into separate voice channels? (requires 'Move Members' permission)",
)
async def slash_teams(interaction: discord.Interaction, move: bool = False):
    """Randomly splits voice channel members into two teams."""
    member = interaction.user
    if not isinstance(member, discord.Member):
        await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
        return

    vc = member.voice.channel if member.voice else None
    if not vc:
        await interaction.response.send_message(
            "❌ You need to be in a voice channel to use this command!", ephemeral=True
        )
        return

    members_in_vc = [m for m in vc.members if not m.bot]
    if len(members_in_vc) < 2:
        await interaction.response.send_message(
            "❌ Need at least **2 people** in the voice channel to split into teams.", ephemeral=True
        )
        return

    random.shuffle(members_in_vc)
    mid = len(members_in_vc) // 2
    team_a = members_in_vc[:mid + (len(members_in_vc) % 2)]  # larger half if odd
    team_b = members_in_vc[mid + (len(members_in_vc) % 2):]

    def fmt_team(team_list):
        return "\n".join(f"• {m.mention}" for m in team_list) or "—"

    embed = discord.Embed(
        title="⚔️ Teams Generated!",
        description=f"**Voice Channel:** {vc.mention} — **{len(members_in_vc)} players**",
        color=PURPLE_NEON,
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name=f"🔵 Team A  ({len(team_a)})", value=fmt_team(team_a), inline=True)
    embed.add_field(name=f"🔴 Team B  ({len(team_b)})", value=fmt_team(team_b), inline=True)
    embed.set_footer(text=f"Split by {member.display_name}")

    # If move=True, try to move players into separate temp channels
    if move:
        guild = interaction.guild
        category = vc.category

        # Check permissions
        if not interaction.channel.permissions_for(guild.me).move_members:
            embed.add_field(
                name="⚠️ Move failed",
                value="I need **Move Members** permission to move players.",
                inline=False,
            )
            await interaction.response.send_message(embed=embed)
            return

        await interaction.response.defer()

        try:
            vc_a = await guild.create_voice_channel(
                name="🔵 Team A",
                category=category,
                user_limit=len(team_a),
                reason=f"Teams split by {member}",
            )
            vc_b = await guild.create_voice_channel(
                name="🔴 Team B",
                category=category,
                user_limit=len(team_b),
                reason=f"Teams split by {member}",
            )

            # Register as temp channels so they auto-delete when empty
            temp_voice_channels[vc_a.id] = member.id
            temp_voice_channels[vc_b.id] = member.id

            errors = []
            for m in team_a:
                try:
                    await m.move_to(vc_a)
                    await asyncio.sleep(0.3)
                except Exception:
                    errors.append(m.display_name)

            for m in team_b:
                try:
                    await m.move_to(vc_b)
                    await asyncio.sleep(0.3)
                except Exception:
                    errors.append(m.display_name)

            embed.add_field(
                name="✅ Players moved!",
                value=(
                    f"🔵 → {vc_a.mention}\n"
                    f"🔴 → {vc_b.mention}\n"
                    f"*(channels auto-delete when empty)*"
                    + (f"\n⚠️ Could not move: {', '.join(errors)}" if errors else "")
                ),
                inline=False,
            )
        except Exception as e:
            embed.add_field(name="❌ Error creating channels", value=str(e), inline=False)

        await interaction.followup.send(embed=embed)
    else:
        await interaction.response.send_message(embed=embed)


# ─────────────────────────────────────────────
#  PREFIX COMMANDS
# ─────────────────────────────────────────────

@bot.command(name="setup")
@commands.has_permissions(administrator=True)
async def cmd_setup(ctx: commands.Context):
    embed = discord.Embed(
        title="⚠️  CONFIRM SERVER RESET",
        description=(
            "This will **DELETE ALL CHANNELS** and **RECREATE** the entire server "
            "as a Fortnite Gaming Server.\n\n"
            "Type `CONFIRM` within **30 seconds** to proceed.\n"
            "Type anything else or wait to cancel."
        ),
        color=RED_ERR,
    )
    embed.set_footer(text="⚠️ This action is irreversible!")
    await ctx.send(embed=embed)

    def check(m: discord.Message):
        return m.author == ctx.author and m.channel == ctx.channel

    try:
        msg = await bot.wait_for("message", timeout=30.0, check=check)
    except asyncio.TimeoutError:
        await ctx.send("❌ Setup cancelled (timed out).")
        return

    if msg.content.strip() != "CONFIRM":
        await ctx.send("❌ Setup cancelled.")
        return

    log_channel = None
    try:
        log_channel = await ctx.guild.create_text_channel(
            name="⚙️-setup-log",
            reason="Temporary setup log",
        )
        await log_channel.send("```\n🔧 Fortnite HQ Setup Starting...\n```")
    except Exception:
        pass

    await setup_server(ctx.guild, log_channel)

    if log_channel:
        await asyncio.sleep(30)
        try:
            await log_channel.delete()
        except Exception:
            pass


@bot.command(name="help")
async def cmd_help(ctx: commands.Context):
    embed = discord.Embed(
        title="⚡ Fortnite HQ – Bot Commands",
        color=PURPLE_NEON,
    )
    embed.add_field(
        name="⚙️ Admin",
        value=(
            "`!setup` — Wipes & rebuilds the entire server\n"
            "`!serverstats` — Post updated server statistics"
        ),
        inline=False,
    )
    embed.add_field(
        name="🔇 Moderation",
        value=(
            "`!mute @user <duration> [reason]` — Mute a user\n"
            "   Duration: `30s` / `5m` / `2h` / `1d`\n"
            "`!unmute @user [reason]` — Remove mute\n"
            "`!muteinfo @user` — Check mute status\n"
            "All actions are logged in `#moderation-log`"
        ),
        inline=False,
    )
    embed.add_field(
        name="🎮 General",
        value=(
            "`!ping` — Check bot latency\n"
            "`!roll` — Roll a random number (1-100)\n"
            "`!flip` — Flip a coin\n"
            "`!8ball <question>` — Ask the magic 8-ball\n"
            "`!userinfo [@user]` — Show info about a user\n"
            "`!serverinfo` — Show server information"
        ),
        inline=False,
    )
    embed.add_field(
        name="⚔️ Slash Commands",
        value=(
            "`/teams` — Randomly split your voice channel into Team A & B\n"
            "   `move: True` → also moves players into separate channels"
        ),
        inline=False,
    )
    embed.add_field(
        name="🔊 Voice",
        value=(
            "Join any **➕ (Join to Create)** channel and the bot will\n"
            "instantly create a private lobby just for you.\n"
            "The channel auto-deletes when everyone leaves."
        ),
        inline=False,
    )
    embed.set_footer(text="⚡ Fortnite HQ  •  ⚠️ !setup is irreversible!")
    await ctx.send(embed=embed)


@bot.command(name="ping")
async def cmd_ping(ctx: commands.Context):
    latency = round(bot.latency * 1000)
    color = GREEN_OK if latency < 100 else (GOLD if latency < 200 else RED_ERR)
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"Bot latency: **{latency}ms**",
        color=color,
    )
    await ctx.send(embed=embed)


@bot.command(name="roll")
async def cmd_roll(ctx: commands.Context, maximum: int = 100):
    result = random.randint(1, max(1, maximum))
    embed = discord.Embed(
        title="🎲 Dice Roll",
        description=f"{ctx.author.mention} rolled **{result}** out of {maximum}!",
        color=PURPLE_LIGHT,
    )
    await ctx.send(embed=embed)


@bot.command(name="flip")
async def cmd_flip(ctx: commands.Context):
    result = random.choice(["Heads 🪙", "Tails 🔵"])
    embed = discord.Embed(
        title="🪙 Coin Flip",
        description=f"{ctx.author.mention} flipped: **{result}**",
        color=PURPLE_MID,
    )
    await ctx.send(embed=embed)


@bot.command(name="8ball")
async def cmd_8ball(ctx: commands.Context, *, question: str = ""):
    if not question:
        await ctx.send("❓ Please ask a question! Example: `!8ball Will I win this match?`")
        return
    responses = [
        "🟢 It is certain.",
        "🟢 Without a doubt.",
        "🟢 Yes, definitely!",
        "🟢 Most likely.",
        "🟡 Ask again later.",
        "🟡 Cannot predict now.",
        "🟡 Don't count on it.",
        "🔴 Very doubtful.",
        "🔴 My sources say no.",
        "🔴 Outlook not so good.",
    ]
    embed = discord.Embed(title="🎱 Magic 8-Ball", color=PURPLE_DARK)
    embed.add_field(name="❓ Question", value=question, inline=False)
    embed.add_field(name="🎱 Answer", value=random.choice(responses), inline=False)
    embed.set_footer(text=f"Asked by {ctx.author.display_name}")
    await ctx.send(embed=embed)


@bot.command(name="userinfo")
async def cmd_userinfo(ctx: commands.Context, member: discord.Member = None):
    member = member or ctx.author
    roles = [r.mention for r in member.roles if r.name != "@everyone"]
    embed = discord.Embed(
        title=f"👤 {member.display_name}",
        color=member.color if member.color.value else PURPLE_LIGHT,
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="🆔 ID",             value=member.id,                               inline=True)
    embed.add_field(name="📅 Joined Server",  value=member.joined_at.strftime("%d %b %Y"),   inline=True)
    embed.add_field(name="📅 Account Created", value=member.created_at.strftime("%d %b %Y"), inline=True)
    embed.add_field(name=f"🎭 Roles ({len(roles)})", value=" ".join(roles) or "None",        inline=False)
    embed.set_footer(text="⚡ Fortnite HQ")
    await ctx.send(embed=embed)


@bot.command(name="serverinfo")
async def cmd_serverinfo(ctx: commands.Context):
    guild = ctx.guild
    online = sum(1 for m in guild.members if m.status != discord.Status.offline) if guild.members else "?"
    embed = discord.Embed(title=f"⚡ {guild.name}", color=PURPLE_NEON)
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.add_field(name="👑 Owner",          value=guild.owner.mention if guild.owner else "?", inline=True)
    embed.add_field(name="👥 Members",        value=guild.member_count,                          inline=True)
    embed.add_field(name="🟢 Online",         value=online,                                      inline=True)
    embed.add_field(name="💬 Channels",       value=len(guild.text_channels),                    inline=True)
    embed.add_field(name="🔊 Voice Channels", value=len(guild.voice_channels),                   inline=True)
    embed.add_field(name="🎭 Roles",          value=len(guild.roles),                            inline=True)
    embed.add_field(name="📅 Created",        value=guild.created_at.strftime("%d %b %Y"),       inline=True)
    embed.set_footer(text="⚡ Fortnite HQ")
    await ctx.send(embed=embed)


@bot.command(name="serverstats")
@commands.has_permissions(administrator=True)
async def cmd_serverstats(ctx: commands.Context):
    guild = ctx.guild
    stats_ch = discord.utils.get(guild.text_channels, name="📊・server-stats")
    if not stats_ch:
        await ctx.send("❌ Could not find **#📊・server-stats** channel.")
        return

    online = sum(1 for m in guild.members if m.status != discord.Status.offline) if guild.members else "?"
    embed = discord.Embed(
        title="📊  SERVER STATISTICS",
        description=f"Live stats for **{guild.name}**",
        color=CYAN_INFO,
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name="👥 Total Members",  value=guild.member_count,         inline=True)
    embed.add_field(name="🟢 Online",         value=online,                      inline=True)
    embed.add_field(name="💬 Text Channels",  value=len(guild.text_channels),    inline=True)
    embed.add_field(name="🔊 Voice Channels", value=len(guild.voice_channels),   inline=True)
    embed.set_footer(text="⚡ Fortnite HQ  •  Updated")

    try:
        await stats_ch.purge(limit=10)
        await stats_ch.send(embed=embed)
        await ctx.send(f"✅ Server stats updated in {stats_ch.mention}!", delete_after=5)
    except Exception as e:
        await ctx.send(f"❌ Failed to update stats: {e}")


# ─────────────────────────────────────────────
#  ERROR HANDLERS
# ─────────────────────────────────────────────
@cmd_setup.error
async def setup_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You need **Administrator** permission to run `!setup`.")

@cmd_serverstats.error
async def serverstats_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You need **Administrator** permission to run `!serverstats`.")

@cmd_mute.error
async def mute_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You need **Manage Messages** permission to mute users.")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ Member not found.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Usage: `!mute @user <duration> [reason]`  — e.g. `!mute @user 10m Spamming`")

@cmd_unmute.error
async def unmute_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You need **Manage Messages** permission to unmute users.")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ Member not found.")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Missing argument. Use `!help` to see command usage.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Invalid argument. Use `!help` for help.")


# ─────────────────────────────────────────────
#  BOT READY
# ─────────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"✅  Logged in as {bot.user} ({bot.user.id})")
    print(f"📡  Connected to {len(bot.guilds)} server(s)")
    print("Commands: !setup | !help | !ping | !roll | !flip | !8ball | !mute | !unmute | /teams")

    # Sync slash commands globally on startup
    try:
        synced = await bot.tree.sync()
        print(f"✅  Synced {len(synced)} slash command(s) globally.")
    except Exception as e:
        print(f"⚠️  Slash command sync failed: {e}")

    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="⚡ Fortnite HQ | !help",
        )
    )


# ─────────────────────────────────────────────
#  LAUNCH
# ─────────────────────────────────────────────
# Store your token as environment variable:
#   Linux/Mac:  export DISCORD_TOKEN="your_token_here"
#   Windows:    set DISCORD_TOKEN=your_token_here
# Then run: python fortnite_bot.py

TOKEN = os.environ.get("DISCORD_TOKEN", "PASTE_YOUR_TOKEN_HERE")
if TOKEN == "PASTE_YOUR_TOKEN_HERE":
    print("⚠️  WARNING: Set your DISCORD_TOKEN environment variable!")
    print("   Linux/Mac:  export DISCORD_TOKEN='your_token'")
    print("   Windows:    set DISCORD_TOKEN=your_token")

bot.run(TOKEN)
