"""Flask API and web UI for the single-user Personal Bot Agent."""
import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from werkzeug.exceptions import BadRequest

from bot.actions import (
    add_note, add_task, check_system_status, complete_task,
    list_notes, list_tasks, tail_log,
)
from bot.router import route as route_message
from bot.tracer import append_trace, read_traces
from agent.reverify import get_brain_snapshot, reverify_all_brains
from agent.unified_brain import handle_request

ROOT = Path(__file__).resolve().parent
UI_DIR = ROOT / "ui"
ENV_FILE = ROOT / ".env"
ENV_LOADED = load_dotenv(ENV_FILE, override=False)

APP_HOST = os.getenv("APP_HOST", "127.0.0.1").strip() or "127.0.0.1"
try:
    APP_PORT = int(os.getenv("APP_PORT", "8000"))
    GUARDRAIL_MAX_STEPS = int(os.getenv("GUARDRAIL_MAX_STEPS", "10"))
    GUARDRAIL_TIMEOUT_SEC = int(os.getenv("GUARDRAIL_TIMEOUT_SEC", "60"))
except ValueError as exc:
    raise RuntimeError("APP_PORT, GUARDRAIL_MAX_STEPS and GUARDRAIL_TIMEOUT_SEC must be integers") from exc
if not 1 <= APP_PORT <= 65535:
    raise RuntimeError("APP_PORT must be between 1 and 65535")
if not 1 <= GUARDRAIL_MAX_STEPS <= 50 or not 1 <= GUARDRAIL_TIMEOUT_SEC <= 600:
    raise RuntimeError("Guardrail settings are outside their permitted ranges")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
ALLOW_LIVE_FETCH = os.getenv("ALLOW_LIVE_FETCH", "false").strip().lower() in {"1", "true", "yes", "on"}

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024

# CORS is restricted to the Pages site and local/Codespaces development origins.
from urllib.parse import urlsplit

PAGES_ORIGIN = "https://rjbaiwork-netizen.github.io"


def _cors_origin_allowed(origin):
    if not origin:
        return False
    try:
        parsed = urlsplit(origin)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return False
        if parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
            return False
        host = (parsed.hostname or "").lower().rstrip(".")
        if origin == PAGES_ORIGIN:
            return True
        if host in {"localhost", "127.0.0.1", "::1"}:
            return True
        return host.endswith(".app.github.dev") or host.endswith(".github.dev")
    except ValueError:
        return False


@app.before_request
def handle_api_preflight():
    if request.path.startswith("/api/") and request.method == "OPTIONS":
        return ("", 204)


@app.after_request
def add_api_cors_headers(response):
    if request.path.startswith("/api/"):
        origin = request.headers.get("Origin", "")
        if _cors_origin_allowed(origin):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
            response.headers["Access-Control-Max-Age"] = "600"
            response.headers.add("Vary", "Origin")
    return response


def _json_body():
    if not request.is_json:
        raise ValueError("Content-Type must be application/json")
    try:
        payload = request.get_json(silent=False)
    except BadRequest as exc:
        raise ValueError("Malformed JSON request body") from exc
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object")
    return payload


def _error(message, status=400):
    return jsonify({"ok": False, "error": str(message)}), status


@app.get("/")
def home():
    return send_from_directory(UI_DIR, "index.html")


@app.get("/ui/<path:filename>")
def ui_assets(filename):
    return send_from_directory(UI_DIR, filename)


@app.get("/api/health")
def health():
    try:
        system = check_system_status()
        healthy = bool(system.get("ok"))
        return jsonify({
            "ok": healthy,
            "status": system.get("status", "unknown"),
            "system": system,
            "configuration": {
                "env_file_present": ENV_FILE.is_file(),
                "dotenv_loaded": bool(ENV_LOADED),
                "gemini_configured": bool(GEMINI_API_KEY),
                "gemini_model": GEMINI_MODEL,
                "allow_live_fetch": ALLOW_LIVE_FETCH,
                "guardrails": {
                    "max_steps": GUARDRAIL_MAX_STEPS,
                    "timeout_sec": GUARDRAIL_TIMEOUT_SEC,
                },
            },
        }), (200 if healthy else 503)
    except Exception:
        app.logger.exception("Health check failed")
        return _error("Health check could not complete; inspect server logs.", 500)


