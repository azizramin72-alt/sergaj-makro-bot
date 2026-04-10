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
TOKEN = os.getenv("DISCORD_TOKEN")
ADMIN_ID = 1370498558419140628
DB = "keys.json"
SECRET = os.getenv("SECRET", "sergajsecret")

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
    return f"BIGRED-{part}"

# =====================
# API ROUTES
# =====================
@app.route("/validate", methods=["POST"])
def validate():
    data = request.json
    key = data.get("key", "").strip().upper()
    if not key:
        return jsonify({"valid": False, "reason": "No key provided"})
    db = load()
    if key not in db:
        return jsonify({"valid": False, "reason": "Invalid key"})
    k = db[key]
    if k["banned"]:
        return jsonify({"valid": False, "reason": "Key is banned"})
    exp = datetime.fromisoformat(k["expires"])
    if datetime.now() > exp:
        return jsonify({"valid": False, "reason": "Key expired"})
    days_left = (exp - datetime.now()).days
    return jsonify({"valid": True, "reason": "OK", "days_left": days_left})

@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "Big Red Server online"})

# =====================
# EMBED HELPER
# =====================
async def send_key_embed(user, key, days, product="Big Red Optimizer"):
    expire_date = (datetime.now() + timedelta(days=days)).strftime("%d.%m.%Y")
    duration_text = "OneTime" if days <= 1 else f"{days} Days"

    embed = discord.Embed(
        title="Big Red | Key Generation",
        color=0xE53935  # Rot passend zum Branding
    )
    embed.add_field(name="\u200b", value="● Key Generation Request Successful.", inline=False)
    embed.add_field(name="\u200b", value=f"● Your License for **{product}** is:", inline=False)
    embed.add_field(name="\u200b", value=f"```{key}```", inline=False)
    embed.add_field(name="● Duration:", value=duration_text, inline=True)
    embed.add_field(name="● Product:", value=product, inline=True)
    embed.add_field(name="● Expires:", value=expire_date, inline=True)
    embed.add_field(
        name="● Instruction:",
        value="https://twitch.tv/kevinheadred",
        inline=False
    )
    embed.set_footer(text=f"Auth - Big Red  •  {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    embed.set_thumbnail(url="https://i.imgur.com/your-logo.png")  # Logo URL hier eintragen

    await user.send(embed=embed)

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

    args = msg.content.strip().split()
    if not args:
        return
    cmd = args[0]

    # !genkey [days] [@user]
    if cmd == "!genkey":
        try:
            days = int(args[1]) if len(args) > 1 else 30
        except:
            await msg.channel.send("❌ Usage: `!genkey <days> [@user]`")
            return

        key = gen_key()
        db = load()
        expire = (datetime.now() + timedelta(days=days)).isoformat()
        db[key] = {"banned": False, "expires": expire}
        save(db)

        if msg.mentions:
            user = msg.mentions[0]
            try:
                await send_key_embed(user, key, days)
                await msg.channel.send(
                    f"✅ Key generated and sent to {user.mention} via DM!\n"
                    f"🔑 `{key}` — **{days} days**"
                )
            except discord.Forbidden:
                await msg.channel.send(
                    f"✅ Key generated but couldn't DM {user.mention} (DMs closed)\n"
                    f"🔑 `{key}` — **{days} days**"
                )
        else:
            await msg.channel.send(
                f"✅ Key generated!\n"
                f"🔑 `{key}` — **{days} days**\n"
                f"💡 Tip: Use `!genkey {days} @user` to send key via DM"
            )

    # !bankey [key]
    elif cmd == "!bankey":
        if len(args) < 2:
            return await msg.channel.send("❌ Usage: `!bankey BIGRED-XXXXXXXX`")
        key = args[1].upper()
        db = load()
        if key not in db:
            return await msg.channel.send("❌ Key not found.")
        db[key]["banned"] = True
        save(db)
        await msg.channel.send(f"🔨 Key `{key}` has been **banned**.")

    # !unbankey [key]
    elif cmd == "!unbankey":
        if len(args) < 2:
            return await msg.channel.send("❌ Usage: `!unbankey BIGRED-XXXXXXXX`")
        key = args[1].upper()
        db = load()
        if key not in db:
            return await msg.channel.send("❌ Key not found.")
        db[key]["banned"] = False
        save(db)
        await msg.channel.send(f"✅ Key `{key}` has been **unbanned**.")

    # !keyinfo [key]
    elif cmd == "!keyinfo":
        if len(args) < 2:
            return await msg.channel.send("❌ Usage: `!keyinfo BIGRED-XXXXXXXX`")
        key = args[1].upper()
        db = load()
        if key not in db:
            return await msg.channel.send("❌ Key not found.")
        k = db[key]
        exp = datetime.fromisoformat(k["expires"])
        left = (exp - datetime.now()).days
        status = "❌ Banned" if k["banned"] else "✅ Active"
        expired = "⚠️ Expired" if datetime.now() > exp else f"📅 {left} days remaining"
        await msg.channel.send(
            f"🔑 **Key Info**\n"
            f"```{key}```\n"
            f"Status: {status}\n"
            f"Expires: {exp.strftime('%d.%m.%Y')} — {expired}"
        )

    # !listkeys
    elif cmd == "!listkeys":
        db = load()
        if not db:
            return await msg.channel.send("📭 No keys found.")
        lines = []
        for k, v in db.items():
            exp = datetime.fromisoformat(v["expires"])
            left = (exp - datetime.now()).days
            icon = "❌" if v["banned"] else ("⚠️" if left < 0 else "✅")
            lines.append(f"{icon} `{k}` — {left}d")
        chunk = ""
        for line in lines:
            if len(chunk) + len(line) > 1800:
                await msg.channel.send(f"**Keys:**\n{chunk}")
                chunk = ""
            chunk += line + "\n"
        if chunk:
            await msg.channel.send(f"**Keys:**\n{chunk}")

    # !delkey [key]
    elif cmd == "!delkey":
        if len(args) < 2:
            return await msg.channel.send("❌ Usage: `!delkey BIGRED-XXXXXXXX`")
        key = args[1].upper()
        db = load()
        if key not in db:
            return await msg.channel.send("❌ Key not found.")
        del db[key]
        save(db)
        await msg.channel.send(f"🗑️ Key `{key}` has been **deleted**.")

    # !help
    elif cmd == "!help":
        await msg.channel.send(
            "**Big Red Bot Commands**\n\n"
            "`!genkey <days> [@user]` — Generate a key\n"
            "`!bankey <key>` — Ban a key\n"
            "`!unbankey <key>` — Unban a key\n"
            "`!keyinfo <key>` — Key details\n"
            "`!listkeys` — List all keys\n"
            "`!delkey <key>` — Delete a key\n"
        )

# =====================
# START SERVER + BOT
# =====================
def run_flask():
    app.run(host="0.0.0.0", port=8080)

threading.Thread(target=run_flask).start()
bot.run(TOKEN)
