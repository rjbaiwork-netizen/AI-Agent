"""Strict integrity verification for the seven required brain documents."""
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from bot.tracer import append_trace

ROOT = Path(__file__).resolve().parents[1]
BRAIN_DIR = Path(__file__).with_name("brains")
OUT_DIR = ROOT / "data" / "brain_versions"
REQUIRED_BRAINS = (
    "common_base.md", "notes_routine.md", "project_logic.md", "logs_issues.md",
    "research_live.md", "coding_security.md", "writing_drafts.md",
)


def _utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".report-", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def get_brain_snapshot():
    results = {}
    errors = []
    for name in REQUIRED_BRAINS:
        path = BRAIN_DIR / name
        if not path.is_file():
            results[name] = {"status": "missing", "sha256": None, "size_bytes": 0}
            errors.append(f"Missing required brain file: {name}")
            continue
        content = path.read_bytes()
        if not content.strip():
            results[name] = {"status": "empty", "sha256": hashlib.sha256(content).hexdigest(), "size_bytes": len(content)}
            errors.append(f"Brain file is empty: {name}")
            continue
        results[name] = {
            "status": "verified",
            "sha256": hashlib.sha256(content).hexdigest(),
            "size_bytes": len(content),
        }
    return {"ok": not errors, "files": results, "errors": errors, "checked_at": _utc_now()}


def reverify_all_brains():
    snapshot = get_brain_snapshot()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "schema_version": 1,
        "verified_at": snapshot["checked_at"],
        "ok": snapshot["ok"],
        "status": "success" if snapshot["ok"] else "failed",
        "summary": (
            f"Verified all {len(REQUIRED_BRAINS)} required brain files."
            if snapshot["ok"] else "Brain verification failed: " + "; ".join(snapshot["errors"])
        ),
        "files": snapshot["files"],
        "errors": snapshot["errors"],
    }
    serialized = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    _atomic_write(OUT_DIR / "latest.json", serialized)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    _atomic_write(OUT_DIR / f"verification-{stamp}.json", serialized)
    append_trace("brain_reverify", {
        "summary": report["summary"],
        "files": report["files"],
        "errors": report["errors"],
    }, status="ok" if snapshot["ok"] else "error", source="agent.reverify")
    return {"ok": snapshot["ok"], "summary": report["summary"], "report": report}


if __name__ == "__main__":
    result = reverify_all_brains()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["ok"] else 1)
