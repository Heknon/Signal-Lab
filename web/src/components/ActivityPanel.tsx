import { useEffect, useState } from "react";
import { Play, Square } from "lucide-react";
import type { Lesson } from "../api";
import { useLab } from "../context";
import { fmtNumber } from "../lib/format";

export interface ActivityState {
  kind: "experiment" | "incident";
  lesson: string;
  title: string;
  by: string;
  started: number;
  ends: number;
  now: number;
  phase: string;
  phases: { name: string; start: number; end: number }[];
  status: "running" | "done" | "aborted" | "stopped";
  reason: string;
  samples: [number, number][];
  steady: { label?: string; threshold?: number; abort_at?: number; abort_above?: number; direction?: "above" | "below" } | null;
  hypothesis_held: boolean | null;
  fault_started?: number | null;
  fault_ended?: number | null;
}

async function call<T>(path: string, method = "GET"): Promise<T> {
  const r = await fetch(path, { method });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? `HTTP ${r.status}`);
  return r.json();
}

export function useActivity(lessonId: string) {
  const [state, setState] = useState<{ current: ActivityState | null; last: ActivityState | null }>({ current: null, last: null });
  useEffect(() => {
    let live = true;
    const tick = () => call<{ current: ActivityState | null; last: ActivityState | null }>(`/api/activity?lesson=${encodeURIComponent(lessonId)}`).then((s) => live && setState(s)).catch(() => undefined);
    tick();
    const id = window.setInterval(tick, 2000);
    return () => { live = false; window.clearInterval(id); };
  }, [lessonId]);
  const mine = state.current?.lesson === lessonId ? state.current : state.last;
  return { current: state.current, mine };
}

const fmtClock = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

/** Steady-state samples with threshold, abort line and the fault window shaded. */
function SteadyChart({ a }: { a: ActivityState }) {
  // Narrow screens get a narrower coordinate system so labels stay readable.
  const narrow = typeof window !== "undefined" && window.innerWidth < 600;
  const W = narrow ? 360 : 640, H = narrow ? 200 : 180, P = { l: 40, r: 10, t: 12, b: 24 };
  const t0 = a.started * 1000, t1 = Math.max(a.ends * 1000, t0 + 1);
  const values = a.samples.map(([, v]) => v);
  const abortAt = a.steady?.abort_at ?? a.steady?.abort_above;
  const refs = [a.steady?.threshold, abortAt].filter((x): x is number => typeof x === "number");
  const max = Math.max(...values, ...refs, 0.0001) * 1.15;
  const x = (t: number) => P.l + ((t - t0) / (t1 - t0)) * (W - P.l - P.r);
  const y = (v: number) => H - P.b - (v / max) * (H - P.t - P.b);
  const path = a.samples.map(([t, v], i) => `${i ? "L" : "M"}${x(t).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const inject = a.fault_started ? { from: a.fault_started * 1000, to: (a.fault_ended ?? (a.status === "running" ? a.now : a.ends)) * 1000 } : null;
  const ticks = [0, 0.5, 1].map((f) => f * max);
  return (
    <svg className="steady-chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={a.steady?.label ?? "steady state"}>
      {inject && <rect x={x(inject.from)} y={P.t} width={Math.max(1, x(inject.to) - x(inject.from))} height={H - P.t - P.b} className="fault-band" />}
      {ticks.map((v) => (
        <g key={v}>
          <line x1={P.l} x2={W - P.r} y1={y(v)} y2={y(v)} className="grid" />
          <text x={P.l - 6} y={y(v) + 4} textAnchor="end" className="axis">{fmtNumber(v, 2)}</text>
        </g>
      ))}
      {a.steady?.threshold != null && <line x1={P.l} x2={W - P.r} y1={y(a.steady.threshold)} y2={y(a.steady.threshold)} className="threshold" />}
      {abortAt != null && <line x1={P.l} x2={W - P.r} y1={y(abortAt)} y2={y(abortAt)} className="abort" />}
      <path d={path} className="series" />
      <text x={P.l} y={H - 6} className="axis">start</text>
      <text x={W - P.r} y={H - 6} textAnchor="end" className="axis">+{fmtClock((t1 - t0) / 1000)}</text>
    </svg>
  );
}

export default function ActivityPanel({ lesson }: { lesson: Lesson }) {
  const { toast } = useLab();
  const { current, mine } = useActivity(lesson.id);
  const [busy, setBusy] = useState(false);
  const other = current && current.status === "running" && current.lesson !== lesson.id ? current : null;
  const a = mine;
  const running = a?.status === "running";
  const left = a ? Math.max(0, a.ends - a.now) : 0;
  const isExperiment = lesson.kind === "experiment";
  const spec = lesson.experiment;

  const start = async () => {
    setBusy(true);
    try { await call(`/api/lessons/${lesson.id}/start`, "POST"); }
    catch (e) { toast((e as Error).message); }
    finally { setBusy(false); }
  };
  const stop = async () => {
    try { await call("/api/activity/stop", "POST"); } catch (e) { toast((e as Error).message); }
  };

  return (
    <section className="activity">
      {isExperiment && spec?.hypothesis && (
        <div className="hypothesis"><span className="section-label">Hypothesis</span><p>{String(spec.hypothesis)}</p></div>
      )}
      <div className="activity-bar">
        {!running && (
          <button className="btn btn-primary" onClick={start} disabled={busy || !!other}>
            {busy ? <span className="spinner" /> : <Play />}{a ? "Run again" : isExperiment ? "Start experiment" : "Start incident"}
          </button>
        )}
        {running && <button className="btn" onClick={stop}><Square />Stop</button>}
        {running && (
          <span className="activity-status">
            <span className="dot dot-warn" />
            {isExperiment ? <>{a.phase} · {fmtClock(left)} left</> : <>Incident in progress · {fmtClock(left)} left</>}
            {a.by && <span className="subtle"> · started by {a.by}</span>}
          </span>
        )}
        {a && a.status !== "running" && (
          <span className={`activity-status ${a.status === "aborted" || a.hypothesis_held === false ? "bad" : "good"}`}>
            {a.status === "aborted" ? a.reason
              : a.status === "stopped" ? a.reason
              : isExperiment ? (a.hypothesis_held ? "Hypothesis held: steady state stayed within the threshold." : "Hypothesis rejected: steady state crossed the threshold.")
              : `Incident over. The fault started at ${a.fault_started ? new Date(a.fault_started * 1000).toLocaleTimeString() : "?"}.`}
          </span>
        )}
        {other && <span className="activity-status"><span className="dot dot-warn" />{other.by} is running “{other.title}” ({fmtClock(Math.max(0, other.ends - other.now))} left). The shop is shared, so wait for it to finish.</span>}
      </div>
      {isExperiment && a && a.samples.length > 0 && (
        <div className="steady">
          <div className="steady-legend">
            <span><i className="series" />{a.steady?.label ?? "steady state"}</span>
            {a.steady?.threshold != null && <span><i className="threshold" />hypothesis limit</span>}
            {(a.steady?.abort_at ?? a.steady?.abort_above) != null && <span><i className="abort" />abort</span>}
            {a.fault_started && <span><i className="fault" />fault injected</span>}
          </div>
          <SteadyChart a={a} />
        </div>
      )}
    </section>
  );
}
