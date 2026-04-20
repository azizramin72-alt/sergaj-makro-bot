"""
web.py — Valora OAuth2 Webserver
Run alongside bot.py. Handles Discord OAuth2 callback,
saves access tokens so the bot can add users to servers.

Install: pip install flask requests python-dotenv
Run:     python web.py
"""

import os
import json
import requests
from datetime import datetime, timezone
from flask import Flask, request, redirect, render_template_string
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID      = os.getenv("DISCORD_CLIENT_ID", "")
CLIENT_SECRET  = os.getenv("DISCORD_CLIENT_SECRET", "")
WEB_BASE_URL   = os.getenv("WEB_BASE_URL", "http://localhost:5000")
REDIRECT_URI   = f"{WEB_BASE_URL}/callback"
VERIFIED_FILE  = "verified.json"

app = Flask(__name__)

# ── Load / save verified.json ─────────────────────────────────
def load_verified():
    if os.path.exists(VERIFIED_FILE):
        with open(VERIFIED_FILE) as f:
            return json.load(f)
    return {}

def save_verified(data):
    with open(VERIFIED_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ── HTML Pages ────────────────────────────────────────────────
SUCCESS_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Verified — Valora</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@600;700&family=DM+Sans:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #0b0d14;
    --card: #12151f;
    --border: #1c2035;
    --blue: #00BFFF;
    --green: #00e5a0;
    --text: #dde4f0;
    --muted: #5a6480;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'DM Sans', sans-serif;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
  }
  /* animated bg grid */
  body::before {
    content: '';
    position: fixed;
    inset: 0;
    background-image:
      linear-gradient(rgba(0,191,255,0.03) 1px, transparent 1px),
      linear-gradient(90deg, rgba(0,191,255,0.03) 1px, transparent 1px);
    background-size: 40px 40px;
    pointer-events: none;
  }
  .card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 48px 44px;
    max-width: 460px;
    width: 100%;
    text-align: center;
    position: relative;
    overflow: hidden;
  }
  .card::before {
    content: '';
    position: absolute;
    top: 0; left: 50%; transform: translateX(-50%);
    width: 200px; height: 1px;
    background: linear-gradient(90deg, transparent, var(--green), transparent);
  }
  .icon-wrap {
    width: 80px; height: 80px;
    border-radius: 50%;
    background: rgba(0,229,160,0.1);
    border: 1px solid rgba(0,229,160,0.3);
    display: flex; align-items: center; justify-content: center;
    margin: 0 auto 24px;
    font-size: 36px;
    animation: pop 0.5s cubic-bezier(0.175,0.885,0.32,1.275) both;
  }
  @keyframes pop {
    0%  { transform: scale(0); opacity: 0; }
    100%{ transform: scale(1); opacity: 1; }
  }
  .brand {
    font-family: 'Rajdhani', sans-serif;
    font-size: 13px;
    letter-spacing: 4px;
    color: var(--blue);
    margin-bottom: 12px;
    text-transform: uppercase;
  }
  h1 {
    font-family: 'Rajdhani', sans-serif;
    font-size: 32px;
    color: var(--green);
    margin-bottom: 12px;
    letter-spacing: 1px;
  }
  p {
    color: var(--muted);
    font-size: 15px;
    line-height: 1.7;
    margin-bottom: 8px;
  }
  .username {
    display: inline-block;
    background: rgba(0,191,255,0.1);
    border: 1px solid rgba(0,191,255,0.2);
    border-radius: 8px;
    padding: 6px 16px;
    font-size: 15px;
    font-weight: 500;
    color: var(--blue);
    margin: 16px 0 24px;
  }
  .divider {
    height: 1px;
    background: var(--border);
    margin: 24px 0;
  }
  .footer {
    font-size: 12px;
    color: var(--muted);
  }
  .footer a { color: var(--blue); text-decoration: none; }
  .badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(0,229,160,0.08);
    border: 1px solid rgba(0,229,160,0.2);
    border-radius: 999px;
    padding: 5px 14px;
    font-size: 13px;
    color: var(--green);
    margin-top: 4px;
  }
</style>
</head>
<body>
<div class="card">
  <div class="icon-wrap">✅</div>
  <div class="brand">Valora Store</div>
  <h1>Verified!</h1>
  <p>You have successfully verified your Discord account.</p>
  <div class="username">{{ username }}</div>
  <p>Return to Discord — you will receive your <strong style="color:var(--text)">Verified</strong> role shortly.</p>
  <div class="divider"></div>
  <div class="badge">🔐 Secure • Discord OAuth2</div>
  <div class="divider"></div>
  <div class="footer">
    <a href="https://valora-store.mysellauth.com/">valora-store.mysellauth.com</a><br>
    <span style="margin-top:6px;display:block">You can close this tab.</span>
  </div>
</div>
</body>
</html>"""

ERROR_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Error — Valora</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500&display=swap" rel="stylesheet">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0b0d14; color: #dde4f0; font-family: 'DM Sans', sans-serif;
         min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; }
  .card { background: #12151f; border: 1px solid #1c2035; border-radius: 20px; padding: 48px 44px;
          max-width: 440px; width: 100%; text-align: center; }
  h1 { color: #FF6B6B; font-size: 28px; margin: 20px 0 12px; }
  p  { color: #5a6480; font-size: 15px; line-height: 1.7; }
  .icon { font-size: 48px; display: block; margin-bottom: 8px; }
</style>
</head>
<body>
<div class="card">
  <span class="icon">❌</span>
  <h1>Verification Failed</h1>
  <p>{{ error }}</p>
  <p style="margin-top:16px">Please try again by clicking the verify button in Discord.</p>
</div>
</body>
</html>"""

# ── Routes ────────────────────────────────────────────────────
@app.route("/")
def index():
    return "<h2 style='font-family:sans-serif;text-align:center;margin-top:100px'>Valora OAuth2 Server is running ✅</h2>"

@app.route("/callback")
def callback():
    code  = request.args.get("code")
    error = request.args.get("error")

    if error or not code:
        return render_template_string(ERROR_HTML, error="Authorization was denied or cancelled."), 400

    # 1. Exchange code for access token
    token_res = requests.post(
        "https://discord.com/api/v10/oauth2/token",
        data={
            "client_id":     CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type":    "authorization_code",
            "code":          code,
            "redirect_uri":  REDIRECT_URI,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )

    if token_res.status_code != 200:
        return render_template_string(ERROR_HTML, error=f"Token exchange failed: {token_res.text}"), 500

    token_data   = token_res.json()
    access_token = token_data.get("access_token")

    if not access_token:
        return render_template_string(ERROR_HTML, error="No access token received."), 500

    # 2. Fetch user info
    user_res = requests.get(
        "https://discord.com/api/v10/users/@me",
        headers={"Authorization": f"Bearer {access_token}"}
    )

    if user_res.status_code != 200:
        return render_template_string(ERROR_HTML, error="Could not fetch user info."), 500

    user = user_res.json()
    uid  = user["id"]
    name = user.get("username", "unknown")

    # 3. Save to verified.json  (bot reads this)
    verified = load_verified()
    verified[uid] = {
        "username":     name,
        "access_token": access_token,
        "verified_at":  datetime.now(timezone.utc).isoformat(),
    }
    save_verified(verified)

    print(f"[VERIFY] ✅ {name} ({uid}) verified successfully")

    return render_template_string(SUCCESS_HTML, username=f"{name}")


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"🌐 Valora OAuth2 Server running on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
