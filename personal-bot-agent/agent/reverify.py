import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRAIN = Path(__file__).with_name("brains")
OUT = ROOT / "data" / "brain_versions"


def verify():
    files = sorted(BRAIN.glob("*.md"))
    if not files:
        raise SystemExit("No brain files")
    report = {
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "files": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in files
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "latest.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print("Verified", len(files), "brain files")
    return report


def reverify_all_brains():
    report = verify()
    return {
        "ok": bool(report.get("files")),
        "summary": f"Verified {len(report.get('files', {}))} brain files",
        "report": report,
    }


if __name__ == "__main__":
    verify()
