import { Link } from "react-router-dom";
import { ArrowRight, Boxes, Code2, ExternalLink, Lock, Radio, Server, Sparkles, Database, Gauge, Search } from "lucide-react";
import type { Pack } from "../api";
import { useLab, type FlatLesson } from "../context";
import { lessonState, progress, useProgress, type Progress } from "../lib/progress";
import TopBar from "../components/TopBar";
import { BackendLogo, KindLabel, SignalBadge, StateIcon } from "../components/ui";

const PACK_ICON: Record<string, React.ReactNode> = { radio: <Radio />, gauge: <Gauge />, search: <Search />, database: <Database />, boxes: <Boxes /> };

function nextLesson(lessons: FlatLesson[], p: Progress): FlatLesson | undefined {
  const open = (l: FlatLesson) => lessonState(p, l.id) === "todo" && !l.pack.locked;
  const last = lessons.findIndex((l) => l.id === p.last);
  if (last >= 0 && lessonState(p, lessons[last].id) === "todo") return lessons[last];
  return lessons.slice(last + 1).find(open) ?? lessons.find(open);
}

function TrackCard({ pack }: { pack: Pack }) {
  const p = useProgress();
  const all = pack.modules.flatMap((m) => m.lessons);
  const done = all.filter((l) => p.completed[l.id]).length;
  const known = all.filter((l) => p.known[l.id]).length;
  const minutes = all.reduce((a, l) => a + l.minutes, 0);
  return (
    <section className="card track" aria-labelledby={`track-${pack.id}`}>
      <div className="track-head">
        <span className="track-icon">{PACK_ICON[pack.icon ?? ""] ?? <Radio />}</span>
        <div>
          <h3 id={`track-${pack.id}`}>{pack.title}</h3>
          <p>{pack.description}</p>
        </div>
        <div className="track-meta">
          <span className="subtle" style={{ fontSize: 12 }}>{all.length} lessons · ~{Math.round(minutes / 5) * 5 || minutes} min</span>
          <div className="progress-bar" aria-label={`${done} done, ${known} known of ${all.length}`}>
            <span className="done" style={{ width: `${(done / Math.max(1, all.length)) * 100}%` }} />
            <span className="known" style={{ width: `${(known / Math.max(1, all.length)) * 100}%` }} />
          </div>
        </div>
      </div>
      {pack.locked && (
        <div className="locked-note"><Lock /><span>Needs the {pack.missing.backends.map((b) => <code key={b}>{b}</code>)} backend plugin. Enable it with <code>./lab use {[...pack.missing.backends].join(" ")}</code>.</span></div>
      )}
      {pack.modules.map((m) => {
        const ids = m.lessons.map((l) => l.id);
        const allKnownOrDone = ids.every((i) => lessonState(p, i) !== "todo");
        const anyKnown = ids.some((i) => p.known[i]);
        return (
          <div key={m.id} className="module">
            <div className="module-info">
              <h4>{m.title}</h4>
              {m.description && <p>{m.description}</p>}
              {m.assumes.length > 0 && <div className="assumes">Assumes {m.assumes.map((a) => <span key={a} className="badge badge-outline">{a}</span>)}</div>}
              <div className="module-actions">
                {!allKnownOrDone ? (
                  <button className="btn btn-ghost btn-sm" style={{ marginLeft: -9 }} onClick={() => progress.setKnown(ids, true)} title="Skip this module: mark every lesson as known">Skip, I know this</button>
                ) : anyKnown ? (
                  <button className="btn btn-ghost btn-sm" style={{ marginLeft: -9 }} onClick={() => progress.setKnown(ids, false)}>Unmark known</button>
                ) : null}
              </div>
            </div>
            <ul className="lesson-list">
              {m.lessons.map((l) => (
                <li key={l.id}>
                  <Link to={`/learn/${l.id}`} className={`lesson-row ${pack.locked ? "locked" : ""}`}>
                    <StateIcon state={lessonState(p, l.id)} />
                    <span className="stack" style={{ minWidth: 0 }}>
                      <span className="title">{l.title}</span>
                      <span className="summary">{l.summary}</span>
                    </span>
                    <span className="meta"><KindLabel kind={l.kind} /><span>{l.minutes}m</span></span>
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </section>
  );
}

export default function Home() {
  const { meta, course, lessons, error } = useLab();
  const p = useProgress();
  const next = nextLesson(lessons, p);
  const total = lessons.length;
  const done = lessons.filter((l) => p.completed[l.id]).length;
  const known = lessons.filter((l) => p.known[l.id]).length;
  const started = done + known > 0 || !!p.last;
  const enabled = meta?.backends.filter((b) => b.enabled) ?? [];
  const available = meta?.backends.filter((b) => !b.enabled) ?? [];

  return (
    <div className="app">
      <TopBar />
      <main className="page">
        <div className="home">
          {error && <div className="scenario-banner">Can't reach the lab API: {error.message}</div>}
          <section className="hero">
            <div>
              <span className="badge badge-ok"><Sparkles />Interactive OpenTelemetry course</span>
              <h1>Learn observability by sending <em>real signals</em>.</h1>
              <p className="lead">Write Python with the real OpenTelemetry SDK, watch traces, metrics and logs flow through a Collector, then find them in {enabled.length ? enabled.map((b) => b.title).join(" and ") : "your backends"}. Every exercise is checked against the telemetry you actually produce.</p>
              <div className="hero-actions">
                {next && (
                  <Link to={`/learn/${next.id}`} className="btn btn-primary btn-lg">{started ? "Continue" : "Start learning"}<ArrowRight /></Link>
                )}
                {next && started && <span className="muted" style={{ fontSize: 13 }}>Next: <b style={{ color: "var(--text)", fontWeight: 550 }}>{next.title}</b></span>}
              </div>
            </div>
            <div className="card hero-progress">
              <div className="row"><span className="eyebrow">Your progress</span><span className="grow" /><span className="subtle" style={{ fontSize: 12 }}>{done} done · {known} skipped · {total} total</span></div>
              <div className="progress-bar">
                <span className="done" style={{ width: `${(done / Math.max(1, total)) * 100}%` }} />
                <span className="known" style={{ width: `${(known / Math.max(1, total)) * 100}%` }} />
              </div>
              <div className="signal-flow" style={{ marginTop: 6 }} aria-label="How signals flow">
                <span className="flow-node"><Code2 />your code</span><span className="flow-arrow">→</span>
                <span className="flow-node">OTel SDK</span><span className="flow-arrow">→</span>
                {meta?.collector !== false && <><span className="flow-node"><Server />Collector</span><span className="flow-arrow">→</span></>}
                {enabled.map((b) => <span key={b.id} className="flow-node"><BackendLogo backend={b} size={14} />{b.title.split(" ")[0]}</span>)}
                {!enabled.length && <span className="flow-node">lab inspector</span>}
              </div>
              <p className="subtle" style={{ margin: 0, fontSize: 12 }}>Progress is saved in this browser. Skip anything you know; nothing is locked behind earlier lessons.</p>
            </div>
          </section>

          <section className="section" aria-labelledby="stack-h">
            <div className="section-head">
              <div><h2 id="stack-h">Your stack</h2><p>Backends are plugins. The same lessons work whichever ones you enable.</p></div>
              <Link to="/stack" className="btn btn-ghost btn-sm">Pipeline &amp; plugins<ArrowRight /></Link>
            </div>
            <div className="stack-grid">
              {enabled.map((b) => (
                <div key={b.id} className="card backend-card">
                  <div className="backend-head"><BackendLogo backend={b} /><div><h3>{b.title}</h3><span className="subtle" style={{ fontSize: 11.5 }}>{b.vendor}</span></div></div>
                  <div className="row" style={{ gap: 4, flexWrap: "wrap" }}>{b.capabilities.map((c) => <SignalBadge key={c} signal={c} />)}</div>
                  <div className="backend-links">{b.links.slice(0, 3).map((l) => <a key={l.id} href={l.url} target="_blank" rel="noreferrer">{l.label}<ExternalLink /></a>)}</div>
                </div>
              ))}
              {available.map((b) => (
                <div key={b.id} className="card backend-card disabled">
                  <div className="backend-head"><BackendLogo backend={b} /><div><h3>{b.title}</h3><span className="subtle" style={{ fontSize: 11.5 }}>Available plugin</span></div></div>
                  <p>{b.description}</p>
                  <code className="subtle" style={{ fontSize: 11.5 }}>./lab use … {b.id}</code>
                </div>
              ))}
            </div>
          </section>

          <section className="section" aria-labelledby="course-h">
            <div className="section-head">
              <div><h2 id="course-h">Course</h2><p>Tracks are split into modules you can take in any order. Skip a module if you already know it.</p></div>
            </div>
            {course.map((pack) => <TrackCard key={pack.id} pack={pack} />)}
          </section>
        </div>
      </main>
    </div>
  );
}
