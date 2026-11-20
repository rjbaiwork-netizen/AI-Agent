"use strict";
const $ = (id) => document.getElementById(id);
const state = { busy: new Set(), notes: [], tasks: [], brains: null, logs: null, backendUrl: "" };
const BACKEND_STORAGE_KEY = "personal-bot-agent-backend-url";
const isPagesHost = location.hostname === "rjbaiwork-netizen.github.io";
function normalizeBackendUrl(value) {
  const trimmed = String(value || "").trim();
  if (!trimmed) throw new Error("Enter your Flask backend URL.");
  let parsed;
  try { parsed = new URL(trimmed); } catch (_) { throw new Error("Backend URL is invalid. Paste the complete HTTPS Codespaces forwarded URL."); }
  if (!["https:", "http:"].includes(parsed.protocol) || parsed.username || parsed.password || parsed.search || parsed.hash) {
    throw new Error("Use a valid backend URL without username, password, query string or fragment.");
  }
  if (parsed.protocol !== "https:" && !["localhost", "127.0.0.1", "[::1]"].includes(parsed.hostname)) {
    throw new Error("Remote Codespaces backend URLs must use HTTPS.");
  }
  const cleanPath = parsed.pathname.split("/").filter(Boolean).join("/");
  const normalizedPath = cleanPath ? "/" + cleanPath : "";
  return parsed.origin + normalizedPath;
}
function updateBackendStatus(message, connected = false) {
  $("backend-connection-state").textContent = connected ? "Connected" : (state.backendUrl ? "Configured · offline" : "Not connected");
  $("backend-connection-state").className = connected ? "status-pill connected" : "status-pill";
  $("backend-help").textContent = message;
}
function loadBackendUrl() {
  let saved = "";
  try { saved = localStorage.getItem(BACKEND_STORAGE_KEY) || ""; }
  catch (_) { updateBackendStatus("This browser blocks local storage. Enable site storage to remember the backend URL."); }
  if (saved) {
    try { state.backendUrl = normalizeBackendUrl(saved); }
    catch (error) {
      state.backendUrl = "";
      try { localStorage.removeItem(BACKEND_STORAGE_KEY); } catch (_) {}
      updateBackendStatus("The previously saved backend URL was invalid and has been cleared: " + error.message);
    }
  } else if (!isPagesHost && !state.backendUrl) {
    state.backendUrl = location.origin;
  }
  $("backend-url").value = state.backendUrl;
  if (state.backendUrl) updateBackendStatus("Saved backend URL loaded. Checking /api/health…");
  else updateBackendStatus("Backend not configured. Connect a running Flask server.");
}
async function api(path, options = {}) {
  if (!state.backendUrl) throw new Error("Backend not connected. Enter and save your Codespaces forwarded URL first.");
  const config = { ...options, headers: { ...(options.body ? { "Content-Type": "application/json" } : {}), ...(options.headers || {}) } };
  let response;
  try {
    response = await fetch(state.backendUrl + path, { ...config, mode: "cors", credentials: "include" });
  } catch (error) {
    throw new Error("Could not reach the backend. Check that Flask is running, port 8000 is forwarded, and the URL is correct. A CORS or Codespaces port-privacy restriction may also block the request. " + (error?.message || ""));
  }
  const contentType = response.headers.get("content-type") || "";
  let payload;
  if (contentType.toLowerCase().includes("application/json")) {
    try { payload = await response.json(); }
    catch (_) { throw new Error("Backend returned invalid JSON (HTTP " + response.status + ")."); }
  } else {
    payload = await response.text();
  }
  if (!response.ok) {
    const detail = payload && typeof payload === "object" ? (payload.error || payload.reply || payload.message) : payload;
    throw new Error((detail && String(detail).trim()) || ("Backend request failed (HTTP " + response.status + ")."));
  }
  if (!contentType.toLowerCase().includes("application/json")) {
    throw new Error("Backend returned a non-JSON response (HTTP " + response.status + "). Check the URL and Flask API route.");
  }
  return payload;
}
function setBusy(id, busy, label) {
  const element = $(id);
  if (!element) return;
  element.disabled = busy;
  if (label) {
    if (busy) { element.dataset.originalLabel = element.textContent; element.textContent = label; }
    else if (element.dataset.originalLabel) { element.textContent = element.dataset.originalLabel; delete element.dataset.originalLabel; }
  }
}
function showError(message) {
  $("global-error").textContent = message;
  $("global-error").classList.remove("hidden");
}
function clearError() { $("global-error").textContent = ""; $("global-error").classList.add("hidden"); }
function showEmpty(target, message) { $(target).replaceChildren(Object.assign(document.createElement("p"), { className: "muted", textContent: message })); }
function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
async function refreshHealth() {
  if (!state.backendUrl) {
    $("health-label").textContent = "Backend not connected";
    $("health-indicator").className = "status-dot warning";
    $("gemini-label").textContent = "Gemini: unavailable";
    updateBackendStatus("Static frontend is loaded. Connect the Flask backend to enable API features.");
    return;
  }
  setBusy("refresh-status", true, "Refreshing…");
  try {
    const data = await api("/api/health");
    $("health-label").textContent = data.status || (data.ok ? "System healthy" : "System degraded");
    $("health-indicator").className = "status-dot " + (data.ok ? "ok" : "error");
    updateBackendStatus(data.ok ? "Backend health check succeeded." : "Backend responded, but its health check reports a problem.", Boolean(data.ok));
    const config = data.configuration || {};
    $("gemini-label").textContent = "Gemini: " + (config.gemini_configured ? "configured" : "not configured");
    if (!data.ok) showError((data.system?.errors || []).join(" · ") || "System health is degraded.");
    else clearError();
  } catch (error) {
    $("health-label").textContent = "Backend unavailable";
    updateBackendStatus("Could not reach backend: " + error.message + ". Check that Flask is running and the Codespaces port is accessible.");
    $("health-indicator").className = "status-dot error";
    $("gemini-label").textContent = "Gemini: unknown";
    showError(error.message);
  } finally { setBusy("refresh-status", false); }
}
function renderChat(data) {
  $("chat-response").textContent = data.reply || "The API returned no reply text.";
  $("response-status").textContent = data.ok ? "Completed" : "Needs attention";
  $("chat-state").textContent = data.handled_by || "Agent";
  const meta = $("chat-meta");
  meta.replaceChildren();
  for (const [label, value] of [["Intent", data.intent], ["Handled by", data.handled_by], ["Mode", data.meta?.mode], ["Model", data.meta?.model]]) {
    if (value) meta.append(element("span", "", `${label}: ${value}`));
  }
  const steps = $("plan-steps");
  steps.replaceChildren();
  const planSteps = data.plan?.steps || data.data?.plan?.steps || [];
  for (const step of planSteps) steps.append(element("li", "", step.action || JSON.stringify(step)));
}
async function sendChat(message) {
  setBusy("send-chat", true, "Working…");
  $("chat-state").textContent = "Processing";
  $("response-status").textContent = "Loading…";
  try {
    const data = await api("/api/chat", { method: "POST", body: JSON.stringify({ message }) });
    renderChat(data);
    await Promise.allSettled([refreshHealth(), refreshLogs()]);
  } catch (error) {
    $("chat-response").textContent = error.message;
    $("response-status").textContent = "Error";
    showError(error.message);
  } finally { setBusy("send-chat", false); $("chat-state").textContent = "Ready"; }
}
function renderNotes() {
  $("notes-count").textContent = String(state.notes.length);
  const list = $("notes-list"); list.replaceChildren();
  if (!state.notes.length) return showEmpty("notes-list", "No notes saved yet.");
  for (const note of [...state.notes].reverse()) {
    const card = element("article", "record");
    card.append(element("h3", "", note.title || "Untitled note"));
    card.append(element("p", "", note.content || note.text || ""));
    const tags = Array.isArray(note.tags) ? note.tags.join(", ") : "";
    card.append(element("small", "", [tags, note.created_at || ""].filter(Boolean).join(" · ")));
    list.append(card);
  }
}
async function refreshNotes() {
  setBusy("refresh-notes", true, "Refreshing…");
  try { const data = await api("/api/notes"); state.notes = Array.isArray(data.notes) ? data.notes : []; renderNotes(); }
  catch (error) { showEmpty("notes-list", error.message); showError(error.message); }
  finally { setBusy("refresh-notes", false); }
}
function renderTasks() {
  $("tasks-count").textContent = String(state.tasks.length);
  const list = $("tasks-list"); list.replaceChildren();
  if (!state.tasks.length) return showEmpty("tasks-list", "No tasks created yet.");
  for (const task of [...state.tasks].reverse()) {
    const card = element("article", "record");
    card.append(element("h3", "", task.title || "Untitled task"));
    card.append(element("small", "", `Priority: ${task.priority || "normal"} · ${task.due ? "Due: " + task.due + " · " : ""}${task.completed ? "Completed" : "Open"} · ID: ${task.id}`));
    const actions = element("div", "record-actions");
    actions.append(element("span", task.completed ? "badge ok" : "priority", task.completed ? "DONE" : String(task.priority || "normal").toUpperCase()));
    if (!task.completed) {
      const button = element("button", "button small secondary", "Complete");
      button.type = "button";
      button.addEventListener("click", async () => {
        button.disabled = true;
        try { await api(`/api/tasks/${encodeURIComponent(task.id)}/complete`, { method: "POST" }); await refreshTasks(); await refreshLogs(); }
        catch (error) { button.disabled = false; showError(error.message); }
      });
      actions.append(button);
    }
    card.append(actions); list.append(card);
  }
}
async function refreshTasks() {
  setBusy("refresh-tasks", true, "Refreshing…");
  try { const data = await api("/api/tasks"); state.tasks = Array.isArray(data.tasks) ? data.tasks : []; renderTasks(); }
  catch (error) { showEmpty("tasks-list", error.message); showError(error.message); }
  finally { setBusy("refresh-tasks", false); }
}
async function refreshBrains() {
  setBusy("refresh-brains", true, "Refreshing…");
  try {
    const data = await api("/api/brains");
    state.brains = data.snapshot;
    const list = $("brains-list"); list.replaceChildren();
    for (const [name, info] of Object.entries(data.snapshot?.files || {})) {
      const item = element("div", "brain-item");
      item.append(element("span", "", name));
      item.append(element("span", "badge " + (info.status === "verified" ? "ok" : "error"), info.status));
      list.append(item);
    }
    if (!list.children.length) showEmpty("brains-list", "The backend returned no brain-file records.");
    $("brain-report").textContent = JSON.stringify(data.snapshot, null, 2);
  } catch (error) {
    showEmpty("brains-list", error.message);
    $("brain-report").textContent = error.message;
  } finally { setBusy("refresh-brains", false); }
}
async function refreshLogs() {
  setBusy("refresh-logs", true, "Refreshing…");
  try {
    const data = await api("/api/logs?lines=100&traces=100");
    state.logs = data;
    $("bot-log").textContent = (data.bot_log || []).join("\n") || "No log entries.";
    $("trace-log").textContent = (data.traces || []).map((item) => JSON.stringify(item)).join("\n") || "No trace entries.";
  } catch (error) {
    $("bot-log").textContent = error.message;
    $("trace-log").textContent = error.message;
  } finally { setBusy("refresh-logs", false); }
}
$("chat-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = $("chat-message").value.trim();
  if (!message) return;
  await sendChat(message);
});
document.querySelectorAll("[data-command]").forEach((button) => button.addEventListener("click", () => {
  $("chat-message").value = button.dataset.command;
  sendChat(button.dataset.command);
}));
$("note-form").addEventListener("submit", async (event) => {
  event.preventDefault(); clearError(); setBusy("save-note", true, "Saving…");
  try {
    const tags = $("note-tags").value.split(",").map((tag) => tag.trim()).filter(Boolean);
    await api("/api/notes", { method: "POST", body: JSON.stringify({ title: $("note-title").value, content: $("note-content").value, tags }) });
    $("note-form").reset(); await refreshNotes(); await refreshLogs();
  } catch (error) { showError(error.message); }
  finally { setBusy("save-note", false); }
});
$("task-form").addEventListener("submit", async (event) => {
  event.preventDefault(); clearError(); setBusy("save-task", true, "Adding…");
  try {
    await api("/api/tasks", { method: "POST", body: JSON.stringify({ title: $("task-title").value, priority: $("task-priority").value, due: $("task-due").value.trim() || null }) });
    $("task-form").reset(); await refreshTasks(); await refreshLogs();
  } catch (error) { showError(error.message); }
  finally { setBusy("save-task", false); }
});
$("backend-form").addEventListener("submit", async (event) => {
  event.preventDefault(); clearError();
  try {
    const candidate = normalizeBackendUrl($("backend-url").value);
    localStorage.setItem(BACKEND_STORAGE_KEY, candidate);
    state.backendUrl = candidate;
    $("backend-url").value = candidate;
    updateBackendStatus("Backend URL saved. Testing /api/health…");
    await refreshHealth();
    if ($("backend-connection-state").textContent === "Connected") {
      await Promise.allSettled([refreshNotes(), refreshTasks(), refreshBrains(), refreshLogs()]);
    }
  } catch (error) {
    updateBackendStatus(error.message);
    showError(error.message);
  }
});
$("disconnect-backend").addEventListener("click", async () => {
  clearError();
  try {
    const saved = localStorage.getItem(BACKEND_STORAGE_KEY) || "";
    if (!saved) throw new Error("No saved backend URL is available to restore.");
    state.backendUrl = normalizeBackendUrl(saved);
    $("backend-url").value = state.backendUrl;
    updateBackendStatus("Restored saved backend URL. Testing /api/health…");
    await refreshHealth();
    if ($("backend-connection-state").textContent === "Connected") {
      await Promise.allSettled([refreshNotes(), refreshTasks(), refreshBrains(), refreshLogs()]);
    }
  } catch (error) { updateBackendStatus(error.message); showError(error.message); }
});
$("clear-backend").addEventListener("click", async () => {
  clearError();
  try { localStorage.removeItem(BACKEND_STORAGE_KEY); }
  catch (_) { showError("Could not clear the saved backend URL because browser storage is unavailable."); return; }
  state.backendUrl = "";
  $("backend-url").value = "";
  await refreshHealth();
});

