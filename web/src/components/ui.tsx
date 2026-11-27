import { useCallback, useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { BookOpen, Check, ClipboardCheck, Code2, HelpCircle, Search as SearchIcon, Activity, BarChart3, ScrollText } from "lucide-react";
import type { Backend, Capability, LessonKind } from "../api";
import type { LessonState } from "../lib/progress";

export function Empty({ icon, title, children }: { icon?: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="empty">
      <div className="empty-inner">
        {icon}
        <h4>{title}</h4>
        {children && <p>{children}</p>}
      </div>
    </div>
  );
}

export function StateIcon({ state, current }: { state: LessonState; current?: boolean }) {
  return (
    <span className={`state-icon ${state === "done" ? "done" : state === "known" ? "known" : ""} ${current && state === "todo" ? "current" : ""}`} aria-label={state}>
      {state !== "todo" && <Check />}
    </span>
  );
}

const KIND: Record<LessonKind, { icon: ReactNode; label: string }> = {
  code: { icon: <Code2 />, label: "Code" },
  query: { icon: <SearchIcon />, label: "Query" },
  quiz: { icon: <HelpCircle />, label: "Quiz" },
  task: { icon: <ClipboardCheck />, label: "Hands-on" },
  read: { icon: <BookOpen />, label: "Read" },
};
export function KindLabel({ kind }: { kind: LessonKind }) {
  const k = KIND[kind] ?? KIND.read;
  return <span className="kind-icon">{k.icon}{k.label}</span>;
}

export const SIGNAL_ICON: Record<Capability, ReactNode> = { traces: <Activity />, metrics: <BarChart3 />, logs: <ScrollText /> };
export function SignalBadge({ signal }: { signal: Capability }) {
  const cls = signal === "traces" ? "badge-trace" : signal === "metrics" ? "badge-metric" : "badge-log";
  return <span className={`badge ${cls}`}>{SIGNAL_ICON[signal]}{signal}</span>;
}

export function BackendLogo({ backend, size }: { backend: Pick<Backend, "title" | "color">; size?: number }) {
  const initials = backend.title.split(/[\s+]+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join("");
  const style: CSSProperties = { background: backend.color ?? "var(--surface-3)" };
  if (size) Object.assign(style, { width: size, height: size });
  return <span className="backend-logo" style={style}>{initials}</span>;
}

/** Resizable two-pane split. Sizes persist per `id`. */
export function Split({ id, vertical, initial, min = 0.2, max = 0.8, className = "", first, second, firstClass = "", secondClass = "" }: {
  id: string; vertical?: boolean; initial: number; min?: number; max?: number; className?: string;
  first: ReactNode; second: ReactNode; firstClass?: string; secondClass?: string;
}) {
  const [ratio, setRatio] = useState(() => {
    try { const v = Number(localStorage.getItem(`sl-split:${id}`)); return v > 0 && v < 1 ? v : initial; } catch { return initial; }
  });
  const ref = useRef<HTMLDivElement>(null);
  const [dragging, setDragging] = useState(false);
  const onDown = useCallback((e: React.PointerEvent) => {
    e.preventDefault();
    setDragging(true);
    const el = ref.current!;
    const rect = el.getBoundingClientRect();
    const move = (ev: PointerEvent) => {
      const r = vertical ? (ev.clientY - rect.top) / rect.height : (ev.clientX - rect.left) / rect.width;
      setRatio(Math.min(max, Math.max(min, r)));
    };
    const up = () => {
      setDragging(false);
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
    document.body.style.cursor = vertical ? "row-resize" : "col-resize";
    document.body.style.userSelect = "none";
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }, [vertical, min, max]);
  useEffect(() => { try { localStorage.setItem(`sl-split:${id}`, String(ratio)); } catch { /* ignore */ } }, [id, ratio]);
  return (
    <div ref={ref} className={`split ${vertical ? "vertical" : ""} ${className}`}>
      <div className={`pane ${firstClass}`} style={{ flex: `${ratio} 1 0` }}>{first}</div>
      <div className={`resizer ${dragging ? "dragging" : ""}`} onPointerDown={onDown} onDoubleClick={() => setRatio(initial)} role="separator" aria-orientation={vertical ? "horizontal" : "vertical"} title="Drag to resize · double-click to reset" />
      <div className={`pane ${secondClass}`} style={{ flex: `${1 - ratio} 1 0` }}>{second}</div>
    </div>
  );
}

export function useClickOutside<T extends HTMLElement>(open: boolean, onClose: () => void) {
  const ref = useRef<T>(null);
  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) onClose(); };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("mousedown", onDoc); document.removeEventListener("keydown", onKey); };
  }, [open, onClose]);
  return ref;
}

export function InlineCode({ text }: { text: string }) {
  // Render `backticks` in short strings (check titles, details) as code.
  const parts = text.split(/(`[^`]+`)/g);
  return <>{parts.map((p, i) => (p.startsWith("`") && p.endsWith("`") ? <code key={i}>{p.slice(1, -1)}</code> : <span key={i}>{p}</span>))}</>;
}
