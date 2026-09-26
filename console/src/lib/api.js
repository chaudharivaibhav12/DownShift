import { appState, connection, pending, lastError } from "./stores.js";
import { announce } from "./a11y.js";
import { oid } from "./format.js";

async function req(path, opts) {
  const r = await fetch(path, { headers: { "content-type": "application/json" }, ...opts });
  if (!r.ok) {
    const text = await r.text().catch(() => "");
    let detail = text;
    try { detail = JSON.parse(text).detail ?? text; } catch { /* not JSON */ }
    throw new Error(String(detail || `${r.status} ${r.statusText}`));
  }
  return r.json();
}

export async function refresh() {
  try {
    appState.set(await req("/api/state"));
    connection.set("live");
  } catch {
    connection.set("off");
  }
}

/* Per-answer detail (rows, steps) is fetched once and cached, as the original console did. */
const detail = new Map();
export async function answerDetail(id) {
  if (!id) return null;
  if (detail.has(id)) return detail.get(id);
  const a = await req("/api/answers/" + id);
  detail.set(id, a);
  return a;
}

export async function ask(question) {
  pending.set({ question, startedAt: Date.now() });
  try {
    const a = await req("/api/ask", { method: "POST", body: JSON.stringify({ question }) });
    detail.set(oid(a._id), a);
    return a;
  } finally {
    pending.set(null);
    await refresh();
  }
}

export const fetchRuns = () => req("/api/runs");
export const fetchRun = (id) => req("/api/runs/" + encodeURIComponent(id));

export const replay = () => req("/api/replay", { method: "POST" });
export const schemaChange = () => req("/api/schema-change", { method: "POST", body: "{}" });
export const reset = () => req("/api/reset", { method: "POST" });

/* The stream only says "something changed"; the state endpoint stays the source of truth. */
export function connect() {
  let t = null;
  const soon = () => {
    clearTimeout(t);
    t = setTimeout(refresh, 120);
  };
  const es = new EventSource("/api/stream");
  es.onopen = () => connection.set("live");
  es.onmessage = soon;
  es.onerror = () => connection.set("off");
  const safety = setInterval(refresh, 8000); // if the stream dies quietly
  return () => {
    es.close();
    clearInterval(safety);
    clearTimeout(t);
  };
}

export function toastError(e) {
  const message = e?.message || String(e);
  lastError.set({ message, at: Date.now() });
  announce(message);
  return message;
}
