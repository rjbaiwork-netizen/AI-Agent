"""Validated file-backed actions for the single-user assistant."""
import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from bot.tracer import append_trace, read_traces

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
LOGS = ROOT / "logs"
NOTES_PATH = DATA / "notes.json"
TASKS_PATH = DATA / "tasks.json"
BRAIN_REPORT = DATA / "brain_versions" / "latest.json"
BOT_LOG = LOGS / "bot.log"
TRACE_LOG = LOGS / "trace.jsonl"
BRAINS = ROOT / "agent" / "brains"


def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _atomic_json_write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def _read_json_list(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        _atomic_json_write(path, [])
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Cannot read valid JSON from {path.relative_to(ROOT)}: {exc}") from exc
    if not isinstance(value, list):
        raise RuntimeError(f"{path.relative_to(ROOT)} must contain a JSON array")
    return value


def _log_action(event, details, status="ok"):
    LOGS.mkdir(parents=True, exist_ok=True)
    message = f"{_now()} | {event} | status={status} | {json.dumps(details, ensure_ascii=False, sort_keys=True)}\n"
    with BOT_LOG.open("a", encoding="utf-8") as handle:
        handle.write(message)
        handle.flush()
    append_trace(event, details, status=status, source="bot.actions")


def _validate_text(value, field, maximum=4000):
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    value = value.strip()
    if not value:
        raise ValueError(f"{field} cannot be empty")
    if len(value) > maximum:
        raise ValueError(f"{field} cannot exceed {maximum} characters")
    return value


def check_system_status():
    required = [NOTES_PATH, TASKS_PATH, BOT_LOG, TRACE_LOG, BRAIN_REPORT]
    checks = {}
    errors = []
    for directory in (DATA, LOGS, BRAINS):
        checks[str(directory.relative_to(ROOT))] = {
            "exists": directory.is_dir(),
            "type": "directory",
        }
        if not directory.is_dir():
            errors.append(f"Missing directory: {directory.relative_to(ROOT)}")
    for path in required:
        exists = path.is_file()
        item = {"exists": exists, "size_bytes": path.stat().st_size if exists else None}
        if exists and path.suffix == ".json":
            try:
                with path.open("r", encoding="utf-8") as handle:
                    json.load(handle)
                item["valid"] = True
            except (OSError, json.JSONDecodeError) as exc:
                item["valid"] = False
                item["error"] = str(exc)
                errors.append(f"Invalid JSON: {path.relative_to(ROOT)}")
        elif exists and path.name == "trace.jsonl":
            try:
                for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                    if line.strip():
                        json.loads(line)
                item["valid"] = True
            except (OSError, json.JSONDecodeError) as exc:
                item["valid"] = False
                item["error"] = str(exc)
                errors.append(f"Invalid JSONL: {path.relative_to(ROOT)}")
        checks[str(path.relative_to(ROOT))] = item
        if not exists:
            errors.append(f"Missing file: {path.relative_to(ROOT)}")
    brain_files = sorted(BRAINS.glob("*.md"))
    checks["agent/brains/files"] = {
        "count": len(brain_files),
        "files": [p.name for p in brain_files],
        "non_empty": all(p.stat().st_size > 0 for p in brain_files),
    }
    if len(brain_files) != 7 or not checks["agent/brains/files"]["non_empty"]:
        errors.append("Expected seven non-empty brain markdown files")
    result = {
        "status": "ok" if not errors else "degraded",
        "ok": not errors,
        "checked_at": _now(),
        "checks": checks,
        "errors": errors,
    }
    _log_action("system_status", result)
    return result


def list_tasks(status=None):
    tasks = _read_json_list(TASKS_PATH)
    if status is not None:
        normalized = str(status).strip().lower()
        if normalized not in {"open", "pending", "completed", "done", "all"}:
            raise ValueError("status must be open, pending, completed, done, or all")
        if normalized in {"open", "pending"}:
            tasks = [task for task in tasks if not task.get("completed", False)]
        elif normalized in {"completed", "done"}:
            tasks = [task for task in tasks if task.get("completed", False)]
    return tasks


def add_task(title, priority="normal", due=None):
    title = _validate_text(title, "title", 500)
    priority = str(priority).strip().lower()
    if priority not in {"low", "normal", "high", "urgent"}:
        raise ValueError("priority must be low, normal, high, or urgent")
    if due is not None:
        due = _validate_text(due, "due", 100)
    tasks = _read_json_list(TASKS_PATH)
    task = {
        "id": uuid.uuid4().hex[:12],
        "title": title,
        "priority": priority,
        "due": due,
        "completed": False,
        "created_at": _now(),
        "completed_at": None,
    }
    tasks.append(task)
    _atomic_json_write(TASKS_PATH, tasks)
    _log_action("task_added", {"task_id": task["id"], "title": title, "priority": priority})
    return task


def complete_task(task_id):
    task_id = _validate_text(task_id, "task_id", 100)
    tasks = _read_json_list(TASKS_PATH)
    for task in tasks:
        if str(task.get("id")) == task_id:
            if not task.get("completed", False):
                task["completed"] = True
                task["completed_at"] = _now()
                _atomic_json_write(TASKS_PATH, tasks)
            _log_action("task_completed", {"task_id": task_id})
            return task
    raise KeyError(f"Task not found: {task_id}")


def list_notes():
    return _read_json_list(NOTES_PATH)


def add_note(title, content, tags=None):
    title = _validate_text(title, "title", 300)
    content = _validate_text(content, "content", 10000)
    if tags is None:
        tags = []
    if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
        raise ValueError("tags must be a list of strings")
    clean_tags = sorted({tag.strip()[:50] for tag in tags if tag.strip()})
    notes = _read_json_list(NOTES_PATH)
    note = {
        "id": uuid.uuid4().hex[:12],
        "title": title,
        "content": content,
        "tags": clean_tags,
        "created_at": _now(),
        "updated_at": _now(),
    }
    notes.append(note)
    _atomic_json_write(NOTES_PATH, notes)
    _log_action("note_added", {"note_id": note["id"], "title": title, "tags": clean_tags})
    return note


def tail_log(lines=40):
    if isinstance(lines, bool) or not isinstance(lines, int) or not 1 <= lines <= 1000:
        raise ValueError("lines must be an integer between 1 and 1000")
    LOGS.mkdir(parents=True, exist_ok=True)
    BOT_LOG.touch(exist_ok=True)
    with BOT_LOG.open("r", encoding="utf-8") as handle:
        return handle.read().splitlines()[-lines:]


# Backwards-compatible helpers used by the existing Flask notes endpoint.
def read_notes():
    return list_notes()


def append_note(text):
    text = _validate_text(text, "text", 2000)
    return add_note("Quick note", text, [])


def execute(intent, payload=None):
    payload = payload or {}
    actions = {
        "system_status": lambda: check_system_status(),
        "list_notes": lambda: list_notes(),
        "add_note": lambda: add_note(payload.get("title", "Quick note"), payload.get("content", payload.get("text", "")), payload.get("tags")),
        "list_tasks": lambda: list_tasks(payload.get("status")),
        "add_task": lambda: add_task(payload.get("title", ""), payload.get("priority", "normal"), payload.get("due")),
        "complete_task": lambda: complete_task(payload.get("task_id", "")),
        "tail_log": lambda: tail_log(payload.get("lines", 40)),
        "read_traces": lambda: read_traces(payload.get("limit", 50)),
    }
    if intent not in actions:
        raise ValueError(f"Unsupported action: {intent}")
    return actions[intent]()
