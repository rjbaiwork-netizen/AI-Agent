#!/usr/bin/env python3
"""Build and validate the static GitHub Pages frontend from maintained UI sources."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "personal-bot-agent" / "ui"
OUTPUT = ROOT / "_site"
REQUIRED = ("index.html", "styles.css", "app.js")

if not SOURCE.is_dir():
    raise SystemExit(f"UI source directory not found: {SOURCE}")
for name in REQUIRED:
    source_file = SOURCE / name
    if not source_file.is_file() or source_file.stat().st_size == 0:
        raise SystemExit(f"Required UI source is missing or empty: {source_file}")

if OUTPUT.exists():
    shutil.rmtree(OUTPUT)
OUTPUT.mkdir(parents=True)
for name in REQUIRED:
    shutil.copy2(SOURCE / name, OUTPUT / name)

index = (OUTPUT / "index.html").read_text(encoding="utf-8")
if '<meta charset="UTF-8">' not in index:
    raise SystemExit("index.html must declare UTF-8 encoding.")
if '<meta name="viewport" content="width=device-width, initial-scale=1.0">' not in index:
    raise SystemExit("index.html must declare a responsive viewport.")
for asset in ("./styles.css", "./app.js"):
    if asset not in index:
        raise SystemExit(f"Missing relative Pages asset reference: {asset}")
if "/ui/styles.css" in index or "/ui/app.js" in index:
    raise SystemExit("Pages HTML must not use root-absolute Flask asset paths.")

(OUTPUT / ".nojekyll").write_text("", encoding="utf-8")
for name in REQUIRED:
    artifact = OUTPUT / name
    if not artifact.is_file() or artifact.stat().st_size == 0:
        raise SystemExit(f"Missing or empty Pages artifact: {artifact}")
if not (OUTPUT / ".nojekyll").is_file():
    raise SystemExit("Missing Pages artifact: _site/.nojekyll")

print("GitHub Pages static artifact built and validated successfully.")
print("Files:", ", ".join(sorted(path.name for path in OUTPUT.iterdir())))
