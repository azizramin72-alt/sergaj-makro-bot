import discord
import random
import string
import json
import os
from flask import Flask, request, jsonify
from threading import Thread

# =========================
# CONFIG
# =========================
ADMIN_ID = 1370498558419140628  # DEINE DISCORD ID
DB = "keys.json"

# =========================
# DISCORD BOT
# =========================
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)

def load_keys():
    if not os.path.exists(DB):
        return {}
    with open(DB, "r") as f:
        return json.load(f)

def save_keys(data):
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

    args = msg.content.split()
    cmd = args[0]

    # KEY ERSTELLEN
    if cmd == "!genkey":
        key = gen_key()
        keys = load_keys()
        keys[key] = True
        save_keys(keys)

        await msg.channel.send(f"✅ Key erstellt:\n`{key}`")

    # KEY LÖSCHEN
    elif cmd == "!delkey":
        if len(args) < 2:
            return await msg.channel.send("❌ !delkey KEY")

        key = args[1]
        keys = load_keys()

        if key in keys:
            del keys[key]
            save_keys(keys)
            await msg.channel.send("🗑️ gelöscht")
        else:
            await msg.channel.send("❌ nicht gefunden")

    # LISTE
    elif cmd == "!list":
        keys = load_keys()
        if not keys:
            return await msg.channel.send("Keine Keys")

        text = "\n".join(keys.keys())
        await msg.channel.send(f"🔑 Keys:\n{text}")

# =========================
# FLASK API
# =========================
app = Flask(__name__)

@app.route("/validate", methods=["POST"])
def validate():
    data = request.json
    key = data.get("key")

    keys = load_keys()

    if key == "SERGAJ-FREE":
        return jsonify({"valid": True})

    if key in keys:
        return jsonify({"valid": True})
    else:
        return jsonify({"valid": False})

@app.route("/")
def home():
    return "API läuft!"

# =========================
# RUN BEIDES
# =========================
def run_bot():
    bot.run(os.getenv("TOKEN"))

Thread(target=run_bot).start()

port = int(os.getenv("PORT", 8080))
app.run(host="0.0.0.0", port=port)
