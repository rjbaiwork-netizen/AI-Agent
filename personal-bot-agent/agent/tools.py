"""Typed tool registry and guarded executor for Agent operations."""
import concurrent.futures
import os
import time

from bot import actions
from bot.tracer import append_trace


def _reverify():
    from agent.reverify import reverify_all_brains
    return reverify_all_brains()


TOOL_REGISTRY = {
    "check_system_status": {"callable": actions.check_system_status, "required": (), "optional": ()},
    "list_notes": {"callable": actions.list_notes, "required": (), "optional": ()},
    "add_note": {"callable": actions.add_note, "required": ("title", "content"), "optional": ("tags",)},
    "list_tasks": {"callable": actions.list_tasks, "required": (), "optional": ("status",)},
    "add_task": {"callable": actions.add_task, "required": ("title",), "optional": ("priority", "due")},
    "complete_task": {"callable": actions.complete_task, "required": ("task_id",), "optional": ()},
    "reverify_all_brains": {"callable": _reverify, "required": (), "optional": ()},
    "tail_log": {"callable": actions.tail_log, "required": (), "optional": ("lines",)},
}


def execute_tool(name, arguments=None, timeout=None):
    if name not in TOOL_REGISTRY:
        raise ValueError(f"Unknown tool: {name}")
    arguments = arguments or {}
    if not isinstance(arguments, dict):
        raise ValueError("Tool arguments must be an object")
    spec = TOOL_REGISTRY[name]
    missing = [key for key in spec["required"] if key not in arguments]
    unknown = set(arguments) - set(spec["required"]) - set(spec["optional"])
    if missing or unknown:
        raise ValueError(f"Invalid arguments for {name}; missing={missing}, unknown={sorted(unknown)}")
    if timeout is None:
        try:
            timeout = int(os.getenv("GUARDRAIL_TIMEOUT_SEC", "60"))
        except ValueError as exc:
            raise ValueError("GUARDRAIL_TIMEOUT_SEC must be an integer") from exc
    if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= 600:
        raise ValueError("timeout must be an integer between 1 and 600")
    started = time.monotonic()
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="agent-tool")
    future = executor.submit(spec["callable"], **arguments)
    try:
        result = future.result(timeout=timeout)
        append_trace(
            "agent_tool",
            {"tool": name, "duration_ms": round((time.monotonic() - started) * 1000), "arguments": arguments},
            source="agent.tools",
        )
        return {"ok": True, "tool": name, "result": result}
    except concurrent.futures.TimeoutError as exc:
        future.cancel()
        append_trace("agent_tool", {"tool": name, "error": f"Timed out after {timeout}s"}, status="error", source="agent.tools")
        raise TimeoutError(
            f"Tool {name} exceeded {timeout} seconds; a running Python thread may finish in the background"
        ) from exc
    except Exception as exc:
        append_trace("agent_tool", {"tool": name, "error": str(exc)}, status="error", source="agent.tools")
        raise
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def available_tools():
    return {
        name: {"required": list(spec["required"]), "optional": list(spec["optional"])}
        for name, spec in TOOL_REGISTRY.items()
    }
