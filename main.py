import discord
import random
import string
import json
import os
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS
import threading

# =====================
# CONFIG
# =====================
TOKEN = os.getenv("TOKEN")  # Railway Variable!
ADMIN_ID = 1370498558419140628  # DEINE DISCORD ID

DB = "keys.json"

# =====================
# DISCORD BOT
# =====================
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)

# =====================
# FLASK API
# =====================
app = Flask(__name__)
CORS(app)

# =====================
# DATABASE
# =====================
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

# =====================
# API ROUTE (WICHTIG!)
# =====================
@app.route("/validate", methods=["POST"])
def validate():
    data = request.json
    key = data.get("key")

    db = load()

    if key not in db:
        return jsonify({"valid": False})

    k = db[key]

    if k["banned"]:
        return jsonify({"valid": False})

    exp = datetime.fromisoformat(k["expires"])
    if datetime.now() > exp:
        return jsonify({"valid": False})

    return jsonify({"valid": True})

# =====================
# DISCORD EVENTS
# =====================
@bot.event
async def on_ready():
    print(f"Bot online: {bot.user}")

@bot.event
async def on_message(msg):
    if msg.author.bot:
        return

    if msg.author.id != ADMIN_ID:
        return

    args = msg.content.split()
    if not args:
        return

    cmd = args[0]

    # GEN KEY
    if cmd == "!genkey":
        try:
            days = int(args[1]) if len(args) > 1 else 30
        except:
            await msg.channel.send("❌ Zahl eingeben! Beispiel: !genkey 30")
            return

        key = gen_key()
        db = load()
        expire = (datetime.now() + timedelta(days=days)).isoformat()

        db[key] = {"banned": False, "expires": expire}
        save(db)

        await msg.channel.send(f"✅ Key: `{key}` ({days} Tage)")

    # BAN KEY
    elif cmd == "!bankey":
        if len(args) < 2:
            return await msg.channel.send("❌ !bankey KEY")

        key = args[1]
        db = load()

        if key not in db:
            return await msg.channel.send("❌ Key nicht gefunden")

        db[key]["banned"] = True
        save(db)

        await msg.channel.send(f"🔨 `{key}` gebannt")

    # UNBAN KEY
    elif cmd == "!unbankey":
        if len(args) < 2:
            return await msg.channel.send("❌ !unbankey KEY")

        key = args[1]
        db = load()

        if key not in db:
            return await msg.channel.send("❌ Key nicht gefunden")

        db[key]["banned"] = False
        save(db)

        await msg.channel.send(f"✅ `{key}` entbannt")

    # KEY INFO
    elif cmd == "!keyinfo":
        if len(args) < 2:
            return await msg.channel.send("❌ !keyinfo KEY")

        key = args[1]
        db = load()

        if key not in db:
            return await msg.channel.send("❌ Key nicht gefunden")

        k = db[key]
        exp = datetime.fromisoformat(k["expires"])
        left = (exp - datetime.now()).days

        status = "❌ Gebannt" if k["banned"] else "✅ Aktiv"

        await msg.channel.send(f"{key}\n{status}\n{left} Tage übrig")

# =====================
# START SERVER + BOT
# =====================
def run_flask():
    app.run(host="0.0.0.0", port=8080)

threading.Thread(target=run_flask).start()

bot.run(TOKEN)
