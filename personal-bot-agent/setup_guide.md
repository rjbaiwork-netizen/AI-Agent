# Setup Guide — Personal Bot & AI Agent

এই প্রজেক্টটি একক ব্যক্তিগত ব্যবহারের জন্য। এখানে কোনো login বা multi-user account ব্যবস্থা নেই। GitHub repository-এর `main` branch-ই canonical source; কোনো API key বা secret source control-এ commit করবেন না।

## GitHub Codespaces setup

1. `rjbaiwork-netizen/AI-Agent` repository থেকে Codespace খুলুন।
2. Terminal-এ চালান:

   ```bash
   cd /workspaces/AI-Agent/personal-bot-agent
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   if [ ! -f .env ]; then cp .env.example .env; fi
   ```

3. `.env`-এ প্রয়োজনমতো `APP_HOST=0.0.0.0` এবং `APP_PORT=8000` রাখুন। Gemini ব্যবহার করতে চাইলে Codespaces secret বা স্থানীয় ignored `.env`-এ `GEMINI_API_KEY` দিন। key কখনো repository-তে commit করবেন না।
4. সার্ভার চালান:

   ```bash
   python app.py
   ```

5. Codespaces Ports ট্যাবে 8000 port-টি Private রাখুন। UI-তে health, chat, notes, tasks, brains এবং logs যাচাই করুন।

## API endpoints

- `GET /` — dashboard UI
- `GET /api/health` — system and configuration status (secret values প্রকাশ করে না)
- `POST /api/chat` — `{"message":"system status"}`
- `GET/POST /api/notes` — note listing and creation
- `GET/POST /api/tasks` — task listing and creation
- `POST /api/tasks/<task_id>/complete` — task completion
- `GET /api/brains`, `POST /api/brains/reverify` — brain integrity
- `POST /api/brains/update` — save a topic, content and registered `brain_file`; writes atomically and re-verifies SHA-256
- `POST /api/brains/update-online` — fetch public HTTPS HTML, plain text or JSON with a bounded timeout; requires `ALLOW_LIVE_FETCH=true`; blocks private/local destinations and unsupported content types

Chat commands accept explicit JSON payloads:

```text
brain update {"topic":"Flask API security","brain_file":"coding_security.md","content":"Validate request schemas and body sizes."}
brain online {"topic":"Python documentation","brain_file":"research_live.md","url":"https://docs.python.org/3/"}
```

Live retrieval records source URL and retrieval metadata. It extracts and creates a deterministic extractive summary from document sentences; it does not independently fact-check source claims. Query strings and URL fragments are rejected to reduce accidental credential logging. Set `ALLOW_LIVE_FETCH=true` in the Codespaces `.env` only when enabling network retrieval. Network, HTTP, timeout and invalid-content failures are returned as errors, never as successful updates.
- `GET /api/logs` — recent bot log and JSONL traces

## Local validation

   ```bash
   python -m compileall -q bot agent app.py tests
   node --check ui/app.js
   python -m json.tool bot/rules.json >/dev/null
   ```

## Storage and privacy

Application records are stored in `data/notes.json`, `data/tasks.json`, `data/brain_versions/`, `logs/bot.log`, and `logs/trace.jsonl`. Do not store credentials or private tokens in notes, logs, or trace payloads. GitHub Actions workflows may commit operational records to `main`; review their permissions and visibility before storing sensitive personal content.
