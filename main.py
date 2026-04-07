import discord
import random
import string
import json
import os
from datetime import datetime, timedelta

TOKEN = "DEIN_TOKEN_HIER"
ADMIN_ID = 123456789  # Deine Discord ID (Zahl)

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

@bot.event
async def on_ready():
    print(f"Bot online: {bot.user}")

@bot.event
async def on_message(msg):
    if msg.author.bot:
        return
    if msg.author.id != ADMIN_ID:
        await msg.channel.send("❌ Keine Berechtigung.")
        return

    args = msg.content.strip().split()
    cmd = args[0] if args else ""

    if cmd == "!genkey":
        days = int(args[1]) if len(args) > 1 else 30
        key = gen_key()
        db = load()
        expire = (datetime.now() + timedelta(days=days)).isoformat()
        db[key] = {"banned": False, "expires": expire}
        save(db)
        await msg.channel.send(f"✅ Key: `{key}`\n📅 Gültig: **{days} Tage**")

    elif cmd == "!bankey":
        if len(args) < 2:
            await msg.channel.send("❌ Syntax: `!bankey SERGAJ-XXXX`")
            return
        key = args[1]
        db = load()
        if key not in db:
            await msg.channel.send("❌ Key nicht gefunden.")
            return
        db[key]["banned"] = True
        save(db)
        await msg.channel.send(f"🔨 `{key}` gebannt.")

    elif cmd == "!unbankey":
        key = args[1] if len(args) > 1 else ""
        db = load()
        if key not in db:
            await msg.channel.send("❌ Key nicht gefunden.")
            return
        db[key]["banned"] = False
        save(db)
        await msg.channel.send(f"✅ `{key}` entbannt.")

    elif cmd == "!keyinfo":
        key = args[1] if len(args) > 1 else ""
        db = load()
        if key not in db:
            await msg.channel.send("❌ Key nicht gefunden.")
            return
        k = db[key]
        exp = datetime.fromisoformat(k["expires"])
        left = (exp - datetime.now()).days
        status = "❌ Gebannt" if k["banned"] else "✅ Aktiv"
        await msg.channel.send(f"🔑 `{key}`\nStatus: {status}\nNoch: **{left} Tage**")

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

    elif cmd == "!delkey":
        key = args[1] if len(args) > 1 else ""
        db = load()
        if key not in db:
            await msg.channel.send("❌ Key nicht gefunden.")
            return
        del db[key]
        save(db)
        await msg.channel.send(f"🗑️ `{key}` gelöscht.")

client.run(os.getenv("TOKEN"))
