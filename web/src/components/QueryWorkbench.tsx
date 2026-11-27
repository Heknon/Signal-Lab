import { useEffect, useState } from "react";
import { Database, ExternalLink, Play, RotateCcw, Table2, LineChart } from "lucide-react";
import { api, type CheckResult, type Lesson, type QueryResult } from "../api";
import { useLab } from "../context";
import { modKey } from "../lib/hooks";
import { drafts } from "../lib/progress";
import { chartColors, fmtNumber } from "../lib/format";
import Chart from "./Chart";
import Editor, { type EditorLanguage } from "./Editor";
import { BackendLogo, Empty, Split } from "./ui";

const LANG_LABEL: Record<string, string> = { metricsql: "MetricsQL", promql: "PromQL", esql: "ES|QL" };
const RANGES = [{ s: 300, l: "5m" }, { s: 900, l: "15m" }, { s: 3600, l: "1h" }];

export default function QueryWorkbench({ lesson, onChecks }: { lesson: Lesson; onChecks: (c: CheckResult[]) => void }) {
  const { meta } = useLab();
  const q = lesson.query!;
  const backend = meta?.backends.find((b) => b.id === q.backend);
  const starter = lesson.starter?.content.trim() ?? "";
  const [query, setQuery] = useState(() => drafts.get(lesson.id) ?? starter);
  const [range, setRange] = useState(q.range_s ?? 900);
  const [result, setResult] = useState<QueryResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<"chart" | "table">("chart");

  useEffect(() => { setQuery(drafts.get(lesson.id) ?? starter); setResult(null); setError(null); }, [lesson.id, starter]);

  const execute = async (text = query, r = range) => {
    if (!text.trim() || !backend?.enabled) return;
    setBusy(true); setError(null);
    try {
      const res = await api.query(q.backend, q.language, text, lesson.id, r);
      setResult(res.result);
      if (res.result.error) setError(res.result.error);
      onChecks(res.checks);
      setView(res.result.series.length ? "chart" : "table");
    } catch (e) {
      setError((e as Error).message);
    } finally { setBusy(false); }
  };
  const onEdit = (v: string) => { setQuery(v); if (v.trim() === starter) drafts.clear(lesson.id); else drafts.set(lesson.id, v); };

  if (!backend?.enabled) {
    return <Empty icon={<Database />} title={`${backend?.title ?? q.backend} isn't enabled`}>Enable the <code>{q.backend}</code> backend plugin to run these queries. See the Stack page.</Empty>;
  }
  const explore = backend.links.find((l) => l.id === "explore" || l.id === "esql");
  const lang = (q.language === "promql" ? "metricsql" : q.language) as EditorLanguage;

  const editorPane = (
    <div className="stack" style={{ height: "100%" }}>
      <div className="wb-bar">
        <span className="file-tab" style={{ fontFamily: "var(--font-sans)" }}><BackendLogo backend={backend} size={18} />{LANG_LABEL[q.language] ?? q.language}<span className="subtle">· {backend.title}</span></span>
        <span className="spacer" />
        {result?.stats?.series !== undefined && !error && <span className="run-status">{fmtNumber(result.stats.series)} series</span>}
        {result?.stats?.rows !== undefined && !error && <span className="run-status">{fmtNumber(result.stats.rows)} rows</span>}
        <button className="btn btn-ghost btn-sm" onClick={() => onEdit(starter)} disabled={query.trim() === starter}><RotateCcw />Reset</button>
        <button className="btn btn-primary btn-sm" onClick={() => execute()} disabled={busy}>{busy ? <span className="spinner" /> : <Play />}Run query<span className="kbd">{modKey}↵</span></button>
      </div>
      <div className="query-editor grow" style={{ minHeight: 0 }}>
        <Editor value={query} onChange={onEdit} language={lang} onRun={() => execute()} compact placeholder={q.language === "esql" ? "FROM traces-apm* | LIMIT 10" : "rate(http_server_request_duration_seconds_count[1m])"} promqlUrl={lang === "metricsql" ? `${location.origin}/api/proxy/${q.backend}` : undefined} />
      </div>
      {q.examples && q.examples.length > 0 && (
        <div className="query-examples">
          <span className="subtle" style={{ fontSize: 12, alignSelf: "center" }}>Try:</span>
          {q.examples.map((e) => <button key={e.label} onClick={() => { onEdit(e.query); execute(e.query); }} title={e.query}>{e.label}</button>)}
        </div>
      )}
    </div>
  );

  const resultPane = (
    <div className="panel">
      <div className="panel-bar">
        <div className="tabs" role="tablist">
          <button className="tab" role="tab" aria-selected={view === "chart"} onClick={() => setView("chart")} disabled={!result?.series.length}><LineChart />Graph</button>
          <button className="tab" role="tab" aria-selected={view === "table"} onClick={() => setView("table")}><Table2 />Table</button>
        </div>
        <div className="right">
          {lang === "metricsql" && (
            <div className="segmented" role="group" aria-label="Time range">
              {RANGES.map((r) => <button key={r.s} aria-pressed={range === r.s} onClick={() => { setRange(r.s); if (result) execute(query, r.s); }}>{r.l}</button>)}
            </div>
          )}
          {explore && <a className="btn btn-ghost btn-sm" href={explore.url} target="_blank" rel="noreferrer">{explore.label}<ExternalLink /></a>}
        </div>
      </div>
      <div className="panel-body">
        {error && <div className="query-error">{error}</div>}
        {!result && !error && <Empty icon={<Play />} title="Run a query">Results come straight from {backend.title}, against live data from the scenario.</Empty>}
        {result && !error && view === "chart" && result.series.length > 0 && (
          <>
            <div className="chart-wrap"><Chart series={result.series} /></div>
            <div className="chart-legend">
              {result.series.slice(0, 12).map((s, i) => <span key={s.name} title={s.name}><i style={{ background: chartColors[i % chartColors.length] }} />{s.name}</span>)}
              {result.series.length > 12 && <span>+{result.series.length - 12} more</span>}
            </div>
          </>
        )}
        {result && !error && (view === "table" || !result.series.length) && (
          result.rows.length === 0 ? <Empty title="No data">The query ran but returned nothing. Check the metric or index name, and that the scenario is sending traffic.</Empty> : (
            <table className="result-table">
              <thead><tr>{result.columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
              <tbody>
                {result.rows.slice(0, 500).map((row, i) => (
                  <tr key={i}>{row.map((v, j) => <td key={j} className={typeof v === "number" ? "num" : ""} title={String(v)}>{typeof v === "number" ? fmtNumber(v, 4) : String(v ?? "")}</td>)}</tr>
                ))}
              </tbody>
            </table>
          )
        )}
      </div>
    </div>
  );

  return (
    <div className="workbench">
      <Split id="query-v" vertical initial={0.34} min={0.18} max={0.7} first={editorPane} second={resultPane} />
    </div>
  );
}
