import { useCallback, useEffect, useRef, useState } from "react";

export function useAsync<T>(fn: () => Promise<T>, deps: unknown[], intervalMs?: number) {
  const [data, setData] = useState<T | undefined>();
  const [error, setError] = useState<Error | undefined>();
  const [loading, setLoading] = useState(true);
  const fnRef = useRef(fn);
  fnRef.current = fn;
  // Never stack polls: a slow endpoint must not pile up requests, because browsers
  // allow only 6 connections per host and a queued request stalls navigation.
  const inFlight = useRef<Promise<void> | null>(null);
  const reload = useCallback(() => {
    if (inFlight.current) return inFlight.current;
    return (inFlight.current = fnRef.current().then(
      (d) => { setData(d); setError(undefined); },
      (e: Error) => setError(e),
    ).finally(() => { setLoading(false); inFlight.current = null; }));
  }, []);
  useEffect(() => {
    setLoading(true);
    reload();
    if (!intervalMs) return;
    const id = window.setInterval(() => { if (document.visibilityState === "visible") reload(); }, intervalMs);
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
