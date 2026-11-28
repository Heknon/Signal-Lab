// Learner progress: completed lessons, lessons marked "I know this", and the
// last lesson visited. Stored on the server (per account), cached locally so
// the first paint is instant. Nothing here gates navigation.
import { useSyncExternalStore } from "react";

export interface Progress {
  completed: Record<string, number>;
  known: Record<string, number>;
  last?: string | null;
}

const KEY = "sl-progress";
let state: Progress = loadCache();
const listeners = new Set<() => void>();

function loadCache(): Progress {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) return { completed: {}, known: {}, ...JSON.parse(raw) };
  } catch { /* storage unavailable */ }
  return { completed: {}, known: {} };
}

function set(next: Progress) {
  state = next;
  try { localStorage.setItem(KEY, JSON.stringify(next)); } catch { /* ignore */ }
  listeners.forEach((l) => l());
}

async function send(method: string, path: string, body?: unknown): Promise<Response | null> {
  try {
    return await fetch(path, { method, headers: { "content-type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) });
  } catch {
    return null;
  }
}

async function put(lessons: string[], value: "done" | "known" | null) {
  const r = await send("PUT", "/api/progress", { lessons, state: value });
  if (r?.ok) set({ ...(await r.json()) });
}

export const progress = {
  /** Replace the local cache with the server's copy (call after login). */
  async sync() {
    const r = await send("GET", "/api/progress");
    if (r?.ok) set({ ...(await r.json()) });
  },
  clearCache() { set({ completed: {}, known: {} }); },
  complete(id: string) {
    if (state.completed[id]) return;
    const known = { ...state.known };
    delete known[id];
    set({ ...state, completed: { ...state.completed, [id]: Date.now() }, known });
    void put([id], "done");
  },
  /** Back to "todo": clears done and known. */
  reset(id: string) {
    const completed = { ...state.completed };
    const known = { ...state.known };
    delete completed[id];
    delete known[id];
    set({ ...state, completed, known });
    void put([id], null);
  },
  setKnown(ids: string[], known: boolean) {
    const next = { ...state.known };
    for (const id of ids) {
      if (known && !state.completed[id]) next[id] = Date.now();
      else delete next[id];
    }
    set({ ...state, known: next });
    void put(ids.filter((id) => !state.completed[id]), known ? "known" : null);
  },
  visit(id: string) {
    if (state.last === id) return;
    set({ ...state, last: id });
    void send("PUT", "/api/progress/last", { lesson: id });
  },
};

export function useProgress(): Progress {
  return useSyncExternalStore((cb) => { listeners.add(cb); return () => listeners.delete(cb); }, () => state);
}

export type LessonState = "done" | "known" | "todo";
export const lessonState = (p: Progress, id: string): LessonState => (p.completed[id] ? "done" : p.known[id] ? "known" : "todo");

// Editor drafts: saved locally on every keystroke and to the server (debounced),
// so they follow you to another browser. A local edit the server hasn't confirmed
// yet is marked pending: on load it wins over the (older) server copy and is
// re-sent. Pending saves are also flushed when the page is hidden or closed.
const timers = new Map<string, number>();
const key = (id: string) => `sl-draft:${id}`;
const pendingKey = (id: string) => `sl-draft-pending:${id}`;
const local = {
  get: (k: string) => { try { return localStorage.getItem(k); } catch { return null; } },
  set: (k: string, v: string) => { try { localStorage.setItem(k, v); } catch { /* storage full or blocked */ } },
  del: (k: string) => { try { localStorage.removeItem(k); } catch { /* ignore */ } },
};

async function pushDraft(id: string, keepalive = false): Promise<void> {
  window.clearTimeout(timers.get(id));
  timers.delete(id);
  const code = local.get(key(id));
  if (code == null || local.get(pendingKey(id)) == null) return;
  try {
    const r = await fetch(`/api/drafts/${id}`, { method: "PUT", headers: { "content-type": "application/json" }, body: JSON.stringify({ code }), keepalive });
    // Only clear the mark if nothing changed while the request was in flight.
    if (r.ok && local.get(key(id)) === code) local.del(pendingKey(id));
  } catch { /* offline: stays pending, sent next time */ }
}

if (typeof window !== "undefined") {
  const flushAll = () => { for (const id of [...timers.keys()]) void pushDraft(id, true); };
  window.addEventListener("pagehide", flushAll);
  document.addEventListener("visibilitychange", () => { if (document.visibilityState === "hidden") flushAll(); });
}

export const drafts = {
  get(id: string): string | null {
    return local.get(key(id));
  },
  /** The draft to show: an unsynced local edit, else the server's copy, else the local one. */
  async fetch(id: string): Promise<string | null> {
    if (local.get(pendingKey(id)) != null) {
      void pushDraft(id);
      return local.get(key(id));
    }
    const r = await send("GET", `/api/drafts/${id}`);
    if (!r?.ok) return null;
    const { code } = await r.json();
    if (code != null) local.set(key(id), code);
    return code;
  },
  set(id: string, code: string) {
    local.set(key(id), code);
    local.set(pendingKey(id), "1");
    window.clearTimeout(timers.get(id));
    timers.set(id, window.setTimeout(() => void pushDraft(id), 800));
  },
  /** Save now (Ctrl/Cmd+S). */
  flush(id: string): Promise<void> {
    return pushDraft(id);
  },
  clear(id: string) {
    local.del(key(id));
    local.del(pendingKey(id));
    window.clearTimeout(timers.get(id));
    timers.delete(id);
    void send("DELETE", `/api/drafts/${id}`);
  },
};
