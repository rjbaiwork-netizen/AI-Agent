#!/usr/bin/env python3
"""Build the production GitHub Pages frontend from maintained UI sources."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "personal-bot-agent" / "ui"
OUTPUT = ROOT / "_site"
if OUTPUT.exists():
    shutil.rmtree(OUTPUT)
OUTPUT.mkdir(parents=True)
for name in ("index.html", "styles.css", "app.js"):
    shutil.copy2(SOURCE / name, OUTPUT / name)
index = (OUTPUT / "index.html").read_text(encoding="utf-8")
index = index.replace('href="/ui/styles.css"', 'href="./styles.css"')
index = index.replace('src="/ui/app.js"', 'src="./app.js"')
(OUTPUT / "index.html").write_text(index, encoding="utf-8")
(OUTPUT / ".nojekyll").write_text("", encoding="utf-8")
for asset in ("./styles.css", "./app.js"):
    if asset not in index:
        raise SystemExit(f"Missing Pages asset reference: {asset}")
for name in ("index.html", "styles.css", "app.js", ".nojekyll"):
    if not (OUTPUT / name).is_file():
        raise SystemExit(f"Missing Pages artifact: {name}")
print("GitHub Pages static artifact built successfully.")
print("Files:", ", ".join(sorted(path.name for path in OUTPUT.iterdir())))
