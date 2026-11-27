import { useEffect, useState } from "react";
import { ArrowUpRight } from "lucide-react";
import type { LogRecord } from "../../api";
import { fmtTime, shortId } from "../../lib/format";
import { Empty } from "../ui";
import { KV } from "./TraceView";

export default function LogsView({ logs, onTrace, focusSpan }: { logs: LogRecord[]; onTrace: (traceId: string, spanId: string | null) => void; focusSpan?: string | null }) {
  const [open, setOpen] = useState<number | null>(null);
  const [filter, setFilter] = useState<string | null>(focusSpan ?? null);
  useEffect(() => setFilter(focusSpan ?? null), [focusSpan]);
  if (!logs.length) {
    return <Empty title="No logs yet." />;
  }
  const shown = filter ? logs.filter((l) => l.span_id === filter) : logs;
  return (
    <div className="logs">
      {filter && (
        <div className="row" style={{ padding: "8px 12px", borderBottom: "1px solid var(--border)", fontSize: 12 }}>
          <span className="muted">Logs for span <span className="mono">{shortId(filter)}</span></span>
          <button className="btn btn-ghost btn-sm" onClick={() => setFilter(null)}>Show all</button>
        </div>
      )}
      {shown.map((l, i) => {
        const body = typeof l.body === "string" ? l.body : JSON.stringify(l.body);
        const attrs = Object.entries(l.attributes).filter(([k]) => !k.startsWith("code."));
        return (
          <div key={i} className={`log-row ${open === i ? "open" : ""}`} onClick={() => setOpen(open === i ? null : i)}>
            <span className="log-time">{fmtTime(l.time_ms).slice(0, 12)}</span>
            <span className={`sev ${l.severity_text.toUpperCase()}`}>{l.severity_text.toUpperCase() || "–"}</span>
            <div style={{ minWidth: 0 }}>
              <div className="log-body">{body}</div>
              {attrs.length > 0 && (
                <div className="log-attrs">{attrs.map(([k, v]) => <span key={k} className="attr-chip">{k}=<b>{String(v)}</b></span>)}</div>
              )}
            </div>
            {l.trace_id ? (
              <button className="trace-link" onClick={(e) => { e.stopPropagation(); onTrace(l.trace_id!, l.span_id); }} title="Jump to the span that wrote this">
                {shortId(l.trace_id)}<ArrowUpRight />
              </button>
            ) : <span className="subtle" style={{ fontSize: 11.5 }} title="Logged outside any span">no trace</span>}
            {open === i && (
              <div className="log-expanded" onClick={(e) => e.stopPropagation()}>
                <KV data={{ severity_number: l.severity_number, "scope.name": l.scope.name, trace_id: l.trace_id ?? "", span_id: l.span_id ?? "", ...l.attributes }} />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
