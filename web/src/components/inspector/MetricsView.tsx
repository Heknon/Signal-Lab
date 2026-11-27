import { useState } from "react";
import { AlertTriangle, BarChart3, ExternalLink } from "lucide-react";
import type { Backend, Metric, Series } from "../../api";
import { fmtNumber } from "../../lib/format";
import { Empty } from "../ui";

function Sparkline({ points }: { points: number[] }) {
  if (points.length < 2) return <svg className="spark" />;
  const min = Math.min(...points), max = Math.max(...points);
  const range = max - min || 1;
  const d = points.map((p, i) => `${i ? "L" : "M"}${(i / (points.length - 1)) * 72},${20 - ((p - min) / range) * 18}`).join(" ");
  return (
    <svg className="spark" viewBox="0 0 72 22" aria-hidden>
      <path d={d} fill="none" stroke="var(--metric)" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

function Attrs({ attrs }: { attrs: Record<string, unknown> }) {
  const e = Object.entries(attrs);
  if (!e.length) return <span className="subtle" style={{ fontSize: 11.5 }}>no attributes</span>;
  return <>{e.map(([k, v]) => <span key={k} className="attr-chip" title={`${k}=${String(v)}`}>{k}=<b>{String(v)}</b></span>)}</>;
}

function seriesValue(s: Series): number {
  return s.value ?? s.count ?? 0;
}

function Histogram({ s, unit }: { s: Series; unit: string }) {
  if (s.bounds && s.bucket_counts) {
    const counts = s.bucket_counts;
    const max = Math.max(...counts, 1);
    const labels = counts.map((_, i) => (i < s.bounds!.length ? `≤${fmtNumber(s.bounds![i], 2)}` : `>${fmtNumber(s.bounds![s.bounds!.length - 1], 2)}`));
    const avg = s.count ? (s.sum ?? 0) / s.count : null;
    return (
      <div className="stack" style={{ gap: 8 }}>
        <div className="hist" role="img" aria-label="Bucket counts">
          {counts.map((c, i) => (
            <div key={i} className="hist-col" title={`${labels[i]}${unit ? " " + unit : ""}: ${c}`}>
              <div className="hist-bar" data-count={c} style={{ height: `${(c / max) * 100}%` }} />
            </div>
          ))}
        </div>
        <div className="hist-labels">{labels.map((l, i) => <span key={i}>{l}</span>)}</div>
        <dl className="hist-stats">
          <div><dt>count</dt><dd>{fmtNumber(s.count)}</dd></div>
          <div><dt>sum</dt><dd>{fmtNumber(s.sum)}</dd></div>
          <div><dt>avg</dt><dd>{fmtNumber(avg)}</dd></div>
          <div><dt>max</dt><dd>{fmtNumber(s.max)}</dd></div>
        </dl>
      </div>
    );
  }
  if (s.positive) {
    return (
      <div className="stack" style={{ gap: 6 }}>
        <div className="muted" style={{ fontSize: 12 }}>Exponential histogram · scale {s.scale} · {s.positive.bucket_counts.length} buckets</div>
        <div className="hist">
          {s.positive.bucket_counts.map((c, i) => {
            const max = Math.max(...s.positive!.bucket_counts, 1);
            return <div key={i} className="hist-col"><div className="hist-bar" data-count={c} style={{ height: `${(c / max) * 100}%` }} /></div>;
          })}
        </div>
        <dl className="hist-stats">
          <div><dt>count</dt><dd>{fmtNumber(s.count)}</dd></div>
          <div><dt>sum</dt><dd>{fmtNumber(s.sum)}</dd></div>
          <div><dt>min</dt><dd>{fmtNumber(s.min)}</dd></div>
          <div><dt>max</dt><dd>{fmtNumber(s.max)}</dd></div>
        </dl>
      </div>
    );
  }
  return null;
}

const INSTRUMENT_HELP: Record<string, string> = {
  counter: "Only goes up. Query it with rate() or increase().",
  updowncounter: "Goes up and down: a current total, like items in a queue.",
  gauge: "A sampled value at a point in time.",
  histogram: "A distribution: bucket counts, sum and count. Query percentiles with histogram_quantile().",
};

function MetricCard({ m, backends, onExemplar }: { m: Metric; backends: Backend[]; onExemplar?: (traceId: string, spanId: string | null) => void }) {
  const [sel, setSel] = useState(0);
  const series = m.series;
  const isHist = m.instrument === "histogram";
  const single = series.length === 1;
  const selected = series[Math.min(sel, series.length - 1)];
  const exemplar = series.flatMap((s) => s.exemplars ?? []).find((e) => e.trace_id);
  const metricLinks = backends.filter((b) => b.enabled && b.capabilities.includes("metrics") && b.links.some((l) => l.id === "explore"));
  return (
    <div className="card metric-card">
      <div className="metric-head">
        <div style={{ minWidth: 0 }}>
          <div className="metric-name">{m.name}</div>
          {m.description && <div className="metric-desc">{m.description}</div>}
        </div>
        <div className="badges">
          <span className="badge badge-metric" title={INSTRUMENT_HELP[m.instrument]}>{m.instrument}</span>
          {m.unit && <span className="badge badge-outline mono" title="unit">{m.unit}</span>}
        </div>
      </div>
      {series.length > 20 && (
        <div className={`cardinality ${series.length > 100 ? "danger" : ""}`}>
          <AlertTriangle />
          <span><b>{series.length} time series</b> from one metric. Every unique attribute combination is a new series that the backend stores and indexes.</span>
        </div>
      )}
      {!isHist && single && (
        <div className="row" style={{ justifyContent: "space-between" }}>
          <div className="metric-big">{fmtNumber(seriesValue(series[0]))}<small>{m.unit}</small></div>
          <Sparkline points={series[0].history.map((h) => h.value ?? 0)} />
        </div>
      )}
      {isHist && selected && <Histogram s={selected} unit={m.unit} />}
      {(!single || isHist) && (
        <table className="series-table">
          <thead><tr><th>Attributes</th><th style={{ textAlign: "right" }}>{isHist ? "count" : "value"}</th>{!isHist && <th />}</tr></thead>
          <tbody>
            {series.slice(0, 50).map((s, i) => (
              <tr key={s.key} onClick={() => setSel(i)} style={{ cursor: isHist ? "pointer" : undefined, background: isHist && i === sel && series.length > 1 ? "var(--surface-2)" : undefined }}>
                <td><Attrs attrs={s.attributes} /></td>
                <td className="v">{fmtNumber(seriesValue(s))}</td>
                {!isHist && <td style={{ width: 80 }}><Sparkline points={s.history.map((h) => h.value ?? 0)} /></td>}
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {series.length > 50 && <div className="subtle" style={{ fontSize: 12 }}>…and {series.length - 50} more series</div>}
      <div className="row" style={{ fontSize: 11.5, color: "var(--text-3)", flexWrap: "wrap" }}>
        <span>{m.service}</span>
        {m.temporality && <span>· {m.temporality}</span>}
        {exemplar && onExemplar && (
          <button className="trace-link" onClick={() => onExemplar(exemplar.trace_id!, exemplar.span_id)}>· exemplar → trace</button>
        )}
        <span className="grow" />
        {metricLinks.map((b) => <a key={b.id} className="trace-link" style={{ color: "var(--metric)" }} href={b.links.find((l) => l.id === "explore")!.url} target="_blank" rel="noreferrer">Explore<ExternalLink /></a>)}
      </div>
    </div>
  );
}

export default function MetricsView({ metrics, backends, onExemplar }: { metrics: Metric[]; backends: Backend[]; onExemplar?: (traceId: string, spanId: string | null) => void }) {
  if (!metrics.length) {
    return <Empty icon={<BarChart3 />} title="No metrics yet">Metrics are exported on an interval and when the program exits, so they land a moment after spans.</Empty>;
  }
  return (
    <div className="metrics-grid">
      {metrics.map((m) => <MetricCard key={m.name + m.service} m={m} backends={backends} onExemplar={onExemplar} />)}
    </div>
  );
}
