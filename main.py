import discord
import json
import os
import random
import string
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
import threading

# =========================
# CONFIG
# =========================
TOKEN = os.getenv("TOKEN")  # Discord Bot Token
ADMIN_ID = 1370498558419140628  # ⚠️ HIER DEINE DISCORD ID EINTRAGEN

DB = "keys.json"

# =========================
# DATABASE
# =========================
def load():
    try:
        with open(DB, "r") as f:
            return json.load(f)
    except:
        return {}

def save(data):
    try:
        with open(DB, "w") as f:
            json.dump(data, f, indent=2)
    except:
        pass

def gen_key():
    part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    return f"SERGAJ-{part}"

# =========================
# DISCORD BOT
# =========================
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)

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

    args = msg.content.split()

    if not args:
        return

    cmd = args[0]

    # KEY ERSTELLEN
    if cmd == "!genkey":
        days = int(args[1]) if len(args) > 1 else 30
        key = gen_key()

        db = load()
        expire = (datetime.now() + timedelta(days=days)).isoformat()

        db[key] = {
            "banned": False,
            "expires": expire,
            "used": False
        }

        save(db)

        await msg.channel.send(f"✅ Key: `{key}`\n📅 {days} Tage gültig")

    # KEY INFO
    elif cmd == "!keyinfo":
        key = args[1] if len(args) > 1 else ""
        db = load()

        if key not in db:
            await msg.channel.send("❌ Key nicht gefunden")
            return

        k = db[key]
        await msg.channel.send(f"🔑 {key}\n{str(k)}")

# =========================
# FLASK API
# =========================
app = Flask(__name__)

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    key = data.get("key", "").upper()

    print("LOGIN REQUEST:", key)

    db = load()
    print("DB:", db)

    if key not in db:
        return jsonify({"status": "error", "reason": "KEY NOT FOUND"})

    k = db[key]

    if k["banned"]:
        return jsonify({"status": "error", "reason": "BANNED"})

    if k.get("used"):
        return jsonify({"status": "error", "reason": "ALREADY USED"})

    expire = datetime.fromisoformat(k["expires"])
    if datetime.now() > expire:
        return jsonify({"status": "error", "reason": "EXPIRED"})

    # KEY ALS BENUTZT MARKIEREN
    db[key]["used"] = True
    save(db)

    return jsonify({"status": "ok"})

# =========================
# START THREADS
# =========================
def run_bot():
    bot.run(TOKEN)

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# =========================
# MAIN
# =========================
if __name__ == "__main__":
    threading.Thread(target=run_bot).start()
    run_web()
