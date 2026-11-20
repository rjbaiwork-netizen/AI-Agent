import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory

from agent.tools import append_note, read_notes
from bot.router import route
from agent.planner import make_plan

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

APP_HOST = os.getenv("APP_HOST", "127.0.0.1")
APP_PORT = int(os.getenv("APP_PORT", "8000"))
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
ALLOW_LIVE_FETCH = os.getenv("ALLOW_LIVE_FETCH", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
GUARDRAIL_MAX_STEPS = int(os.getenv("GUARDRAIL_MAX_STEPS", "10"))
GUARDRAIL_TIMEOUT_SEC = int(os.getenv("GUARDRAIL_TIMEOUT_SEC", "60"))

app = Flask(__name__, static_folder="ui", static_url_path="")


@app.get("/")
def home():
    return send_from_directory(ROOT / "ui", "index.html")


@app.get("/api/health")
def health():
    return jsonify(ok=True)


@app.get("/api/notes")
def notes():
    return jsonify(notes=read_notes())


@app.post("/api/notes")
def add_note():
    data = request.get_json(silent=True) or {}
    text = str(data.get("text", "")).strip()
    if not text:
        return jsonify(error="Text required"), 400
    return jsonify(note=append_note(text))


@app.post("/api/chat")
def chat():
    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip()
    if not message or len(message) > 8000:
        return jsonify(error="Message must contain 1-8000 characters"), 400

    intent = route(message)
    if intent == "planning":
        reply = "\\n".join(make_plan(message))
    else:
        reply = f"Intent: {intent}. Local starter agent; no model provider configured."
    return jsonify(reply=reply)


if __name__ == "__main__":
    (ROOT / "logs").mkdir(exist_ok=True)
    app.run(host=APP_HOST, port=APP_PORT, debug=False)
