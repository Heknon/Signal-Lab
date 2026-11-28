import { useEffect, useRef, useState } from "react";
import { RotateCcw, X } from "lucide-react";
import { api, type Scenario, type ScenarioService } from "../api";
import { useLab } from "../context";
import { useAsync } from "../lib/hooks";
import { ServiceGraph } from "./ServiceGraph";
import { Empty } from "./ui";

function ServiceMap({ services }: { services: ScenarioService[] }) {
  const nodes = services.map((s) => {
    const chaos = s.stats?.chaos;
    const faulty = !!chaos && (chaos.latency_ms > 0 || chaos.error_rate > 0);
    return { id: s.id, stroke: faulty ? "var(--warn)" : s.online ? undefined : "var(--err)", dot: s.online ? undefined : "var(--err)" };
  });
  const edges = services.flatMap((s) => s.calls.map((c) => ({ from: s.id, to: c })));
  return <ServiceGraph nodes={nodes} edges={edges} />;
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
                    {svc.changed && (
                      <div className="svc-changed">
                        Fault set by {svc.changed.by}
                        {svc.changed.expires ? `, clears in ${Math.max(1, Math.round((svc.changed.expires - Date.now() / 1000) / 60))} min` : ""}
                      </div>
                    )}
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
