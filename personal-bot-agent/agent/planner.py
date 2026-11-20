"""Bounded, transparent task planning with coding and root-cause workflows."""
import os
from datetime import datetime, timezone

DEFAULT_MAX_STEPS = 10
DEFAULT_TIMEOUT = 60
_CODING_TERMS = ("code", "coding", "program", "programming", "debug", "bug", "api", "database", "frontend", "backend", "স্ক্রিপ্ট", "কোড", "প্রোগ্রাম")
_PROJECT_TERMS = ("project", "scaffold", "architecture", "build app", "create app", "প্রজেক্ট", "অ্যাপ তৈরি")
_PROBLEM_TERMS = ("problem", "issue", "error", "failure", "root cause", "সমস্যা", "ত্রুটি", "সমাধান")

def _positive_env(name, default, maximum):
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not 1 <= value <= maximum:
        raise ValueError(f"{name} must be between 1 and {maximum}")
    return value

def _task_type(task):
    value = task.casefold()
    if any(term in value for term in _PROJECT_TERMS):
        return "project_build"
    if any(term in value for term in _CODING_TERMS):
        return "coding"
    if any(term in value for term in _PROBLEM_TERMS):
        return "problem_solving"
    return "general"

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
    task_type = _task_type(task)
    if task_type == "project_build":
        actions = [
            "Define project requirements, user flows, constraints, and acceptance criteria.",
            "Design the architecture, data model, interfaces, and security boundaries.",
            "Break the project into implementable components and identify dependencies.",
            "Implement only the requested components using the supplied brain guidance.",
            "Run relevant tests, inspect failures, and verify the delivered files and behavior.",
            "Report changed files, exact test evidence, assumptions, and remaining limitations.",
        ]
    elif task_type == "coding":
        actions = [
            "Clarify expected behavior, inputs, outputs, constraints, and runtime.",
            "Inspect relevant brain patterns, existing interfaces, dependencies, and security rules.",
            "Design the smallest maintainable implementation and handle edge cases.",
            "Implement code without executing untrusted generated content.",
            "Run syntax, unit, integration, and regression checks appropriate to the change.",
            "Report code, changed files, actual verification evidence, and known limitations.",
        ]
    elif task_type == "problem_solving":
        actions = [
            "Reproduce or precisely define the observed failure and expected result.",
            "Collect logs, state, inputs, and environmental evidence without exposing secrets.",
            "Identify the root cause and distinguish evidence from hypotheses.",
            "Choose a minimal corrective action and define regression protection.",
            "Apply or describe the fix, then verify with repeatable checks.",
            "Report root cause, logic, evidence, and any unresolved uncertainty.",
        ]
    else:
        actions = [
            "Understand the requested outcome and identify constraints.",
            "Select relevant brain guidance and available tools.",
            "Execute only authorized, verifiable operations.",
            "Validate results and report evidence, limitations, and errors.",
        ]
    steps = [{"step": index, "action": action, "status": "planned"} for index, action in enumerate(actions[:max_steps], 1)]
    return {
        "task": task.strip(),
        "task_type": task_type,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "steps": steps,
        "guardrails": {"max_steps": max_steps, "timeout_sec": timeout_sec},
        "brain_context_loaded": bool(brain_context.strip()) if isinstance(brain_context, str) else False,
    }
