"""Unified brain: grounded Gemini response when configured, explicit plan fallback otherwise."""
import json
import os
import re
from pathlib import Path

from bot.tracer import append_trace
from agent.planner import make_plan

BRAIN_DIR = Path(__file__).with_name("brains")
BRAIN_FILES = (
    "common_base.md", "notes_routine.md", "project_logic.md", "logs_issues.md",
    "research_live.md", "coding_security.md", "writing_drafts.md",
)


def load_brain(selected=None):
    names = list(selected) if selected else list(BRAIN_FILES)
    invalid = set(names) - set(BRAIN_FILES)
    if invalid:
        raise ValueError(f"Unknown brain document(s): {sorted(invalid)}")
    sections = []
    for name in names:
        path = BRAIN_DIR / name
        if not path.is_file() or not path.read_text(encoding="utf-8").strip():
            raise RuntimeError(f"Required brain document is missing or empty: {name}")
        sections.append(f"## {name}\n{path.read_text(encoding='utf-8').strip()}")
    return "\n\n".join(sections)


def _gemini_response(message, context, api_key, model):
    try:
        from google import genai
    except ImportError as exc:
        raise RuntimeError("google-genai package is unavailable; install requirements.txt") from exc
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=(
            "You are a grounded personal assistant. Follow the supplied project brain. "
            "Do not claim tools were run unless tool results are explicitly supplied. "
            "For coding and project work, structure the response as requirements, architecture, implementation, tests, and limitations. "
            "For failures, show observed evidence, root cause, corrective logic, regression checks, and verification results. "
            "Never claim code was executed or tests passed without actual tool output. "
            "If an operation is required, return JSON only in this schema: "
            '{"tool":"tool_name","arguments":{}}. Otherwise answer normally.\n\n'
            f"PROJECT BRAIN:\n{context}\n\nUSER REQUEST:\n{message}"
        ),
    )
    text = getattr(response, "text", None)
    if not isinstance(text, str) or not text.strip():
        raise RuntimeError("Gemini returned an empty response")
    return text.strip()


def _safe_error(exc, secret=""):
    message = str(exc)
    if secret:
        message = message.replace(secret, "[REDACTED]")
    return f"{type(exc).__name__}: {message[:500]}"


def handle_request(message):
    if not isinstance(message, str) or not message.strip() or len(message) > 8000:
        raise ValueError("message must contain 1-8000 characters")
    context = load_brain()
    plan = make_plan(message, context)
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
    if not api_key:
        append_trace("agent_fallback", {"reason": "GEMINI_API_KEY is not configured", "plan": plan}, source="agent.unified_brain")
        return {
            "reply": "GEMINI_API_KEY সেট করা নেই। তাই কোনো Gemini উত্তর তৈরি করা হয়নি। নিচে যাচাইযোগ্য execution plan দেওয়া হলো।",
            "intent": "agent",
            "handled_by": "planner",
            "data": {"plan": plan},
            "meta": {"ok": True, "mode": "explicit_fallback", "reason": "missing_api_key"},
        }
    try:
        response_text = _gemini_response(message, context, api_key, model)
        tool_result = None
        try:
            candidate = json.loads(response_text)
        except json.JSONDecodeError:
            candidate = None
        if isinstance(candidate, dict) and "tool" in candidate:
            from agent.tools import execute_tool
            tool_name = candidate.get("tool")
            arguments = candidate.get("arguments", {})
            tool_result = execute_tool(tool_name, arguments)
            response_text = json.dumps(tool_result, ensure_ascii=False, indent=2)
        append_trace("agent_response", {"model": model, "tool_executed": bool(tool_result)}, source="agent.unified_brain")
        return {
            "reply": response_text,
            "intent": "agent",
            "handled_by": "gemini",
            "data": {"tool_result": tool_result, "plan": plan},
            "meta": {"ok": True, "model": model, "mode": "gemini"},
        }
    except Exception as exc:
        safe_error = _safe_error(exc, api_key)
        append_trace("agent_fallback", {"reason": safe_error, "model": model, "plan": plan}, status="error", source="agent.unified_brain")
        return {
            "reply": f"Gemini API ব্যবহার করা যায়নি ({safe_error})। কোনো AI উত্তর বানিয়ে দেওয়া হয়নি। যাচাইযোগ্য execution plan দেওয়া হলো।",
            "intent": "agent",
            "handled_by": "planner",
            "data": {"plan": plan},
            "meta": {"ok": False, "mode": "fallback", "reason": safe_error},
        }
