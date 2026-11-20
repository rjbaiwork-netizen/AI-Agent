from agent.tools import append_note, read_notes


def check_system_status():
    return {"status": "ok"}


def list_tasks():
    # Task storage is not configured yet; return an empty task list.
    return []


def execute(intent, payload):
    if intent == "notes":
        return {"ok": True, "note": append_note(str(payload.get("message", "")).strip())}
    if intent == "note_list":
        return {"ok": True, "notes": read_notes()}
    return {"ok": True, "intent": intent}
