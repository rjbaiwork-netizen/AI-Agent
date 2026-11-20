"""Bounded, transparent execution planning without fabricating outcomes."""
import os
from datetime import datetime, timezone

DEFAULT_MAX_STEPS = 10
DEFAULT_TIMEOUT = 60


def _positive_env(name, default, maximum):
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not 1 <= value <= maximum:
        raise ValueError(f"{name} must be between 1 and {maximum}")
    return value


def make_plan(task, brain_context="", max_steps=None, timeout_sec=None):
    if not isinstance(task, str) or not task.strip():
        raise ValueError("task must be a non-empty string")
    if max_steps is None:
        max_steps = _positive_env("GUARDRAIL_MAX_STEPS", DEFAULT_MAX_STEPS, 50)
    if timeout_sec is None:
        timeout_sec = _positive_env("GUARDRAIL_TIMEOUT_SEC", DEFAULT_TIMEOUT, 600)
    if isinstance(max_steps, bool) or not isinstance(max_steps, int) or not 1 <= max_steps <= 50:
        raise ValueError("max_steps must be between 1 and 50")
    if isinstance(timeout_sec, bool) or not isinstance(timeout_sec, int) or not 1 <= timeout_sec <= 600:
        raise ValueError("timeout_sec must be between 1 and 600")
    steps = [
        {"step": 1, "action": "Understand the requested outcome and identify constraints.", "status": "planned"},
        {"step": 2, "action": "Select relevant brain guidance and available tools.", "status": "planned"},
        {"step": 3, "action": "Execute only authorized, verifiable operations.", "status": "planned"},
        {"step": 4, "action": "Validate results and report evidence, limitations, and errors.", "status": "planned"},
    ][:max_steps]
    return {
        "task": task.strip(),
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "steps": steps,
        "guardrails": {"max_steps": max_steps, "timeout_sec": timeout_sec},
        "brain_context_loaded": bool(brain_context.strip()) if isinstance(brain_context, str) else False,
    }
