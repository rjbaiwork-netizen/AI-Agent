# Project Logic Brain

## Repository identity
- Repository: `rjbaiwork-netizen/AI-Agent`.
- Production working branch: `main` only. Do not create, switch to, or recommend a feature branch for authorized direct-main work.
- Application root: `personal-bot-agent/`; Python package imports are resolved with that directory as the working directory.

## Application architecture
- Flask application entry point: `app.py`.
- UI assets: `ui/index.html`, `ui/styles.css`, and `ui/app.js`.
- Deterministic command routing and user actions: `bot/rules.json`, `bot/router.py`, `bot/actions.py`, and `bot/tracer.py`.
- Agent orchestration: `agent/unified_brain.py`, `agent/planner.py`, `agent/tools.py`, and `agent/reverify.py`.
- Domain guidance: seven required Markdown files under `agent/brains/`.

## Persistence
- Notes: `data/notes.json`; tasks: `data/tasks.json`.
- Brain integrity reports: `data/brain_versions/latest.json` plus timestamped reports.
- Operational logs: `logs/bot.log` (human-readable) and `logs/trace.jsonl` (one JSON object per line).
- JSON writes must be validated and atomic. JSONL readers must reject malformed non-empty lines with a line-numbered error.

## GitHub automation and Codespaces
- GitHub Actions workflows use Python 3.11 and install `personal-bot-agent/requirements.txt`.
- Workflows writing repository data require `contents: write`, concurrency serialization, explicit paths, and safe non-force push handling.
- Codespaces should bind the Flask server to `0.0.0.0`; the configured `APP_PORT` must match the forwarded port.
- Never claim a workflow ran merely because its YAML exists. Verify the Actions run record and logs.

## API contracts
- `GET /api/health`: JSON health response.
- `GET /api/notes`: stored notes array.
- `POST /api/notes`: validated note creation.
- `POST /api/chat`: structured router/agent response with reply, intent, handled_by, data, and meta.
- API errors should use an appropriate HTTP status and a clear JSON error field.
