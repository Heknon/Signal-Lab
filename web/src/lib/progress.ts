// Learner progress lives in the browser: completed lessons, lessons marked
// "I know this", and the last lesson visited. Nothing here gates navigation.
import { useSyncExternalStore } from "react";

export interface Progress {
  completed: Record<string, number>;
  known: Record<string, number>;
  last?: string;
}

const KEY = "sl-progress";
let state: Progress = load();
const listeners = new Set<() => void>();

function load(): Progress {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) return { completed: {}, known: {}, ...JSON.parse(raw) };
  } catch { /* storage unavailable */ }
  return { completed: {}, known: {} };
}

function save(next: Progress) {
  state = next;
  try { localStorage.setItem(KEY, JSON.stringify(next)); } catch { /* ignore */ }
  listeners.forEach((l) => l());
}

export const progress = {
  complete(id: string) {
    if (state.completed[id]) return;
    const known = { ...state.known };
    delete known[id];
    save({ ...state, completed: { ...state.completed, [id]: Date.now() }, known });
  },
  setKnown(ids: string[], known: boolean) {
    const next = { ...state.known };
    for (const id of ids) {
      if (known && !state.completed[id]) next[id] = Date.now();
      else delete next[id];
    }
    save({ ...state, known: next });
  },
  visit(id: string) {
    if (state.last !== id) save({ ...state, last: id });
  },
  reset() { save({ completed: {}, known: {} }); },
};

export function useProgress(): Progress {
  return useSyncExternalStore(
    (cb) => { listeners.add(cb); return () => listeners.delete(cb); },
    () => state,
  );
}

export type LessonState = "done" | "known" | "todo";
export const lessonState = (p: Progress, id: string): LessonState => (p.completed[id] ? "done" : p.known[id] ? "known" : "todo");

// Per-lesson editor drafts.
export const drafts = {
  get(id: string): string | null {
    try { return localStorage.getItem(`sl-draft:${id}`); } catch { return null; }
  },
  set(id: string, code: string) {
    try { localStorage.setItem(`sl-draft:${id}`, code); } catch { /* ignore */ }
  },
  clear(id: string) {
    try { localStorage.removeItem(`sl-draft:${id}`); } catch { /* ignore */ }
  },
};
