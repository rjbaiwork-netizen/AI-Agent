"""Isolated Flask API smoke tests; writes only beneath a disposable test directory."""
import json
import os
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

import app as web_app
from agent import reverify, unified_brain
from bot import actions, tracer


class ApiSmokeTests(unittest.TestCase):
    def setUp(self):
        self.runtime = Path(__file__).resolve().parents[1] / ".test-runtime"
        shutil.rmtree(self.runtime, ignore_errors=True)
        data = self.runtime / "data"
        logs = self.runtime / "logs"
        (data / "brain_versions").mkdir(parents=True)
        logs.mkdir(parents=True)
        (data / "notes.json").write_text("[]\n", encoding="utf-8")
        (data / "tasks.json").write_text("[]\n", encoding="utf-8")
        (data / "brain_versions" / "latest.json").write_text("{}\n", encoding="utf-8")
        (logs / "bot.log").write_text("", encoding="utf-8")
        (logs / "trace.jsonl").write_text("", encoding="utf-8")

        actions.DATA = data
        actions.LOGS = logs
        actions.NOTES_PATH = data / "notes.json"
        actions.TASKS_PATH = data / "tasks.json"
        actions.BRAIN_REPORT = data / "brain_versions" / "latest.json"
        actions.BOT_LOG = logs / "bot.log"
        actions.TRACE_LOG = logs / "trace.jsonl"
        tracer.TRACE_PATH = logs / "trace.jsonl"
        reverify.OUT_DIR = data / "brain_versions"

        web_app.app.config.update(TESTING=True)
        self.client = web_app.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.runtime, ignore_errors=True)

    def test_dashboard_and_static_assets(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Personal Bot Agent", response.data)
        response.close()
        for asset in ("/ui/styles.css", "/ui/app.js"):
            response = self.client.get(asset)
            self.assertEqual(response.status_code, 200, asset)
            response.close()

    def test_health_and_notes_api(self):
        health = self.client.get("/api/health")
        self.assertEqual(health.status_code, 200, health.get_data(as_text=True))
        self.assertIn("gemini_configured", health.get_json()["configuration"])
        self.assertEqual(self.client.get("/api/notes").get_json()["notes"], [])
        created = self.client.post("/api/notes", json={
            "title": "Smoke test note", "content": "Saved to isolated test storage", "tags": ["test"]
        })
        self.assertEqual(created.status_code, 201, created.get_data(as_text=True))
        self.assertEqual(len(self.client.get("/api/notes").get_json()["notes"]), 1)

    def test_task_create_list_and_complete(self):
        created = self.client.post("/api/tasks", json={"title": "Smoke test task", "priority": "high"})
        self.assertEqual(created.status_code, 201, created.get_data(as_text=True))
        task_id = created.get_json()["task"]["id"]
        listed = self.client.get("/api/tasks").get_json()["tasks"]
        self.assertEqual(len(listed), 1)
        completed = self.client.post(f"/api/tasks/{task_id}/complete")
        self.assertEqual(completed.status_code, 200, completed.get_data(as_text=True))
        self.assertTrue(completed.get_json()["task"]["completed"])

    def test_brain_verification_and_logs(self):
        brains = self.client.get("/api/brains")
        self.assertEqual(brains.status_code, 200, brains.get_data(as_text=True))
        self.assertEqual(len(brains.get_json()["snapshot"]["files"]), 7)
        verified = self.client.post("/api/brains/reverify")
        self.assertEqual(verified.status_code, 200, verified.get_data(as_text=True))
        self.assertTrue((self.runtime / "data/brain_versions/latest.json").is_file())
        logs = self.client.get("/api/logs")
        self.assertEqual(logs.status_code, 200, logs.get_data(as_text=True))
        self.assertIsInstance(logs.get_json()["traces"], list)

    def test_chat_fast_path_and_explicit_agent_fallback(self):
        fast = self.client.post("/api/chat", json={"message": "system status"})
        self.assertEqual(fast.status_code, 200, fast.get_data(as_text=True))
        self.assertEqual(fast.get_json()["handled_by"], "bot")
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            fallback = self.client.post("/api/chat", json={"message": "Explain the purpose of this personal assistant"})
        self.assertEqual(fallback.status_code, 200, fallback.get_data(as_text=True))
        self.assertEqual(fallback.get_json()["handled_by"], "planner")
        self.assertEqual(fallback.get_json()["meta"]["reason"], "missing_api_key")

    def test_gemini_error_redacts_api_key(self):
        secret = "unit-test-private-key"
        with patch.dict(os.environ, {"GEMINI_API_KEY": secret}):
            with patch.object(unified_brain, "_gemini_response", side_effect=RuntimeError(f"provider rejected {secret}")):
                result = unified_brain.handle_request("Please explain this project")
        self.assertNotIn(secret, result["reply"])
        self.assertNotIn(secret, json.dumps(result["meta"]))
        trace_text = (self.runtime / "logs/trace.jsonl").read_text(encoding="utf-8")
        self.assertNotIn(secret, trace_text)

    def test_invalid_payload_is_rejected(self):
        response = self.client.post("/api/chat", json={"message": ""})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.get_json()["ok"])
        malformed = self.client.post("/api/notes", data="{", content_type="application/json")
        self.assertEqual(malformed.status_code, 400)
        self.assertFalse(malformed.get_json()["ok"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
