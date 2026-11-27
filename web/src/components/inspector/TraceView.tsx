import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { Activity, AlertCircle, ChevronDown, ChevronRight, ExternalLink, Link2, X } from "lucide-react";
import type { Backend, LogRecord, Span } from "../../api";
import { fmtDuration, fmtValue, serviceColor, shortId } from "../../lib/format";
import { Empty } from "../ui";

interface Row { span: Span; depth: number; hasChildren: boolean }

function buildRows(spans: Span[], collapsed: Set<string>): Row[] {
  const ids = new Set(spans.map((s) => s.span_id));
  const children = new Map<string, Span[]>();
  const roots: Span[] = [];
  for (const s of spans) {
    if (s.parent_span_id && ids.has(s.parent_span_id)) {
      const list = children.get(s.parent_span_id) ?? [];
      list.push(s);
      children.set(s.parent_span_id, list);
    } else roots.push(s);
  }
  const byStart = (a: Span, b: Span) => a.start_ms - b.start_ms;
  const rows: Row[] = [];
  const walk = (s: Span, depth: number) => {
    const kids = (children.get(s.span_id) ?? []).sort(byStart);
    rows.push({ span: s, depth, hasChildren: kids.length > 0 });
    if (!collapsed.has(s.span_id)) kids.forEach((k) => walk(k, depth + 1));
  };
  roots.sort(byStart).forEach((r) => walk(r, 0));
  return rows;
}

function niceStep(total: number, count: number): number {
  const raw = total / count;
  const pow = Math.pow(10, Math.floor(Math.log10(raw || 1)));
  const n = raw / pow;
  return (n < 1.5 ? 1 : n < 3.5 ? 2 : n < 7.5 ? 5 : 10) * pow;
}

export function groupTraces(spans: Span[]) {
  const map = new Map<string, Span[]>();
  for (const s of spans) map.set(s.trace_id, [...(map.get(s.trace_id) ?? []), s]);
  return [...map.entries()].map(([id, list]) => {
    const start = Math.min(...list.map((s) => s.start_ms));
    const end = Math.max(...list.map((s) => s.end_ms));
    const ids = new Set(list.map((s) => s.span_id));
    const root = list.find((s) => !s.parent_span_id || !ids.has(s.parent_span_id)) ?? list[0];
    return { id, spans: list, start, end, root, services: [...new Set(list.map((s) => s.service))], errors: list.filter((s) => s.status.code === "error").length };
  }).sort((a, b) => a.start - b.start);
}

