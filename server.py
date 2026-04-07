from flask import Flask, request, jsonify
import json
import os
from datetime import datetime

app = Flask(__name__)
DB_FILE = "keys.json"

def load():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE) as f:
        return json.load(f)

def save(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=2)

@app.route("/validate", methods=["GET"])
def validate():
    key = request.args.get("key", "").strip().upper()
    if not key:
        return jsonify({"valid": False, "reason": "No key provided"})
    db = load()
    if key not in db:
        return jsonify({"valid": False, "reason": "Key not found"})
    k = db[key]
    if k["banned"]:
        return jsonify({"valid": False, "reason": "Key banned"})
    expires = datetime.fromisoformat(k["expires"])
    if datetime.now() > expires:
        return jsonify({"valid": False, "reason": "Key expired"})
    return jsonify({"valid": True, "reason": "OK"})

@app.route("/addkey", methods=["POST"])
def addkey():
    secret = request.headers.get("X-Secret", "")
    if secret != os.environ.get("SECRET", "meingeheimespasswort"):
        return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    key = data.get("key")
    expires = data.get("expires")
    db = load()
    db[key] = {"banned": False, "expires": expires}
    save(db)
    return jsonify({"success": True})

@app.route("/bankey", methods=["POST"])
def bankey():
    secret = request.headers.get("X-Secret", "")
    if secret != os.environ.get("SECRET", "meingeheimespasswort"):
        return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    key = data.get("key")
    db = load()
    if key not in db:
        return jsonify({"error": "Key not found"}), 404
    db[key]["banned"] = True
    save(db)
    return jsonify({"success": True})

@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "SERGAJ Server online"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
