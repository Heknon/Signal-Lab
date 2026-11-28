import { useMemo } from "react";
import { serviceColor } from "../lib/format";

export interface GraphNode {
  id: string;
  /** Not instrumented: known only from the caller's client span (dashed). */
  external?: boolean;
  /** Outline colour override (faults, offline). */
  stroke?: string;
  dot?: string;
  title?: string;
}
export interface GraphEdge { from: string; to: string; label?: string; error?: boolean; title?: string; onClick?: () => void }

// Edge labels sit mid-arrow: below the line for a downward arrow, above it
// otherwise, so labels of arrows fanning out from one service don't stack.
const LABEL_AT = 0.5;
const CHAR_W = 6.7; // IBM Plex Mono at 11px
const nodeWidth = (id: string) => Math.max(72, Math.round(id.length * CHAR_W + 34));

/** Left-to-right call graph: services in columns by call depth. */
export function ServiceGraph({ nodes, edges, label = "Service map" }: { nodes: GraphNode[]; edges: GraphEdge[]; label?: string }) {
  const layout = useMemo(() => {
    const calls = new Map<string, string[]>();
    for (const e of edges) calls.set(e.from, [...(calls.get(e.from) ?? []), e.to]);
    const depth = new Map<string, number>();
    const visit = (id: string, d: number, seen: Set<string>) => {
      if (seen.has(id) || (depth.get(id) ?? -1) >= d) return;
      depth.set(id, d);
      const next = new Set(seen).add(id);
      (calls.get(id) ?? []).forEach((c) => visit(c, d + 1, next));
    };
    const called = new Set(edges.map((e) => e.to));
    nodes.filter((n) => !called.has(n.id)).forEach((n) => visit(n.id, 0, new Set()));
    nodes.forEach((n) => { if (!depth.has(n.id)) visit(n.id, 0, new Set()); });

    const cols = new Map<number, GraphNode[]>();
    nodes.forEach((n) => { const d = depth.get(n.id)!; cols.set(d, [...(cols.get(d) ?? []), n]); });
    const order = [...cols.keys()].sort((a, b) => a - b);
    const colWidth = order.map((d) => Math.max(...cols.get(d)!.map((n) => nodeWidth(n.id))));
    // Room between columns for the longest edge label (10px mono ≈ 6.1px/char).
    const gap = Math.max(56, ...edges.map((e) => Math.round((e.label?.length ?? 0) * 6.1) + 44));
    const pad = 8, rowH = 44;
    const W = colWidth.reduce((a, b) => a + b, 0) + gap * Math.max(0, order.length - 1) + pad * 2;
    // Arrows that skip a column curve over the top, so they need headroom.
    const skips = edges.some((e) => Math.abs((depth.get(e.to) ?? 0) - (depth.get(e.from) ?? 0)) > 1);
    const top = skips ? 34 : 0;
    const H = Math.max(...order.map((d) => cols.get(d)!.length)) * rowH + 12 + top;
    const pos = new Map<string, { x: number; y: number; w: number; col: number }>();
    let x = pad;
    order.forEach((d, i) => {
      const list = cols.get(d)!;
      list.forEach((n, j) => pos.set(n.id, { x: x + colWidth[i] / 2, y: top + ((H - top) / (list.length + 1)) * (j + 1), w: nodeWidth(n.id), col: i }));
      x += colWidth[i] + gap;
    });
    return { pos, W, H };
  }, [nodes, edges]);

  return (
    <svg className="svc-map" viewBox={`0 0 ${layout.W} ${layout.H}`} style={{ maxWidth: layout.W }} role="img" aria-label={label}>
      <defs>
        <marker id="arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0L8 4L0 8z" fill="var(--text-3)" /></marker>
        <marker id="arrow-err" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0L8 4L0 8z" fill="var(--err)" /></marker>
      </defs>
      {edges.map((e) => {
        const a = layout.pos.get(e.from), b = layout.pos.get(e.to);
        if (!a || !b) return null;
        const x1 = a.x + a.w / 2, x2 = b.x - b.w / 2 - 2;
        const skip = b.col - a.col > 1;
        const cy = Math.min(a.y, b.y) - 13 - 30;
        const d = skip
          ? `M${a.x} ${a.y - 13} C${a.x} ${cy} ${b.x} ${cy} ${b.x} ${b.y - 15}`
          : `M${x1} ${a.y} L${x2} ${b.y}`;
        const lx = (a.x + b.x) / 2, ly = cy + 16;
        return (
          <g key={`${e.from}->${e.to}`} className={`svc-edge ${e.onClick ? "clickable" : ""}`} onClick={e.onClick}>
            {e.title && <title>{e.title}</title>}
            <path d={d} fill="none" stroke={e.error ? "var(--err)" : "var(--border-strong)"} strokeWidth="1.2" markerEnd={`url(#${e.error ? "arrow-err" : "arrow"})`} />
            <path d={d} fill="none" stroke="transparent" strokeWidth="12" />
            {e.label && <text className="svc-edge-label" x={skip ? lx : x1 + (x2 - x1) * LABEL_AT} y={skip ? ly : a.y + (b.y - a.y) * LABEL_AT + (b.y > a.y + 1 ? 13 : -5)} textAnchor="middle">{e.label}</text>}
          </g>
        );
      })}
      {nodes.map((n) => {
        const p = layout.pos.get(n.id)!;
        return (
          <g key={n.id} transform={`translate(${p.x - p.w / 2},${p.y - 13})`}>
            {n.title && <title>{n.title}</title>}
            <rect width={p.w} height="26" rx="7" fill="var(--surface-2)" stroke={n.stroke ?? "var(--border-strong)"} strokeDasharray={n.external ? "4 3" : undefined} />
            {!n.external && <circle cx="12" cy="13" r="3.5" fill={n.dot ?? serviceColor(n.id)} />}
            <text x={n.external ? 12 : 22} y="17" className={n.external ? "external" : undefined}>{n.id}</text>
          </g>
        );
      })}
    </svg>
  );
}