export default function TraceView({ spans, backends, focus, logs, onShowLogs }: {
  spans: Span[]; backends: Backend[]; focus?: { traceId: string; spanId?: string | null } | null; logs: LogRecord[]; onShowLogs?: (spanId: string) => void;
}) {
  const traces = useMemo(() => groupTraces(spans), [spans]);
  const [traceId, setTraceId] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const wrap = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(800);
  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setWidth(el.clientWidth));
    ro.observe(el);
    return () => ro.disconnect();
  }, [spans.length > 0]);

  useEffect(() => {
    if (focus) { setTraceId(focus.traceId); setSelected(focus.spanId ?? null); }
  }, [focus]);
  const current = traces.find((t) => t.id === traceId) ?? traces[0];
  useEffect(() => { if (traces.length && !traces.some((t) => t.id === traceId)) setTraceId(traces[0].id); }, [traces, traceId]);

  if (!spans.length) {
    return <Empty icon={<Activity />} title="No spans yet">Run your code. Spans appear here the moment the Collector forwards them.</Empty>;
  }
  const rows = buildRows(current.spans, collapsed);
  const total = Math.max(current.end - current.start, 0.001);
  const trackWidth = Math.max(120, width * 0.6 - 68);
  const step = niceStep(total, Math.max(2, Math.floor(trackWidth / 78)));
  const ticks: number[] = [];
  for (let t = 0; t <= total + 1e-9; t += step) ticks.push(t);
  const span = current.spans.find((s) => s.span_id === selected) ?? null;
  const toggle = (id: string) => setCollapsed((c) => { const n = new Set(c); if (n.has(id)) n.delete(id); else n.add(id); return n; });

  return (
    <div className="inspector" ref={wrap}>
      <div className="waterfall-wrap">
        {traces.length > 1 && (
          <div className="trace-list" role="toolbar" aria-label="Traces">
            {traces.map((t) => (
              <button key={t.id} className="trace-chip" aria-pressed={t.id === current.id} onClick={() => { setTraceId(t.id); setSelected(null); }}>
                {t.errors > 0 && <AlertCircle style={{ width: 12, height: 12, color: "var(--err)" }} />}
                {t.root.name}
                <span className="mono">{t.spans.length} · {fmtDuration(t.end - t.start)}</span>
              </button>
            ))}
          </div>
        )}
        <div className="waterfall" role="tree" aria-label="Trace waterfall">
          <div className="wf-head">
            <div className="wf-summary" title={`trace ${current.id}`}>
              {current.services.length} service{current.services.length > 1 ? "s" : ""} · {current.spans.length} span{current.spans.length > 1 ? "s" : ""} · <span className="mono">{shortId(current.id)}</span>
            </div>
            <div className="wf-ticks">
              {ticks.map((t) => <span key={t} className="wf-tick" style={{ left: `${(t / total) * 100}%` }}>{fmtDuration(t)}</span>)}
            </div>
            <div style={{ textAlign: "right", paddingRight: 12 }}>{fmtDuration(total)}</div>
          </div>
          {rows.map(({ span: s, depth, hasChildren }) => {
            const left = ((s.start_ms - current.start) / total) * 100;
            const width = Math.max((s.duration_ms / total) * 100, 0.3);
            const color = s.status.code === "error" ? "var(--err)" : serviceColor(s.service);
            return (
              <Fragment key={s.span_id}>
              <div role="treeitem" aria-selected={selected === s.span_id} className={`wf-row ${selected === s.span_id ? "selected" : ""}`} onClick={() => setSelected(selected === s.span_id ? null : s.span_id)}>
                <div className="wf-name" style={{ paddingLeft: 8 + depth * 14 }}>
                  <span className="toggle" onClick={(e) => { if (hasChildren) { e.stopPropagation(); toggle(s.span_id); } }}>
                    {hasChildren ? (collapsed.has(s.span_id) ? <ChevronRight size={13} /> : <ChevronDown size={13} />) : null}
                  </span>
                  <span className="svc" style={{ background: serviceColor(s.service) }} />
                  {s.status.code === "error" && <AlertCircle className="err-icon" />}
                  <span className="n">{s.name}</span>
                  <span className="svc-name">{s.service}</span>
                  {s.links.length > 0 && <Link2 style={{ width: 12, height: 12, color: "var(--text-3)", flex: "none" }} />}
                </div>
                <div className="wf-track">
                  <div className="wf-bar" style={{ left: `${left}%`, width: `${width}%`, background: color }}>
                    {s.events.map((e, i) => (
                      <span key={i} className="ev" title={e.name} style={{ left: `${Math.min(100, Math.max(0, ((e.time_ms - s.start_ms) / Math.max(s.duration_ms, 0.001)) * 100))}%` }} />
                    ))}
                  </div>
                </div>
                <div className="wf-dur">{fmtDuration(s.duration_ms)}</div>
              </div>
              {span?.span_id === s.span_id && (
                <SpanDetail span={span} backends={backends} onClose={() => setSelected(null)} logs={logs.filter((l) => l.span_id === span.span_id)} onShowLogs={onShowLogs} depth={depth} />
              )}
              </Fragment>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export function KV({ data }: { data: Record<string, unknown> }) {
  const entries = Object.entries(data);
  if (!entries.length) return <div className="subtle" style={{ fontSize: 12 }}>None</div>;
  return (
    <table className="kv">
      <tbody>
        {entries.sort(([a], [b]) => a.localeCompare(b)).map(([k, v]) => {
          const f = fmtValue(v);
          return <tr key={k}><td className="k">{k}</td><td className={`v ${f.kind}`}>{f.text}</td></tr>;
        })}
      </tbody>
    </table>
  );
}

function SpanDetail({ span, backends, onClose, logs, onShowLogs, depth }: { span: Span; backends: Backend[]; onClose: () => void; logs: LogRecord[]; onShowLogs?: (spanId: string) => void; depth: number }) {
  const traceLinks = backends.filter((b) => b.enabled && b.capabilities.includes("traces") && b.link_templates.trace);
  return (
    <aside className="detail inline" aria-label="Span details" style={{ marginLeft: 12 + depth * 14 }}>
      <div className="detail-head">
        <h4>
          {span.status.code === "error" && <AlertCircle style={{ width: 15, height: 15, color: "var(--err)", flex: "none", marginTop: 2 }} />}
          {span.name}
          <button className="icon-btn" onClick={onClose} aria-label="Close details"><X /></button>
        </h4>
        <div className="detail-sub">
          <span className="badge" style={{ color: serviceColor(span.service) }}>{span.service}</span>
          <span className="badge badge-outline">{span.kind}</span>
          <span className="badge badge-outline">{fmtDuration(span.duration_ms)}</span>
          {span.status.code !== "unset" && <span className={`badge ${span.status.code === "error" ? "badge-err" : "badge-ok"}`}>{span.status.code}{span.status.message ? `: ${span.status.message}` : ""}</span>}
        </div>
        {traceLinks.length > 0 && (
          <div className="backend-links" style={{ marginTop: 8 }}>
            {traceLinks.map((b) => (
              <a key={b.id} href={b.link_templates.trace.replace("{trace_id}", span.trace_id)} target="_blank" rel="noreferrer">Open in {b.title.split(" ")[0]}<ExternalLink /></a>
            ))}
            {logs.length > 0 && onShowLogs && <a href="#" onClick={(e) => { e.preventDefault(); onShowLogs(span.span_id); }}>{logs.length} log{logs.length > 1 ? "s" : ""}</a>}
          </div>
        )}
      </div>
      <div className="detail-grid">
      <div className="detail-section">
        <h5>Identity</h5>
        <KV data={{ trace_id: span.trace_id, span_id: span.span_id, parent_span_id: span.parent_span_id ?? "(root)", "scope.name": span.scope.name }} />
      </div>
      <div className="detail-section">
        <h5>Attributes</h5>
        <KV data={span.attributes} />
      </div>
      {span.events.length > 0 && (
        <div className="detail-section">
          <h5>Events · {span.events.length}</h5>
          {span.events.map((e, i) => {
            const { "exception.stacktrace": stack, ...rest } = e.attributes as Record<string, unknown>;
            return (
              <div key={i} className="event-item">
                <div className="event-name">{e.name}<span className="t">+{fmtDuration(e.time_ms - span.start_ms)}</span></div>
                <KV data={rest} />
                {typeof stack === "string" && <pre className="stacktrace">{stack}</pre>}
              </div>
            );
          })}
        </div>
      )}
      {span.links.length > 0 && (
        <div className="detail-section">
          <h5><Link2 size={12} />Links · {span.links.length}</h5>
          {span.links.map((l, i) => (
            <div key={i} className="event-item">
              <KV data={{ trace_id: l.trace_id, span_id: l.span_id, ...l.attributes }} />
            </div>
          ))}
        </div>
      )}
      <div className="detail-section">
        <h5>Resource</h5>
        <KV data={span.resource} />
      </div>
      </div>
    </aside>
  );
}
