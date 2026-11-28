import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Load data for `deps`, optionally polling every `intervalMs`.
 *
 * - When deps change, the new request always runs, and results of older requests
 *   are dropped: responses can arrive out of order (A -> B -> C with B slowest
 *   must not show B at C). `data` is cleared, so callers never render the
 *   previous deps' data as if it were current.
 * - Polls never stack: a tick is skipped while a request is in flight (browsers
 *   allow only 6 connections per host), and polling pauses in hidden tabs.
 */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[], intervalMs?: number) {
  const [data, setData] = useState<T | undefined>();
  const [error, setError] = useState<Error | undefined>();
  const [loading, setLoading] = useState(true);
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const gen = useRef(0);
  const inFlight = useRef(false);
  const load = useCallback((g: number) => {
    inFlight.current = true;
    return fnRef.current().then(
      (d) => { if (g === gen.current) { setData(d); setError(undefined); } },
      (e: Error) => { if (g === gen.current) setError(e); },
    ).finally(() => { if (g === gen.current) { setLoading(false); inFlight.current = false; } });
  }, []);
  const reload = useCallback(() => load(gen.current), [load]);
  useEffect(() => {
    const g = ++gen.current;
    setData(undefined);
    setError(undefined);
    setLoading(true);
    load(g);
    if (!intervalMs) return;
    const id = window.setInterval(() => {
      if (document.visibilityState === "visible" && !inFlight.current) load(g);
    }, intervalMs);
    return () => window.clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return { data, error, loading, reload, setData };
}

export function useLocalState<T>(key: string, initial: T): [T, (v: T) => void] {
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = localStorage.getItem(key);
      return raw == null ? initial : (JSON.parse(raw) as T);
    } catch { return initial; }
  });
  const set = useCallback((v: T) => {
    setValue(v);
    try { localStorage.setItem(key, JSON.stringify(v)); } catch { /* ignore */ }
  }, [key]);
  return [value, set];
}

export function useHotkey(combo: string, handler: (e: KeyboardEvent) => void, enabled = true) {
  const ref = useRef(handler);
  ref.current = handler;
  useEffect(() => {
    if (!enabled) return;
    const [mod, key] = combo.includes("+") ? combo.split("+") : ["", combo];
    const onKey = (e: KeyboardEvent) => {
      const modOk = mod === "mod" ? e.metaKey || e.ctrlKey : mod === "" ? !e.metaKey && !e.ctrlKey : true;
      if (modOk && e.key.toLowerCase() === key.toLowerCase()) ref.current(e);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [combo, enabled]);
}

export const isMac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);
export const modKey = isMac ? "⌘" : "Ctrl";
