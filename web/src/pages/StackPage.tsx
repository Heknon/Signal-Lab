import { ExternalLink, FileCode2, Puzzle } from "lucide-react";
import { api } from "../api";
import { useLab } from "../context";
import { useAsync } from "../lib/hooks";
import { highlight } from "../lib/highlight";
import TopBar from "../components/TopBar";
import { BackendLogo, SignalBadge } from "../components/ui";

const SIGNAL_OF = (name: string) => name.split("/")[0];

export default function StackPage() {
  const { meta, health } = useLab();
  const collector = useAsync(api.collector, []);
  const plugins = useAsync(api.plugins, []);
  const pipelines = Object.entries(collector.data?.pipelines ?? {});

  return (
    <div className="app">
      <TopBar crumbs={[{ label: "Stack & plugins" }]} />
      <main className="page">
        <div className="stack-page">
          <h1>Stack &amp; plugins</h1>
          <p className="muted" style={{ margin: "0 0 28px", fontSize: 14 }}>What's running, how telemetry flows through the Collector, and which plugins are loaded.</p>

          <section className="section" style={{ paddingTop: 0 }}>
            <div className="section-head"><div><h2>Collector pipelines</h2><p>Every pipeline starts at the same OTLP receiver, so each signal fans out to every backend and to the lab's live inspector.</p></div></div>
            <div className="card">
              {pipelines.length === 0 ? (
                <div className="pipeline"><span className="muted">{meta?.collector ? "Collector config not mounted into the lab." : "Dev mode: the SDK exports straight to the lab's tap, with no Collector in between."}</span></div>
              ) : (
                <div className="pipeline">
                  {pipelines.map(([name, p]) => {
                    const sig = SIGNAL_OF(name);
                    return (
                      <div key={name} style={{ display: "contents" }}>
                        <span className="pipeline-name"><span className={`badge ${sig === "traces" ? "badge-trace" : sig === "metrics" ? "badge-metric" : "badge-log"}`}>{name}</span></span>
                        <div className="pipeline-flow">
                          {(p.receivers ?? []).map((r) => <span key={r} className="comp receiver">{r}</span>)}
                          <span className="arrow">→</span>
                          {(p.processors ?? []).map((r) => <span key={r} className="comp processor">{r}</span>)}
                          <span className="arrow">→</span>
                          {(p.exporters ?? []).map((r) => <span key={r} className="comp exporter">{r}</span>)}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
              {collector.data?.files.map((f) => (
                <details key={f.path} className="plugin-row" style={{ display: "block", padding: 0 }}>
                  <summary style={{ cursor: "pointer", padding: "10px 16px", display: "flex", gap: 8, alignItems: "center", fontSize: 12.5 }}><FileCode2 style={{ width: 14, height: 14 }} /><span className="mono">{f.path}</span></summary>
                  <pre className="code-block mono">{highlight(f.content, "yaml")}</pre>
                </details>
              ))}
            </div>
          </section>

          <section className="section">
            <div className="section-head"><div><h2>Backends</h2><p>Each backend is a folder in <code>plugins/backends/</code> with a manifest, Compose file, Collector fragment and adapter.</p></div></div>
            <div className="card">
              {(plugins.data?.backends ?? []).map((b) => (
                <div key={b.id} className="plugin-row">
                  <div>
                    <h4><BackendLogo backend={b} size={20} />{b.title}{b.enabled ? <span className="badge badge-ok">enabled</span> : <span className="badge">available</span>}</h4>
                    <p>{b.description}</p>
                    <div className="row" style={{ marginTop: 6, flexWrap: "wrap", gap: 4 }}>
                      {b.capabilities.map((c) => <SignalBadge key={c} signal={c} />)}
                      {b.query_languages.map((q) => <span key={q} className="badge badge-outline mono">{q}</span>)}
                      <span className="path">plugins/{b.path}</span>
                    </div>
                    {b.enabled && (
                      <div className="health-grid">
                        {b.components.map((c) => {
                          const h = health?.backends[b.id]?.[c.id];
                          return <span key={c.id} className="badge badge-outline"><span className={`dot ${!h ? "dot-idle" : h.ok ? "dot-ok" : "dot-err"}`} />{c.title}<span className="subtle">{h?.detail}</span></span>;
                        })}
                      </div>
                    )}
                  </div>
                  <div className="backend-links" style={{ justifyContent: "flex-end", maxWidth: 260 }}>
                    {b.enabled && b.links.map((l) => <a key={l.id} href={l.url} target="_blank" rel="noreferrer">{l.label}<ExternalLink /></a>)}
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="section">
            <div className="section-head"><div><h2>Lesson packs &amp; scenarios</h2><p>Lessons are Markdown + Python + YAML checks. Add a folder to <code>plugins/lessons/</code> to extend the course.</p></div></div>
            <div className="card">
              {(plugins.data?.lesson_packs ?? []).map((p) => (
                <div key={p.id} className="plugin-row">
                  <div><h4><Puzzle style={{ width: 15, height: 15, color: "var(--text-3)" }} />{p.title}<span className="badge">{p.lessons} lessons</span></h4><p>{p.description}</p><span className="path">plugins/{p.path}</span></div>
                  <div>{(p.requires.backends ?? []).map((b) => <span key={b} className="badge badge-outline">needs {b}</span>)}</div>
                </div>
              ))}
              {(plugins.data?.scenarios ?? []).map((s) => (
                <div key={s.id} className="plugin-row">
                  <div><h4>{s.title}<span className="badge badge-warn">scenario</span></h4><p>{s.description}</p><span className="path">plugins/{s.path}</span></div>
                  <div className="row" style={{ flexWrap: "wrap", gap: 4, justifyContent: "flex-end" }}>{s.services.map((x) => <span key={x.id} className="badge badge-outline mono">{x.id}</span>)}</div>
                </div>
              ))}
            </div>
            {plugins.data && (
              <p className="subtle" style={{ fontSize: 12.5, marginTop: 12 }}>
                Check types: {plugins.data.check_types.map((c) => <code key={c} style={{ marginRight: 6 }}>{c}</code>)}
                {meta && <> · runner: {meta.runner} · OTLP endpoint for learner code: <code>{meta.otlp_endpoint}</code></>}
              </p>
            )}
            {plugins.data?.errors.length ? <div className="query-error">{plugins.data.errors.join("\n")}</div> : null}
          </section>
        </div>
      </main>
    </div>
  );
}
