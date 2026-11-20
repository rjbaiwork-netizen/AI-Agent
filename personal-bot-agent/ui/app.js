"use strict";
const $ = (id) => document.getElementById(id);
const state = { busy: new Set(), notes: [], tasks: [], brains: null, logs: null };

async function api(path, options = {}) {
  const config = { ...options, headers: { ...(options.body ? { "Content-Type": "application/json" } : {}), ...(options.headers || {}) } };
  const response = await fetch(path, config);
  const type = response.headers.get("content-type") || "";
  const payload = type.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const message = payload && typeof payload === "object" ? (payload.error || payload.reply || payload.message) : payload;
    throw new Error(message || `Request failed (HTTP ${response.status})`);
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
  setBusy("refresh-status", true, "Refreshing…");
  try {
    const data = await api("/api/health");
    $("health-label").textContent = data.status || (data.ok ? "System healthy" : "System degraded");
    $("health-indicator").className = "status-dot " + (data.ok ? "ok" : "error");
    const config = data.configuration || {};
    $("gemini-label").textContent = "Gemini: " + (config.gemini_configured ? "configured" : "not configured");
    if (!data.ok) showError((data.system?.errors || []).join(" · ") || "System health is degraded.");
    else clearError();
  } catch (error) {
    $("health-label").textContent = "Backend unavailable";
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
  try { const data = await api("/api/notes"); state.notes = Array.isArray(data.notes) ? data.notes : []; renderNotes(); }
  catch (error) { showEmpty("notes-list", error.message); showError(error.message); }
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
  try { const data = await api("/api/tasks"); state.tasks = Array.isArray(data.tasks) ? data.tasks : []; renderTasks(); }
  catch (error) { showEmpty("tasks-list", error.message); showError(error.message); }
}
async function refreshBrains() {
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
    $("brain-report").textContent = JSON.stringify(data.snapshot, null, 2);
  } catch (error) {
    showEmpty("brains-list", error.message);
    $("brain-report").textContent = error.message;
  }
}
async function refreshLogs() {
  try {
    const data = await api("/api/logs?lines=100&traces=100");
    state.logs = data;
    $("bot-log").textContent = (data.bot_log || []).join("\n") || "No log entries.";
    $("trace-log").textContent = (data.traces || []).map((item) => JSON.stringify(item)).join("\n") || "No trace entries.";
  } catch (error) {
    $("bot-log").textContent = error.message;
    $("trace-log").textContent = error.message;
  }
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
$("refresh-status").addEventListener("click", refreshHealth);
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
  await Promise.allSettled([refreshHealth(), refreshNotes(), refreshTasks(), refreshBrains(), refreshLogs()]);
}
initialize();