function setBrainUpdateStatus(message, success = false) {
  $("brain-update-status").textContent = message;
  $("brain-update-status").className = "backend-help" + (success ? " success" : "");
}
$("brain-update-form").addEventListener("submit", async (event) => {
  event.preventDefault(); clearError(); setBusy("save-brain-update", true, "Saving & verifying…");
  try {
    const data = await api("/api/brains/update", { method: "POST", body: JSON.stringify({
      topic: $("brain-topic").value, brain_file: $("brain-file").value, content: $("brain-content").value
    }) });
    setBrainUpdateStatus("Saved and verified: " + data.result.brain_file + " · SHA-256 " + data.result.sha256, true);
    $("brain-content").value = "";
    await Promise.allSettled([refreshBrains(), refreshLogs(), refreshHealth()]);
  } catch (error) { setBrainUpdateStatus("Update failed: " + error.message); showError(error.message); }
  finally { setBusy("save-brain-update", false); }
});
$("brain-online-form").addEventListener("submit", async (event) => {
  event.preventDefault(); clearError(); setBusy("fetch-brain-source", true, "Fetching source…");
  try {
    const data = await api("/api/brains/update-online", { method: "POST", body: JSON.stringify({
      topic: $("online-topic").value, url: $("online-url").value, brain_file: $("online-brain-file").value, timeout: 12
    }) });
    setBrainUpdateStatus("Source retrieved and saved: " + data.result.brain_file + " · " + data.result.characters_saved + " characters · SHA-256 " + data.result.sha256, true);
    await Promise.allSettled([refreshBrains(), refreshLogs(), refreshHealth()]);
  } catch (error) { setBrainUpdateStatus("Online update failed: " + error.message); showError(error.message); }
  finally { setBusy("fetch-brain-source", false); }
});
\n$("refresh-status").addEventListener("click", refreshHealth);
$("refresh-notes").addEventListener("click", refreshNotes);
$("refresh-tasks").addEventListener("click", refreshTasks);
$("refresh-brains").addEventListener("click", refreshBrains);
$("refresh-logs").addEventListener("click", refreshLogs);
$("reverify-brains").addEventListener("click", async () => {
  clearError(); setBusy("reverify-brains", true, "Verifying…");
  try {
    const data = await api("/api/brains/reverify", { method: "POST" });
    $("brain-report").textContent = JSON.stringify(data.result?.report || data.result, null, 2);
    await Promise.allSettled([refreshBrains(), refreshLogs(), refreshHealth()]);
  } catch (error) { showError(error.message); }
  finally { setBusy("reverify-brains", false); }
});
document.querySelectorAll("[data-tab]").forEach((button) => button.addEventListener("click", () => {
  document.querySelectorAll("[data-tab]").forEach((tab) => { const active = tab === button; tab.classList.toggle("active", active); tab.setAttribute("aria-selected", String(active)); });
  document.querySelectorAll(".tab-panel").forEach((panel) => panel.classList.toggle("hidden", panel.id !== button.dataset.tab));
}));
async function initialize() {
  loadBackendUrl();
  await refreshHealth();
  if ($("backend-connection-state").textContent === "Connected") {
    await Promise.allSettled([refreshNotes(), refreshTasks(), refreshBrains(), refreshLogs()]);
  } else {
    showEmpty("notes-list", "Connect the Flask backend to load saved notes.");
    showEmpty("tasks-list", "Connect the Flask backend to load tasks.");
    showEmpty("brains-list", "Connect the Flask backend to verify the seven brain files.");
    $("brain-report").textContent = "Backend not connected.";
    $("bot-log").textContent = "Connect the backend to view bot.log.";
    $("trace-log").textContent = "Connect the backend to view trace.jsonl.";
  }
}
initialize();
