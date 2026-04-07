import discord
import random
import string
import json
import os
from datetime import datetime, timedelta

ADMIN_ID = 1370498558419140628  # DEINE ID

intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)

DB = "keys.json"

def load():
    if not os.path.exists(DB):
        return {}
    with open(DB) as f:
        return json.load(f)

def save(data):
    with open(DB, "w") as f:
        json.dump(data, f, indent=2)

def gen_key():
    part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    return f"SERGAJ-{part}"

def parse_days(arg):
    try:
        # erlaubt "30" oder "30d"
        return int(arg.replace("d", ""))
    except:
        return None

@bot.event
async def on_ready():
    print(f"Bot online: {bot.user}")

@bot.event
async def on_message(msg):
    if msg.author.bot:
        return

    if msg.author.id != ADMIN_ID:
        return  # KEINE SPAM NACHRICHTEN

    args = msg.content.strip().split()
    if not args:
        return

    cmd = args[0].lower()

    # 🔑 KEY GENERIEREN
    if cmd == "!genkey":
        days = 30

        if len(args) > 1:
            parsed = parse_days(args[1])
            if parsed is None:
                await msg.channel.send("❌ Beispiel: `!genkey 30` oder `!genkey 30d`")
                return
            days = parsed

        key = gen_key()
        db = load()

        expire = (datetime.now() + timedelta(days=days)).isoformat()
        db[key] = {"banned": False, "expires": expire}

        save(db)

        await msg.channel.send(
            f"✅ Key erstellt:\n`{key}`\n📅 Gültig: **{days} Tage**"
        )

    # 🔨 BAN
    elif cmd == "!bankey":
        if len(args) < 2:
            await msg.channel.send("❌ `!bankey SERGAJ-XXXX`")
            return

        key = args[1].upper()
        db = load()

        if key not in db:
            await msg.channel.send("❌ Key nicht gefunden.")
            return

        db[key]["banned"] = True
        save(db)

        await msg.channel.send(f"🔨 `{key}` gebannt.")

    # ✅ UNBAN
    elif cmd == "!unbankey":
        if len(args) < 2:
            await msg.channel.send("❌ `!unbankey SERGAJ-XXXX`")
            return

        key = args[1].upper()
        db = load()

        if key not in db:
            await msg.channel.send("❌ Key nicht gefunden.")
            return

        db[key]["banned"] = False
        save(db)

        await msg.channel.send(f"✅ `{key}` entbannt.")

    # 🔍 INFO
    elif cmd == "!keyinfo":
        if len(args) < 2:
            await msg.channel.send("❌ `!keyinfo SERGAJ-XXXX`")
            return

        key = args[1].upper()
        db = load()

        if key not in db:
            await msg.channel.send("❌ Key nicht gefunden.")
            return

        k = db[key]
        exp = datetime.fromisoformat(k["expires"])
        left = (exp - datetime.now()).days

        status = "❌ Gebannt" if k["banned"] else "✅ Aktiv"

        await msg.channel.send(
            f"🔑 `{key}`\nStatus: {status}\n⏳ Noch: **{left} Tage**"
        )

    # 📋 LISTE
    elif cmd == "!listkeys":
        db = load()

        if not db:
            await msg.channel.send("Keine Keys vorhanden.")
            return

        lines = []

        for k, v in db.items():
            left = (datetime.fromisoformat(v["expires"]) - datetime.now()).days
            icon = "❌" if v["banned"] else "✅"
            lines.append(f"{icon} `{k}` — {left}d")

        await msg.channel.send("**Keys:**\n" + "\n".join(lines))

    # 🗑️ DELETE
    elif cmd == "!delkey":
        if len(args) < 2:
            await msg.channel.send("❌ `!delkey SERGAJ-XXXX`")
            return

        key = args[1].upper()
        db = load()

        if key not in db:
            await msg.channel.send("❌ Key nicht gefunden.")
            return

        del db[key]
        save(db)

        await msg.channel.send(f"🗑️ `{key}` gelöscht.")


# 🚀 START
TOKEN = os.getenv("TOKEN")

if not TOKEN:
    print("❌ TOKEN fehlt in Railway ENV!")
else:
    bot.run(TOKEN)
