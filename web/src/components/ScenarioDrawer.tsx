import { useEffect, useMemo, useRef, useState } from "react";
import { RotateCcw, X } from "lucide-react";
import { api, type Scenario, type ScenarioService } from "../api";
import { useLab } from "../context";
import { useAsync } from "../lib/hooks";
import { serviceColor } from "../lib/format";
import { Empty } from "./ui";

function ServiceMap({ services }: { services: ScenarioService[] }) {
  // Lay services out in columns by call depth.
  const layout = useMemo(() => {
    const depth = new Map<string, number>();
    const roots = services.filter((s) => !services.some((o) => o.calls.includes(s.id)));
    const visit = (id: string, d: number) => {
      if ((depth.get(id) ?? -1) >= d) return;
      depth.set(id, d);
      services.find((s) => s.id === id)?.calls.forEach((c) => visit(c, d + 1));
    };
    roots.forEach((r) => visit(r.id, 0));
    services.forEach((s) => { if (!depth.has(s.id)) depth.set(s.id, 0); });
    const cols = new Map<number, string[]>();
    services.forEach((s) => { const d = depth.get(s.id)!; cols.set(d, [...(cols.get(d) ?? []), s.id]); });
    const W = 420, pad = 54, colW = (W - pad * 2) / Math.max(1, cols.size - 1 || 1), H = Math.max(...[...cols.values()].map((c) => c.length)) * 44 + 12;
    const pos = new Map<string, { x: number; y: number }>();
    [...cols.entries()].forEach(([d, ids]) => ids.forEach((id, i) => pos.set(id, { x: cols.size === 1 ? W / 2 : pad + d * colW, y: (H / (ids.length + 1)) * (i + 1) })));
    return { pos, W, H };
  }, [services]);

  return (
    <svg className="svc-map" viewBox={`0 0 ${layout.W} ${layout.H}`} role="img" aria-label="Service map">
      <defs>
        <marker id="arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0L8 4L0 8z" fill="var(--text-3)" /></marker>
      </defs>
      {services.flatMap((s) => s.calls.map((c) => {
        const a = layout.pos.get(s.id), b = layout.pos.get(c);
        if (!a || !b) return null;
        return <line key={`${s.id}-${c}`} x1={a.x + 46} y1={a.y} x2={b.x - 50} y2={b.y} stroke="var(--border-strong)" strokeWidth="1.2" markerEnd="url(#arrow)" />;
      }))}
      {services.map((s) => {
        const p = layout.pos.get(s.id)!;
        const chaos = s.stats?.chaos;
        const faulty = !!chaos && (chaos.latency_ms > 0 || chaos.error_rate > 0);
        return (
          <g key={s.id} transform={`translate(${p.x - 46},${p.y - 13})`}>
            <rect width="92" height="26" rx="7" fill="var(--surface-2)" stroke={faulty ? "var(--warn)" : s.online ? "var(--border-strong)" : "var(--err)"} />
            <circle cx="12" cy="13" r="3.5" fill={s.online ? serviceColor(s.id) : "var(--err)"} />
            <text x="22" y="17">{s.id}</text>
          </g>
        );
      })}
    </svg>
  );
}

function Slider({ label, value, min, max, step, format, onCommit }: { label: string; value: number; min: number; max: number; step: number; format: (v: number) => string; onCommit: (v: number) => void }) {
  const [v, setV] = useState(value);
  const dragging = useRef(false);
  useEffect(() => { if (!dragging.current) setV(value); }, [value]);
  return (
    <label className="control">
      <span>{label}</span>
      <input
        type="range" min={min} max={max} step={step} value={v}
        onPointerDown={() => { dragging.current = true; }}
        onChange={(e) => setV(Number(e.target.value))}
        onPointerUp={() => { dragging.current = false; onCommit(v); }}
        onKeyUp={() => onCommit(v)}
      />
      <output>{format(v)}</output>
    </label>
  );
}

export default function ScenarioDrawer() {
  const { scenarioOpen, setScenarioOpen, toast } = useLab();
  const state = useAsync<Scenario>(api.scenario, [scenarioOpen], scenarioOpen ? 2000 : undefined);
  useEffect(() => {
    if (!scenarioOpen) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setScenarioOpen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [scenarioOpen, setScenarioOpen]);
  if (!scenarioOpen) return null;
  const s = state.data;
  const services = s?.services ?? [];
  const gen = services.find((x) => x.role === "loadgen");
  const apps = services.filter((x) => x.role !== "loadgen");
  const anyFault = apps.some((x) => x.stats && (x.stats.chaos.latency_ms > 0 || x.stats.chaos.error_rate > 0));

  const chaos = async (id: string, body: { latency_ms?: number; error_rate?: number }) => {
    try { await api.chaos(id, body); state.reload(); } catch (e) { toast((e as Error).message); }
  };

  return (
    <>
      <div className="scrim" onClick={() => setScenarioOpen(false)} />
      <aside className="drawer" aria-label="Scenario">
        <div className="drawer-head">
          <h3>{s?.title ?? "Scenario"}</h3>
          <span className="grow" />
          {anyFault && <button className="btn btn-sm" onClick={async () => { await api.resetScenario(); state.reload(); toast("All faults cleared"); }}><RotateCcw />Clear faults</button>}
          <button className="icon-btn" onClick={() => setScenarioOpen(false)} aria-label="Close"><X /></button>
        </div>
        <div className="drawer-body">
          {state.error && <Empty title="Scenario unavailable">{state.error.message}</Empty>}
          {s && (
            <>
              <ServiceMap services={services} />
              {gen && (
                <div className="card svc-card">
                  <div className="svc-head">
                    <h4>Traffic</h4>
                    {!gen.online && <span className="stats">offline</span>}
                  </div>
                  <Slider label="Rate" value={gen.stats?.rps ?? 0} min={0} max={20} step={0.5} format={(v) => `${v} rps`} onCommit={async (v) => { await api.load(v); state.reload(); }} />
                </div>
              )}
              <div className="section-label" style={{ marginTop: 20 }}>Faults</div>
              {apps.map((svc) => {
                const st = svc.stats;
                const faulty = !!st && (st.chaos.latency_ms > 0 || st.chaos.error_rate > 0);
                return (
                  <div key={svc.id} className={`card svc-card ${faulty ? "faulty" : ""}`}>
                    <div className="svc-head">
                      <span className={`dot ${svc.online ? "dot-ok" : "dot-err"}`} />
                      <h4>{svc.id}</h4>
                      {st && (
                        <span className="stats">
                          <span title="p95 latency">p95 {st.p95_ms ?? "–"}ms</span>
                          <span title="errors / requests" style={{ color: st.errors ? "var(--err)" : undefined }}>{st.errors}/{st.requests} err</span>
                        </span>
                      )}
                      {!svc.online && <span className="stats">offline</span>}
                    </div>
                    {st && (
                      <>
                        <Slider label="Latency" value={st.chaos.latency_ms} min={0} max={2000} step={50} format={(v) => `+${v} ms`} onCommit={(v) => chaos(svc.id, { latency_ms: v })} />
                        <Slider label="Errors" value={Math.round(st.chaos.error_rate * 100)} min={0} max={100} step={5} format={(v) => `${v}%`} onCommit={(v) => chaos(svc.id, { error_rate: v / 100 })} />
                      </>
                    )}
                  </div>
                );
              })}
            </>
          )}
        </div>
      </aside>
    </>
  );
}
