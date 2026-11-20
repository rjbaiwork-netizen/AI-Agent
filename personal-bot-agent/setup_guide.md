# Setup guide
Run locally: create a Python venv, install `pip install -r requirements.txt`, run `python app.py`, and open `http://127.0.0.1:5000`.

Codespaces: use a private Codespace and keep port 5000 private. This starter has no login; do not expose it publicly.

Data: notes live in `data/notes.json`. GitHub is source control, not a managed database or private file store. Do not commit personal/sensitive data. Keep real keys in environment variables or GitHub Actions secrets.

Limits: this is a deterministic starter with routing, notes, planning, and modular brain files. No LLM, external API, database server, login, or cloud hosting is configured.