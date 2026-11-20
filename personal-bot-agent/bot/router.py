"""Rule-based fast-path router with an explicit Agent fallback."""
import json
import re
from pathlib import Path

from bot import actions
from bot.tracer import append_trace

RULES_PATH = Path(__file__).with_name("rules.json")


def _load_rules():
    try:
        rules = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Unable to load routing rules: {exc}") from exc
    if not isinstance(rules.get("intents"), list):
        raise RuntimeError("rules.json must define an intents array")
    return rules


def _extract_after(message, patterns):
    lower = message.lower()
    for pattern in patterns:
        index = lower.find(pattern.lower())
        if index >= 0:
            return message[index + len(pattern):].strip(" :：-—\t\n")
    return ""


def _run_fast_action(intent, message):
    if intent == "system_status":
        result = actions.check_system_status()
        return "System check: " + result["status"], result
    if intent == "note_add":
        content = _extract_after(message, ["remember", "save note", "add note", "নোট রাখ", "মনে রাখ", "নোট লিখ"])
        if not content:
            content = message.strip()
        note = actions.add_note("Quick note", content)
        return f"নোট সংরক্ষণ হয়েছে: {note['title']}", note
    if intent == "note_list":
        notes = actions.list_notes()
        return f"মোট {len(notes)}টি নোট পাওয়া গেছে।", notes
    if intent == "task_add":
        title = _extract_after(message, ["add task", "new task", "create task", "টাস্ক যোগ", "কাজ যোগ", "নতুন কাজ"])
        task = actions.add_task(title or message)
        return f"টাস্ক তৈরি হয়েছে: {task['title']} (ID: {task['id']})", task
    if intent == "task_complete":
        match = re.search(r"(?:id\s*[:=]?\s*)?([a-f0-9]{12})", message, re.I)
        if not match:
            raise ValueError("টাস্ক সম্পন্ন করতে ১২-অক্ষরের Task ID দিন।")
        task = actions.complete_task(match.group(1))
        return f"টাস্ক সম্পন্ন: {task['title']}", task
    if intent == "task_list":
        tasks = actions.list_tasks()
        return f"মোট {len(tasks)}টি টাস্ক পাওয়া গেছে।", tasks
    if intent == "brain_verify":
        from agent.reverify import reverify_all_brains
        result = reverify_all_brains()
        return result.get("summary", "Brain verification completed."), result
    if intent == "brain_read":
        from agent.unified_brain import load_brain
        return load_brain(), {"brain_context_loaded": True}
    if intent == "logs_read":
        result = actions.tail_log()
        return "\n".join(result) if result else "লগ ফাইল এখনো খালি।", result
    if intent == "trace_read":
        from bot.tracer import read_traces
        result = read_traces()
        return f"সর্বশেষ {len(result)}টি trace record পাওয়া গেছে।", result
    raise ValueError(f"No fast action registered for {intent}")


def route(message):
    if not isinstance(message, str) or not message.strip():
        raise ValueError("message must be a non-empty string")
    if len(message) > 8000:
        raise ValueError("message cannot exceed 8000 characters")
    # Explicit JSON commands keep the chat interface usable without ambiguous free-text parsing.
    for prefix, operation in (("brain update ", "manual"), ("brain online ", "online")):
        if message.casefold().startswith(prefix):
            try:
                payload = json.loads(message[len(prefix):])
                if not isinstance(payload, dict):
                    raise ValueError("Command payload must be a JSON object")
                if operation == "manual":
                    from agent.brain_updates import update_topic
                    result = update_topic(payload.get("topic"), payload.get("content"), payload.get("brain_file", "project_logic.md"))
                else:
                    from agent.brain_updates import update_from_url
                    result = update_from_url(payload.get("topic"), payload.get("url"), payload.get("brain_file", "research_live.md"), payload.get("timeout", 12))
                append_trace("brain_chat_command", {"operation": operation, "brain_file": result.get("brain_file"), "topic": result.get("topic")}, source="bot.router")
                return {"reply": "ব্রেন আপডেট ও SHA-256 re-verification সফল হয়েছে।", "intent": "brain_update" if operation == "manual" else "brain_online_update", "handled_by": "bot", "data": result, "meta": {"ok": True}}
            except Exception as exc:
                append_trace("brain_chat_command", {"operation": operation, "error_type": type(exc).__name__, "error": str(exc)[:400]}, status="error", source="bot.router")
                return {"reply": f"ব্রেন আপডেট ব্যর্থ: {exc}", "intent": "brain_update" if operation == "manual" else "brain_online_update", "handled_by": "bot", "data": None, "meta": {"ok": False, "error": str(exc)}}
    rules = _load_rules()
    normalized = message.casefold()
    selected = None
    for rule in sorted(rules["intents"], key=lambda item: int(item.get("priority", 0)), reverse=True):
        if any(str(pattern).casefold() in normalized for pattern in rule.get("patterns", [])):
            selected = rule
            break
    if selected:
        intent = selected["name"]
        try:
            reply, data = _run_fast_action(intent, message)
            response = {"reply": reply, "intent": intent, "handled_by": "bot", "data": data, "meta": {"ok": True}}
            append_trace("routing_decision", {"intent": intent, "handled_by": "bot"}, source="bot.router")
            return response
        except Exception as exc:
            append_trace("routing_error", {"intent": intent, "error": str(exc)}, status="error", source="bot.router")
            return {"reply": f"অ্যাকশন সম্পন্ন করা যায়নি: {exc}", "intent": intent, "handled_by": "bot", "data": None, "meta": {"ok": False, "error": str(exc)}}
    append_trace("routing_decision", {"intent": "agent", "handled_by": "agent"}, source="bot.router")
    from agent.unified_brain import handle_request
    return handle_request(message)
