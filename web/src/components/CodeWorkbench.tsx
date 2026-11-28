import { useEffect, useMemo, useRef, useState } from "react";
import { Activity, BarChart3, Network, CheckCircle2, CircleDashed, Eye, FileCode2, Play, RotateCcw, ScrollText, Settings2, SquareTerminal, XCircle, ExternalLink } from "lucide-react";
import type { CheckResult, Lesson, RunSummary, SignalConfirm } from "../api";
import { useLab } from "../context";
import { modKey } from "../lib/hooks";
import { drafts } from "../lib/progress";
import { useRun } from "../lib/useRun";
import { fmtDuration } from "../lib/format";
import Editor from "./Editor";
import TraceView from "./inspector/TraceView";
import MapView from "./inspector/MapView";
import MetricsView from "./inspector/MetricsView";
import LogsView from "./inspector/LogsView";
import { Empty, Split } from "./ui";

type Tab = "console" | "traces" | "map" | "metrics" | "logs" | "env";

function primaryTab(lesson: Lesson): Tab {
  const types = lesson.checks.map((c) => c.type);
  if (types.includes("span") || types.includes("trace")) return "traces";
  if (types.includes("metric")) return "metrics";
  if (types.includes("log")) return "logs";
  return "console";
}

function Confirmations({ run }: { run: RunSummary | null }) {
  if (!run) return null;
  const entries = Object.entries(run.backends);
  if (!entries.length) return null;
  return (
    <div className="confirm-row" aria-label="Arrived in backends">
      {entries.map(([id, b]) => {
        const signals = Object.entries(b.signals) as [string, SignalConfirm][];
        const states = signals.map(([, st]) => st.state);
        const state = states.includes("pending") ? "pending" : states.every((x) => x === "found" || x === "unsupported") ? "found" : "missing";
        const url = signals.find(([sig, st]) => sig === "traces" && st.url)?.[1].url ?? signals.find(([, st]) => st.url)?.[1].url;
        const title = signals.map(([sig, st]) => `${sig}: ${st.state === "found" ? `arrived after ${((st.after_ms ?? 0) / 1000).toFixed(1)}s` : st.state === "pending" ? "waiting to be indexed…" : st.state === "missing" ? "not found yet" : "n/a"}`).join("\n");
        const icon = state === "found" ? <CheckCircle2 /> : state === "pending" ? <span className="spinner" style={{ width: 10, height: 10, borderWidth: 1.5 }} /> : <CircleDashed />;
        const label = b.title.split(/[ +]/)[0];
        return url && state === "found" ? (
          <a key={id} className={`confirm ${state}`} href={url} target="_blank" rel="noreferrer" title={`Open in ${b.title}\n${title}`}>{icon}{label}<ExternalLink /></a>
        ) : (
          <span key={id} className={`confirm ${state}`} title={`${b.title}\n${title}`}>{icon}{label}</span>
        );
      })}
    </div>
  );
}