@app.post("/api/chat")
def chat():
    try:
        payload = _json_body()
        message = payload.get("message")
        if not isinstance(message, str) or not message.strip() or len(message) > 8000:
            return _error("message must contain 1-8000 characters")
        result = route_message(message.strip())
        if not isinstance(result, dict):
            raise RuntimeError("Router returned an invalid response")
        append_trace("api_chat", {"intent": result.get("intent"), "handled_by": result.get("handled_by")}, status="ok" if result.get("meta", {}).get("ok") else "error", source="app")
        response = {
            "ok": bool(result.get("meta", {}).get("ok", False)),
            "reply": result.get("reply", ""),
            "intent": result.get("intent", "unknown"),
            "handled_by": result.get("handled_by", "unknown"),
            "data": result.get("data"),
            "plan": (result.get("data") or {}).get("plan") if isinstance(result.get("data"), dict) else None,
            "meta": result.get("meta", {}),
        }
        return jsonify(response), (200 if response["ok"] else 502)
    except (ValueError, KeyError) as exc:
        return _error(exc, 400)
    except Exception:
        app.logger.exception("Chat request failed")
        return _error("Chat processing failed; inspect operational logs.", 500)


@app.get("/api/notes")
def notes_get():
    try:
        return jsonify({"ok": True, "notes": list_notes()})
    except Exception:
        app.logger.exception("Could not read notes")
        return _error("Could not read notes storage.", 500)


@app.post("/api/notes")
def notes_post():
    try:
        payload = _json_body()
        note = add_note(payload.get("title", "Quick note"), payload.get("content", ""), payload.get("tags"))
        return jsonify({"ok": True, "note": note}), 201
    except (ValueError, TypeError) as exc:
        return _error(exc, 400)
    except Exception:
        app.logger.exception("Could not create note")
        return _error("Could not save note.", 500)


@app.get("/api/tasks")
def tasks_get():
    try:
        status = request.args.get("status")
        return jsonify({"ok": True, "tasks": list_tasks(status=status)})
    except ValueError as exc:
        return _error(exc, 400)
    except Exception:
        app.logger.exception("Could not read tasks")
        return _error("Could not read tasks storage.", 500)


@app.post("/api/tasks")
def tasks_post():
    try:
        payload = _json_body()
        task = add_task(payload.get("title", ""), payload.get("priority", "normal"), payload.get("due"))
        return jsonify({"ok": True, "task": task}), 201
    except (ValueError, TypeError) as exc:
        return _error(exc, 400)
    except Exception:
        app.logger.exception("Could not create task")
        return _error("Could not save task.", 500)


@app.post("/api/tasks/<task_id>/complete")
def tasks_complete(task_id):
    try:
        task = complete_task(task_id)
        return jsonify({"ok": True, "task": task})
    except KeyError as exc:
        return _error(exc, 404)
    except (ValueError, TypeError) as exc:
        return _error(exc, 400)
    except Exception:
        app.logger.exception("Could not complete task")
        return _error("Could not update task.", 500)


@app.get("/api/brains")
def brains_get():
    try:
        snapshot = get_brain_snapshot()
        return jsonify({"ok": snapshot["ok"], "snapshot": snapshot}), (200 if snapshot["ok"] else 409)
    except Exception:
        app.logger.exception("Could not inspect brain files")
        return _error("Brain inspection failed.", 500)


@app.post("/api/brains/reverify")
def brains_reverify():
    try:
        result = reverify_all_brains()
        return jsonify({"ok": result["ok"], "result": result}), (200 if result["ok"] else 422)
    except Exception:
        app.logger.exception("Brain re-verification failed")
        return _error("Brain re-verification failed; inspect logs.", 500)


@app.get("/api/logs")
def logs_get():
    try:
        line_count = request.args.get("lines", default=100, type=int)
        trace_count = request.args.get("traces", default=100, type=int)
        if not 1 <= line_count <= 1000 or not 1 <= trace_count <= 1000:
            return _error("lines and traces must be between 1 and 1000")
        return jsonify({
            "ok": True,
            "bot_log": tail_log(line_count),
            "traces": read_traces(trace_count),
        })
    except ValueError as exc:
        return _error(exc, 400)
    except Exception:
        app.logger.exception("Could not read operational logs")
        return _error("Could not read operational logs.", 500)


@app.errorhandler(404)
def not_found(_error):
    if request.path.startswith("/api/"):
        return _error("API endpoint not found.", 404)
    return _error("Page or asset not found.", 404)


@app.errorhandler(413)
def request_too_large(_error):
    return _error("Request body exceeds the 1 MiB limit.", 413)


if __name__ == "__main__":
    print(f"Starting Personal Bot Agent on {APP_HOST}:{APP_PORT}")
    app.run(host=APP_HOST, port=APP_PORT, debug=False)
