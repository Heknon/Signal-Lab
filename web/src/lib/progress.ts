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

// Editor drafts: saved to the server (debounced), mirrored locally.
const timers = new Map<string, number>();
export const drafts = {
  get(id: string): string | null {
    try { return localStorage.getItem(`sl-draft:${id}`); } catch { return null; }
  },
  async fetch(id: string): Promise<string | null> {
    const r = await send("GET", `/api/drafts/${id}`);
    if (!r?.ok) return null;
    const { code } = await r.json();
    if (code != null) try { localStorage.setItem(`sl-draft:${id}`, code); } catch { /* ignore */ }
    return code;
  },
  set(id: string, code: string) {
    try { localStorage.setItem(`sl-draft:${id}`, code); } catch { /* ignore */ }
    window.clearTimeout(timers.get(id));
    timers.set(id, window.setTimeout(() => void send("PUT", `/api/drafts/${id}`, { code }), 800));
  },
  clear(id: string) {
    try { localStorage.removeItem(`sl-draft:${id}`); } catch { /* ignore */ }
    window.clearTimeout(timers.get(id));
    void send("DELETE", `/api/drafts/${id}`);
  },
};
