import discord
import json
import os
import random
import string
from flask import Flask, request, jsonify
from threading import Thread

# -------------------
# DISCORD BOT SETUP
# -------------------

intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)

ADMIN_ID = 1370498558419140628  # 🔴 DEINE DISCORD ID EINTRAGEN
DB = "keys.json"

# -------------------
# FILE FUNKTIONEN
# -------------------

def load():
    if not os.path.exists(DB):
        return {}
    with open(DB, "r") as f:
        return json.load(f)

def save(data):
    with open(DB, "w") as f:
        json.dump(data, f, indent=2)

def gen_key():
    return "SERGAJ-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

# -------------------
# DISCORD EVENTS
# -------------------

@bot.event
async def on_ready():
    print(f"Bot online: {bot.user}")

@bot.event
async def on_message(msg):
    if msg.author.bot:
        return

    # ❌ Nur Admin darf Commands nutzen
    if msg.author.id != ADMIN_ID:
        return

    args = msg.content.split()
    if not args:
        return

    cmd = args[0]

    # 🔑 KEY GENERIEREN
    if cmd == "!genkey":
        key = gen_key()
        db = load()

        db[key] = {
            "used": False
        }

        save(db)

        await msg.channel.send(f"✅ Key erstellt:\n`{key}`")

    # 📋 LISTE
    elif cmd == "!listkeys":
        db = load()
        if not db:
            await msg.channel.send("Keine Keys vorhanden.")
            return

        text = ""
        for k, v in db.items():
            status = "❌ benutzt" if v["used"] else "✅ frei"
            text += f"{k} — {status}\n"

        await msg.channel.send(text)

    # 🗑️ KEY LÖSCHEN
    elif cmd == "!delkey":
        if len(args) < 2:
            await msg.channel.send("❌ !delkey KEY")
            return

        key = args[1]
        db = load()

        if key not in db:
            await msg.channel.send("❌ Key nicht gefunden")
            return

        del db[key]
        save(db)

        await msg.channel.send(f"🗑️ `{key}` gelöscht")

# -------------------
# FLASK API
# -------------------

app = Flask(__name__)

@app.route("/")
def home():
    return "SERGAJ API läuft"

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    key = data.get("key")

    db = load()

    # 🔥 FREE KEY (optional)
    if key == "SERGAJ-FREE":
        return jsonify({"status": "ok"})

    # 🔑 CHECK
    if key in db:
        if db[key]["used"]:
            return jsonify({"status": "used"})

        db[key]["used"] = True
        save(db)

        return jsonify({"status": "ok"})

    return jsonify({"status": "invalid"})

# -------------------
# START SERVER + BOT
# -------------------

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

Thread(target=run_flask).start()

bot.run(os.getenv("TOKEN"))
