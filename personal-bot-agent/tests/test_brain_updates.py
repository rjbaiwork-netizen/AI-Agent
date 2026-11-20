"""Unit tests for topic-based and live online brain updates."""
import os
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

from agent import brain_updates, reverify

class BrainUpdateTests(unittest.TestCase):
    def setUp(self):
        self.runtime = Path(__file__).resolve().parents[1] / ".brain-test-runtime"
        shutil.rmtree(self.runtime, ignore_errors=True)
        self.runtime.mkdir(parents=True)
        self.original_dir = brain_updates.BRAIN_DIR
        self.original_report_dir = reverify.OUT_DIR
        self.original_log = brain_updates.BOT_LOG
        self.original_trace = __import__("bot.tracer", fromlist=["TRACE_PATH"]).TRACE_PATH
        brain_updates.BRAIN_DIR = self.runtime / "brains"
        brain_updates.BRAIN_DIR.mkdir()
        for name in reverify.REQUIRED_BRAINS:
            (brain_updates.BRAIN_DIR / name).write_text(f"# {name}\n\nExisting verified content.\n", encoding="utf-8")
        reverify.BRAIN_DIR = brain_updates.BRAIN_DIR
        reverify.OUT_DIR = self.runtime / "versions"
        brain_updates.BOT_LOG = self.runtime / "logs" / "bot.log"
        from bot import tracer
        tracer.TRACE_PATH = self.runtime / "logs" / "trace.jsonl"

    def tearDown(self):
        brain_updates.BRAIN_DIR = self.original_dir
        reverify.BRAIN_DIR = self.original_dir
        reverify.OUT_DIR = self.original_report_dir
        brain_updates.BOT_LOG = self.original_log
        from bot import tracer
        tracer.TRACE_PATH = self.original_trace
        shutil.rmtree(self.runtime, ignore_errors=True)

    def test_topic_update_writes_hash_report_and_valid_logs(self):
        result = brain_updates.update_topic("Flask request validation", "Validate JSON types and request sizes.", "coding_security.md")
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["sha256"]), 64)
        self.assertIn("## Learned topic: Flask request validation", (brain_updates.BRAIN_DIR / "coding_security.md").read_text(encoding="utf-8"))
        import json
        report = json.loads((reverify.OUT_DIR / "latest.json").read_text(encoding="utf-8"))
        self.assertTrue(report["ok"])
        for line in (self.runtime / "logs" / "trace.jsonl").read_text(encoding="utf-8").splitlines():
            json.loads(line)
        self.assertIn("brain_topic_update", (self.runtime / "logs" / "bot.log").read_text(encoding="utf-8"))

    def test_invalid_input_duplicate_and_secret_rejected(self):
        for kwargs in (
            {"topic": "", "content": "body"},
            {"topic": "topic", "content": ""},
            {"topic": "topic", "content": "api_key=abcdefghijklmno"},
            {"topic": "topic", "content": "valid", "brain_file": "../secrets.txt"},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                brain_updates.update_topic(**kwargs)
        brain_updates.update_topic("unique topic", "valid knowledge")
        with self.assertRaises(ValueError):
            brain_updates.update_topic("unique topic", "different content")

    def test_live_update_success_extracts_html_and_reverifies(self):
        with patch.dict(os.environ, {"ALLOW_LIVE_FETCH": "true"}), patch.object(brain_updates.socket, "getaddrinfo", return_value=[(None, None, None, None, ("93.184.216.34", 443))]):
            with patch.object(brain_updates, "_download_source", return_value=("text/html", "<html><title>Official Docs</title><script>ignore()</script><p>Verified API usage guidance.</p></html>", "https://docs.example.org/page")):
                result = brain_updates.update_from_url("API documentation", "https://docs.example.org/page", "research_live.md")
        self.assertTrue(result["ok"])
        saved = (brain_updates.BRAIN_DIR / "research_live.md").read_text(encoding="utf-8")
        self.assertIn("Official Docs", saved)
        self.assertIn("Verified API usage guidance.", saved)
        self.assertNotIn("ignore()", saved)

    def test_live_update_disabled_invalid_url_timeout_and_bad_content(self):
        with patch.dict(os.environ, {"ALLOW_LIVE_FETCH": "false"}):
            with self.assertRaises(PermissionError):
                brain_updates.update_from_url("topic", "https://docs.example.org")
        with patch.dict(os.environ, {"ALLOW_LIVE_FETCH": "true"}), patch.object(brain_updates.socket, "getaddrinfo", return_value=[(None, None, None, None, ("93.184.216.34", 443))]):
            for url in ("http://docs.example.org", "https://localhost/admin", "https://user:pass@docs.example.org"):
                with self.subTest(url=url), self.assertRaises(ValueError):
                    brain_updates.update_from_url("topic", url)
            with patch.object(brain_updates, "_download_source", side_effect=TimeoutError("request timeout")):
                with self.assertRaises(TimeoutError):
                    brain_updates.update_from_url("timeout topic", "https://docs.example.org")
            with patch.object(brain_updates, "_download_source", return_value=("application/json", "{broken", "https://docs.example.org")):
                with self.assertRaises(ValueError):
                    brain_updates.update_from_url("bad json", "https://docs.example.org")

if __name__ == "__main__":
    unittest.main(verbosity=2)
