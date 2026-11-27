import { Link } from "react-router-dom";
import { ArrowRight, ExternalLink, Lock } from "lucide-react";
import type { Pack } from "../api";
import { useLab, type FlatLesson } from "../context";
import { lessonState, progress, useProgress, type Progress } from "../lib/progress";
import TopBar from "../components/TopBar";
import { KindLabel, StateIcon } from "../components/ui";

function nextLesson(lessons: FlatLesson[], p: Progress): FlatLesson | undefined {
  const open = (l: FlatLesson) => lessonState(p, l.id) === "todo" && !l.pack.locked;
  const last = lessons.findIndex((l) => l.id === p.last);
  if (last >= 0 && lessonState(p, lessons[last].id) === "todo" && !lessons[last].pack.locked) return lessons[last];
  return lessons.slice(last + 1).find(open) ?? lessons.find(open);
}

function Bar({ done, known, total, width }: { done: number; known: number; total: number; width?: number }) {
  return (
    <div className="progress-bar" style={width ? { width } : undefined} role="progressbar" aria-valuemin={0} aria-valuemax={total} aria-valuenow={done + known}>
      <span className="done" style={{ width: `${(done / Math.max(1, total)) * 100}%` }} />
      <span className="known" style={{ width: `${(known / Math.max(1, total)) * 100}%` }} />
    </div>
  );
}

function Track({ pack }: { pack: Pack }) {
  const p = useProgress();
  const all = pack.modules.flatMap((m) => m.lessons);
  const done = all.filter((l) => p.completed[l.id]).length;
  const known = all.filter((l) => p.known[l.id]).length;
  return (
    <section className="track" aria-labelledby={`track-${pack.id}`}>
      <header className="track-head">
        <h2 id={`track-${pack.id}`}>{pack.title}</h2>
        <span className="track-count">{done + known} / {all.length}</span>
        <Bar done={done} known={known} total={all.length} width={88} />
      </header>
      {pack.locked && (
        <div className="locked-note">
          <Lock />
          <span>Needs the {pack.missing.backends.join(", ")} backend.</span>
          <code>./lab use {[...pack.missing.backends].join(" ")}</code>
        </div>
      )}
      <div className="track-body">
        {pack.modules.map((m) => {
          const ids = m.lessons.map((l) => l.id);
          const settled = ids.every((i) => lessonState(p, i) !== "todo");
          const anyKnown = ids.some((i) => p.known[i]);
          return (
            <div key={m.id} className="module">
              <div className="module-info">
                <h3>{m.title}</h3>
                {m.assumes.length > 0 && <p className="assumes">Assumes: {m.assumes.join(", ")}</p>}
                {!settled ? (
                  <button className="link-btn" onClick={() => progress.setKnown(ids, true)}>Skip module</button>
                ) : anyKnown ? (
                  <button className="link-btn" onClick={() => progress.setKnown(ids, false)}>Undo skip</button>
                ) : null}
              </div>
              <ul className="lesson-list">
                {m.lessons.map((l) => (
                  <li key={l.id}>
                    <Link to={`/learn/${l.id}`} className={`lesson-row ${pack.locked ? "locked" : ""}`} title={l.summary}>
                      <StateIcon state={lessonState(p, l.id)} />
                      <span className="title">{l.title}</span>
                      <span className="meta">{l.kind !== "code" && <KindLabel kind={l.kind} />}<span className="mins">{l.minutes} min</span></span>
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>
    </section>
  );
}

export default function Home() {
  const { meta, health, course, lessons, error } = useLab();
  const p = useProgress();
  const next = nextLesson(lessons, p);
  const total = lessons.length;
  const done = lessons.filter((l) => p.completed[l.id]).length;
  const known = lessons.filter((l) => p.known[l.id]).length;
  const started = done + known > 0 || !!p.last;
  const enabled = meta?.backends.filter((b) => b.enabled) ?? [];
  const codeLessons = lessons.filter((l) => l.kind === "code").length;

  return (
    <div className="app">
      <TopBar />
      <main className="page">
        <div className="home">
          {error && <div className="banner">Can't reach the lab API: {error.message}</div>}
          <section className="intro">
            <div className="intro-text">
              <h1>OpenTelemetry, hands on</h1>
              <p>
                {total} lessons, {codeLessons} of them in Python against the real SDK. Your telemetry goes through a Collector to{" "}
                {enabled.length ? new Intl.ListFormat("en", { type: "conjunction" }).format(enabled.map((b) => b.title)) : "the lab"}, and each exercise is graded on what arrives.
              </p>
            </div>
            {next && (
              <div className="resume">
                <div className="resume-progress">
                  <span>{done} done{known ? ` · ${known} skipped` : ""} · {total} total</span>
                  <Bar done={done} known={known} total={total} />
                </div>
                <Link to={`/learn/${next.id}`} className="btn btn-primary btn-lg resume-btn">
                  <span>{started ? "Continue" : "Start"}: {next.title}</span>
                  <ArrowRight />
                </Link>
              </div>
            )}
          </section>

          {enabled.length > 0 && (
            <div className="stack-strip" aria-label="Backends">
              {enabled.map((b) => {
                const h = health?.backends[b.id];
                const ok = h ? Object.values(h).every((c) => c.ok) : null;
                return (
                  <div key={b.id} className="strip-item">
                    <span className={`dot ${ok == null ? "dot-idle" : ok ? "dot-ok" : "dot-err"}`} title={ok == null ? "checking" : ok ? "healthy" : "unreachable"} />
                    <span className="strip-name">{b.title}</span>
                    {b.links.slice(0, 2).map((l) => <a key={l.id} href={l.url} target="_blank" rel="noreferrer">{l.label}<ExternalLink /></a>)}
                  </div>
                );
              })}
              <Link to="/stack" className="strip-more">Pipeline &amp; plugins<ArrowRight /></Link>
            </div>
          )}

          {course.map((pack) => <Track key={pack.id} pack={pack} />)}
        </div>
      </main>
    </div>
  );
}
