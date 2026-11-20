"""Append-only JSONL event tracing for the personal bot."""
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRACE_PATH = ROOT / "logs" / "trace.jsonl"
_LOCK = threading.Lock()


def _json_safe(value):
    try:
        json.dumps(value, ensure_ascii=False)
        return value
    except (TypeError, ValueError):
        if isinstance(value, dict):
            return {str(k): _json_safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [_json_safe(v) for v in value]
        return repr(value)


def append_trace(event_type, payload, status="ok", source="bot"):
    if not isinstance(event_type, str) or not event_type.strip():
        raise ValueError("event_type must be a non-empty string")
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "event_type": event_type.strip(),
        "status": str(status),
        "source": str(source),
        "payload": _json_safe(payload),
    }
    TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(record, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    with _LOCK:
        with TRACE_PATH.open("a", encoding="utf-8") as handle:
            handle.write(encoded + "\n")
            handle.flush()
    return record


def read_traces(limit=50):
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ValueError("limit must be a positive integer")
    TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
    TRACE_PATH.touch(exist_ok=True)
    records = []
    with _LOCK:
        with TRACE_PATH.open("r", encoding="utf-8") as handle:
            for number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                    if not isinstance(item, dict):
                        raise ValueError("record must be a JSON object")
                    records.append(item)
                except (json.JSONDecodeError, ValueError) as exc:
                    raise ValueError(f"Invalid trace JSON at line {number}: {exc}") from exc
    return records[-min(limit, 1000):]