export default function CodeWorkbench({ lesson, onChecks }: { lesson: Lesson; onChecks: (c: CheckResult[], run: RunSummary | null) => void }) {
  const { meta, toast } = useLab();
  const starter = lesson.starter?.content ?? "";
  const [code, setCode] = useState(() => drafts.get(lesson.id) ?? starter);
  const { run, output, telemetry, error, start, busy, running } = useRun(lesson.id);
  const [tab, setTab] = useState<Tab>("console");
  const [file, setFile] = useState<"main" | "traffic">("main");
  const language = (lesson.starter?.language === "yaml" ? "yaml" : "python") as "yaml" | "python";
  const userPicked = useRef(false);
  const [focus, setFocus] = useState<{ traceId: string; spanId?: string | null } | null>(null);
  const [logSpan, setLogSpan] = useState<string | null>(null);
  const backends = meta?.backends ?? [];

  useEffect(() => {
    setCode(drafts.get(lesson.id) ?? starter);
    setTab("console");
    let live = true;
    // The server copy wins: it follows you across browsers.
    drafts.fetch(lesson.id).then((remote) => { if (live && remote != null) setCode(remote); });
    return () => { live = false; };
  }, [lesson.id, starter]);
  useEffect(() => { onChecks(run?.checks ?? [], run); }, [run, onChecks]);

  // Follow the run: console while the first run executes, then the most relevant
  // signal. Later runs stay on the current tab (no Console/Traces bounce on every
  // run) unless the program fails, when the console is what matters.
  const followed = useRef(false);
  useEffect(() => { followed.current = false; }, [lesson.id]);
  useEffect(() => {
    if (!run || userPicked.current) return;
    if (run.status === "running" && !followed.current) setTab("console");
    if (run.exit_code != null && run.exit_code !== 0) { setTab("console"); return; }
    if ((run.status === "done" || run.status === "error" || run.status === "collecting") && run.exit_code === 0) {
      const t = primaryTab(lesson);
      const has = t === "traces" ? telemetry.spans.length : t === "metrics" ? telemetry.metrics.length : t === "logs" ? telemetry.logs.length : 1;
      if (has) { setTab(t); followed.current = true; }
    }
  }, [run, telemetry, lesson]);

  // Pressing Run while the program is still executing queues one more run, which
  // starts with the latest code as soon as the current program exits.
  const codeRef = useRef(code);
  codeRef.current = code;
  const [queued, setQueued] = useState(false);
  useEffect(() => { setQueued(false); }, [lesson.id]);
  useEffect(() => {
    if (queued && !running) { setQueued(false); userPicked.current = false; setFocus(null); start(codeRef.current); }
  }, [queued, running, start]);
  const execute = () => {
    if (!meta?.runs_enabled) return;
    if (running) {
      if (!queued) toast("Runs again as soon as the current run finishes");
      setQueued(true);
      return;
    }
    userPicked.current = false;
    setFocus(null);
    start(code);
  };
  const modified = code !== starter;
  const onEdit = (v: string) => { setCode(v); if (v === starter) drafts.clear(lesson.id); else drafts.set(lesson.id, v); };

  const counts = { traces: telemetry.spans.length, metrics: telemetry.metrics.length, logs: telemetry.logs.length };
  const failedLine = useMemo(() => output.some((o) => o.stream === "stderr" && /Traceback|Error/.test(o.text)), [output]);
  const pick = (t: Tab) => { userPicked.current = true; setTab(t); };
  const jumpToTrace = (traceId: string, spanId: string | null) => { setFocus({ traceId, spanId }); pick("traces"); };

  const status = !run ? null : run.status === "running" || run.status === "queued" ? (
    <span className="run-status"><span className="spinner" />Running…</span>
  ) : run.status === "collecting" ? (
    <span className="run-status"><span className="spinner" />Collecting telemetry…</span>
  ) : run.exit_code === 0 ? (
    <span className="run-status ok"><CheckCircle2 />Exited 0 · {fmtDuration(run.duration_ms)}</span>
  ) : (
    <span className="run-status err"><XCircle />Exited {run.exit_code}</span>
  );

  const editor = (
    <div className="stack" style={{ height: "100%" }}>
      <div className="wb-bar">
        <button className={`file-tab ${file === "main" ? "active" : ""}`} onClick={() => setFile("main")}><FileCode2 />{lesson.starter?.filename ?? "main.py"}{modified && <span className="modified" title="Edited" />}</button>
        {lesson.traffic && <button className={`file-tab ${file === "traffic" ? "active" : ""}`} onClick={() => setFile("traffic")} title="Sent through your Collector on each run (read-only)">{lesson.traffic.filename}<span className="subtle">read-only</span></button>}
        <span className="spacer" />
        {status}
        <button className="btn btn-ghost btn-sm" onClick={() => onEdit(starter)} disabled={!modified} title="Reset to starter code"><RotateCcw />Reset</button>
        <button className="btn btn-primary btn-sm" onClick={execute} disabled={!meta?.runs_enabled} title={meta?.runs_enabled === false ? "Code execution is disabled on this deployment" : `Run (${modKey} Enter)`}>
          {busy ? <span className="spinner" /> : <Play />}{queued ? "Queued" : "Run"}<span className="kbd">{modKey}↵</span>
        </button>
      </div>
      <div className="grow" style={{ minHeight: 0 }}>
        {file === "traffic" && lesson.traffic
          ? <Editor key="traffic" value={lesson.traffic.content} language="python" readOnly />
          : <Editor key="main" value={code} onChange={onEdit} language={language} onRun={execute} intellisense={!!meta?.intellisense} />}
      </div>
    </div>
  );

  const tabs: { id: Tab; label: string; icon: React.ReactNode; count?: number; color?: string }[] = [
    { id: "console", label: "Console", icon: <SquareTerminal /> },
    { id: "traces", label: "Traces", icon: <Activity />, count: counts.traces, color: "var(--trace)" },
    { id: "map", label: "Map", icon: <Network />, color: "var(--trace)" },
    { id: "metrics", label: "Metrics", icon: <BarChart3 />, count: counts.metrics, color: "var(--metric)" },
    { id: "logs", label: "Logs", icon: <ScrollText />, count: counts.logs, color: "var(--log)" },
    { id: "env", label: "Environment", icon: <Settings2 /> },
  ];

  const panel = (
    <div className="panel">
      <div className="panel-bar">
        <div className="tabs" role="tablist">
          {tabs.map((t) => (
            <button key={t.id} role="tab" aria-selected={tab === t.id} className="tab" style={{ ["--tab-color" as string]: t.color }} onClick={() => pick(t.id)}>
              {t.icon}<span className="tab-label">{t.label}</span>
              {t.count !== undefined && <span className={`count ${t.count ? "live" : ""}`}>{t.count}</span>}
            </button>
          ))}
        </div>
        <div className="right"><Confirmations run={run} /></div>
      </div>
      <div className="panel-body">
        {tab === "console" && (
          error ? <div className="query-error">{error}</div> :
          output.length === 0 ? (
            <Empty title="Output appears here.">Run with <span className="kbd">{modKey} ↵</span></Empty>
          ) : (
            <div className="console" role="log">
              {output.map((o, i) => (
                <div key={i} className={`console-line ${o.stream} ${failedLine && o.stream === "stderr" && /Error|Exception/.test(o.text) ? "error" : ""}`}>
                  <span className="t">{o.t != null ? `${(o.t / 1000).toFixed(2)}s` : ""}</span>
                  <span className="text">{o.text}</span>
                </div>
              ))}
            </div>
          )
        )}
        {tab === "traces" && <TraceView spans={telemetry.spans} backends={backends} focus={focus} logs={telemetry.logs} onShowLogs={(id) => { setLogSpan(id); pick("logs"); }} />}
        {tab === "map" && <MapView spans={telemetry.spans} onEdge={(s) => jumpToTrace(s.trace_id, s.span_id)} />}
        {tab === "metrics" && <MetricsView metrics={telemetry.metrics} backends={backends} onExemplar={jumpToTrace} />}
        {tab === "logs" && <LogsView logs={telemetry.logs} onTrace={jumpToTrace} focusSpan={logSpan} />}
        {tab === "env" && (
          <div>
            <table className="env-table"><tbody>
              <tr><td>command</td><td>{lesson.kind === "collector" ? `otelcol --config=base.yaml --config=${lesson.starter?.filename}, then opentelemetry-instrument python ${lesson.traffic?.filename}` : `${lesson.runtime.auto_instrument === false ? "" : "opentelemetry-instrument "}python ${lesson.starter?.filename ?? "main.py"}`}</td></tr>
              {Object.entries(lesson.env).map(([k, v]) => <tr key={k}><td>{k}</td><td>{v}</td></tr>)}
            </tbody></table>
          </div>
        )}
      </div>
    </div>
  );

  return (
    <div className="workbench">
      <Split id="code-v" vertical initial={0.52} min={0.2} max={0.85} first={editor} second={panel} />
      {lesson.solution && <SolutionPeek lesson={lesson} onUse={(c) => onEdit(c)} />}
    </div>
  );
}

function SolutionPeek({ lesson, onUse }: { lesson: Lesson; onUse: (code: string) => void }) {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const handler = () => setOpen(true);
    window.addEventListener("sl:show-solution", handler);
    return () => window.removeEventListener("sl:show-solution", handler);
  }, []);
  if (!open || !lesson.solution) return null;
  return (
    <>
      <div className="scrim" onClick={() => setOpen(false)} />
      <div className="palette" style={{ top: "10vh", width: "min(760px, calc(100vw - 32px))" }} role="dialog" aria-label="Solution">
        <div className="drawer-head"><Eye style={{ width: 16, height: 16 }} /><h3>Solution</h3><span className="grow" />
          <button className="btn btn-sm" onClick={() => { onUse(lesson.solution!.content); setOpen(false); }}>Load into editor</button>
          <button className="btn btn-ghost btn-sm" onClick={() => setOpen(false)}>Close</button>
        </div>
        <div style={{ height: "60vh" }}><Editor value={lesson.solution.content} language={lesson.solution.language === "yaml" ? "yaml" : "python"} readOnly /></div>
      </div>
    </>
  );
}
