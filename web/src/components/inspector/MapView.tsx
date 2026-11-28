import { useMemo } from "react";
import type { Span } from "../../api";
import { fmtDuration } from "../../lib/format";
import { ServiceGraph, type GraphEdge, type GraphNode } from "../ServiceGraph";

interface Edge { from: string; to: string; external: boolean; calls: number; errors: number; totalMs: number; first: Span }

/** What an uninstrumented callee is called, from the caller's client/producer span. */
function targetName(s: Span): string {
  const a = s.attributes;
  const str = (k: string) => (typeof a[k] === "string" && a[k] ? (a[k] as string) : null);
  if (str("peer.service")) return str("peer.service")!;
  if (str("messaging.destination.name")) return str("messaging.destination.name")!;
  if (str("db.system")) return [str("db.system"), str("db.namespace") ?? str("db.name")].filter(Boolean).join(" ");
  if (str("server.address")) return str("server.address")!;
  // Messaging span names are "<destination> <operation>", e.g. "orders publish".
  if (s.kind === "producer") { const m = s.name.match(/^(.+) (publish|send|create)$/); if (m) return m[1]; }
  const url = str("url.full") ?? str("http.url");
  if (url) { try { return new URL(url).host; } catch { /* not a URL */ } }
  return `${s.name} (unknown peer)`;
}

/**
 * Build a service map from spans, the way backends do: an arrow for every
 * client or producer span, pointing at the service whose server or consumer
 * span handled it, or at an external dependency named by the span's attributes.
 * Internal spans never become arrows.
 */
export function deriveMap(spans: Span[]) {
  const byParent = new Map<string, Span[]>();
  const linkedFrom = new Map<string, Span[]>();
  for (const s of spans) {
    if (s.parent_span_id) byParent.set(s.parent_span_id, [...(byParent.get(s.parent_span_id) ?? []), s]);
    for (const l of s.links) linkedFrom.set(l.span_id, [...(linkedFrom.get(l.span_id) ?? []), s]);
  }
  const services = new Set(spans.map((s) => s.service));
  const external = new Set<string>();
  const edges = new Map<string, Edge>();
  const kinds = { client: 0, producer: 0, server: 0, consumer: 0, internal: 0 } as Record<string, number>;
  for (const s of spans) {
    kinds[s.kind] = (kinds[s.kind] ?? 0) + 1;
    if (s.kind !== "client" && s.kind !== "producer") continue;
    const handlers = [...(byParent.get(s.span_id) ?? []), ...(linkedFrom.get(s.span_id) ?? [])]
      .filter((c) => (c.kind === "server" || c.kind === "consumer") && c.service !== s.service);
    const targets = handlers.length ? [...new Set(handlers.map((h) => h.service))] : [targetName(s)];
    for (const to of targets) {
      const isExternal = !handlers.length;
      if (isExternal && !services.has(to)) external.add(to);
      const key = `${s.service}->${to}`;
      const e = edges.get(key) ?? { from: s.service, to, external: isExternal, calls: 0, errors: 0, totalMs: 0, first: s };
      e.calls += 1;
      e.totalMs += s.duration_ms;
      if (s.status.code === "error") e.errors += 1;
      edges.set(key, e);
    }
  }
  return { services: [...services], external: [...external], edges: [...edges.values()], kinds };
}

export default function MapView({ spans, onEdge }: { spans: Span[]; onEdge?: (s: Span) => void }) {
  const map = useMemo(() => deriveMap(spans), [spans]);
  if (!spans.length) return <div className="empty-line">No spans yet.</div>;

  const nodes: GraphNode[] = [
    ...map.services.map((id) => ({ id })),
    ...map.external.map((id) => ({ id, external: true, title: `${id}: not instrumented; known from the caller's ${map.edges.find((e) => e.to === id)?.first.kind} span` })),
  ];
  const edges: GraphEdge[] = map.edges.map((e) => ({
    from: e.from, to: e.to, error: e.errors > 0,
    label: `${e.calls > 1 ? `${e.calls}× · avg ` : ""}${fmtDuration(e.totalMs / e.calls)}${e.errors ? ` · ${e.errors} err` : ""}`,
    title: `${e.from} → ${e.to}: ${e.calls} ${e.first.kind} span${e.calls > 1 ? "s" : ""}, avg ${fmtDuration(e.totalMs / e.calls)}. Click to open one.`,
    onClick: onEdge ? () => onEdge(e.first) : undefined,
  }));
  const k = map.kinds;
  const summary = `${map.services.length} service${map.services.length > 1 ? "s" : ""} · ${map.edges.length} call path${map.edges.length === 1 ? "" : "s"} · spans by kind: ${
    Object.entries(k).filter(([, n]) => n).map(([kind, n]) => `${kind} ${n}`).join(", ")}`;

  return (
    <div className="map-view">
      <div className="map-summary">{summary}</div>
      <ServiceGraph nodes={nodes} edges={edges} />
      {map.edges.length === 0 && (
        <div className="empty-line">No arrows: none of these spans is a <code>client</code> or <code>producer</code> span, so nothing says this service called anything.</div>
      )}
    </div>
  );
}
