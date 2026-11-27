import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, ArrowRight, Check, ChevronRight, Eye, FlaskConical, Lightbulb, Lock, RotateCcw, SkipForward, X } from "lucide-react";
import { api, type CheckResult, type Lesson } from "../api";
import { useLab, type FlatLesson } from "../context";
import { useAsync, useHotkey } from "../lib/hooks";
import { lessonState, progress, useProgress } from "../lib/progress";
import CodeWorkbench from "../components/CodeWorkbench";
import QueryWorkbench from "../components/QueryWorkbench";
import { QuizWorkbench, TaskWorkbench, ToolLinks } from "../components/QuizWorkbench";
import Markdown from "../components/Markdown";
import TopBar from "../components/TopBar";
import { Empty, InlineCode, Split, StateIcon } from "../components/ui";

function Sidebar({ current }: { current: FlatLesson }) {
  const { course } = useLab();
  const p = useProgress();
  const nav = useNavigate();
  const pack = current.pack;
  return (
    <nav className="sidebar" aria-label="Course outline">
      <div className="sidebar-pack">
        {course.length > 1 ? (
          <select className="select" value={pack.id} onChange={(e) => {
            const target = course.find((c) => c.id === e.target.value);
            const first = target?.modules[0]?.lessons[0];
            if (first) nav(`/learn/${first.id}`);
          }} aria-label="Switch track">
            {course.map((c) => <option key={c.id} value={c.id}>{c.title}{c.locked ? " (needs plugin)" : ""}</option>)}
          </select>
        ) : <div style={{ fontWeight: 600 }}>{pack.title}</div>}
      </div>
      {pack.modules.map((m) => {
        const done = m.lessons.filter((l) => lessonState(p, l.id) !== "todo").length;
        return (
          <div key={m.id} className="outline-module">
            <div className="outline-module-head">{m.title}<span className="count">{done}/{m.lessons.length}</span></div>
            {m.lessons.map((l) => (
              <Link key={l.id} to={`/learn/${l.id}`} className={`outline-lesson ${l.id === current.id ? "active" : ""}`} aria-current={l.id === current.id ? "page" : undefined}>
                <StateIcon state={lessonState(p, l.id)} current={l.id === current.id} />
                <span className="t">{l.title}</span>
              </Link>
            ))}
          </div>
        );
      })}
    </nav>
  );
}

function Goals({ lesson, results }: { lesson: Lesson; results: CheckResult[] }) {
  const p = useProgress();
  const byId = new Map(results.map((r) => [r.id, r]));
  // Quiz questions are their own goals; listing "Question 1..n" again is noise.
  const items = lesson.kind === "quiz" ? [] : lesson.checks.map((c) => ({ id: c.id, title: c.title }));
  const passed = items.filter((i) => byId.get(i.id)?.status === "pass").length;
  const complete = items.length > 0 && passed === items.length;
  if (!items.length) return null;
  const wasDone = !!p.completed[lesson.id];
  return (
    <section className={`card goals ${complete ? "complete" : ""}`} aria-label="Goals">
      <div className="goals-head">
        {complete ? "All goals met" : "Goals"}
        <span className="progress-text">{passed}/{items.length}</span>
      </div>
      {items.map((it) => {
        const r = byId.get(it.id);
        const st = r?.status;
        return (
          <div key={it.id} className={`goal ${st ?? ""}`}>
            <span className={`goal-status ${st ?? ""}`}>{st === "pass" ? <Check /> : st === "fail" ? <X /> : st === "pending" ? <span className="spinner" style={{ width: 9, height: 9, borderWidth: 1.5 }} /> : null}</span>
            <div style={{ minWidth: 0 }}>
              <div className="goal-title"><InlineCode text={it.title} /></div>
              {r?.detail && st !== "pass" && <div className="goal-detail"><InlineCode text={r.detail} /></div>}
            </div>
          </div>
        );
      })}
      {!results.length && wasDone && <div className="goals-foot"><Check style={{ width: 14, height: 14, color: "var(--accent)" }} />You completed this lesson before. Run it again any time.</div>}
    </section>
  );
}

function Hints({ hints }: { hints: string[] }) {
  const [shown, setShown] = useState(0);
  if (!hints.length) return null;
  return (
    <details className="disclosure">
      <summary><Lightbulb />Hints<span className="subtle" style={{ fontWeight: 400 }}>{shown}/{hints.length}</span><ChevronRight className="chev" /></summary>
      {shown > 0 && <div className="disclosure-body"><ol>{hints.slice(0, shown).map((h, i) => <li key={i}><InlineCode text={h} /></li>)}</ol></div>}
      {shown < hints.length && <div className="hint-reveal"><button className="btn btn-sm" onClick={() => setShown((s) => s + 1)}>{shown ? "Another hint" : "Show a hint"}</button></div>}
    </details>
  );
}

export default function LessonPage() {
  const { pack = "", slug = "" } = useParams();
  const id = `${pack}/${slug}`;
  const { findLesson, lessons, meta, toast, setScenarioOpen } = useLab();
  const flat = findLesson(id);
  const lesson = useAsync(() => api.lesson(id), [id]);
  const p = useProgress();
  const [results, setResults] = useState<CheckResult[]>([]);
  const wide = typeof window !== "undefined" && window.innerWidth > 1100;
  const [sidebarOpen, setSidebarOpen] = useState(() => { try { return wide && localStorage.getItem("sl-sidebar") !== "0"; } catch { return wide; } });
  const [scenarioNote, setScenarioNote] = useState<string[] | null>(null);
  const nav = useNavigate();

  useEffect(() => { setResults([]); setScenarioNote(null); progress.visit(id); if (!wide) setSidebarOpen(false); }, [id]);
  useEffect(() => {
    const l = lesson.data;
    if (l?.scenario && (l.scenario.chaos || l.scenario.load !== undefined)) {
      api.setup(l.id).then((r) => setScenarioNote(r.applied)).catch(() => undefined);
    }
  }, [lesson.data]);
  const toggleSidebar = () => setSidebarOpen((v) => { if (wide) { try { localStorage.setItem("sl-sidebar", v ? "0" : "1"); } catch { /* ignore */ } } return !v; });
  useHotkey("[", (e) => { if (!(e.target as HTMLElement).closest(".cm-editor, input, textarea")) toggleSidebar(); });

  const onChecks = useCallback((c: CheckResult[]) => setResults(c), []);
  const onComplete = useCallback(() => {
    if (!progress) return;
    const already = !!p.completed[id];
    progress.complete(id);
    if (!already) toast("Lesson complete");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, toast]);

  // A lesson is complete when every goal passes (every question, for quizzes).
  const required = (l0: Lesson) => (l0.kind === "quiz" ? (l0.quiz?.questions ?? []).map((q) => q.id) : l0.checks.map((c) => c.id));
  useEffect(() => {
    const l0 = lesson.data;
    if (!l0) return;
    const ids = required(l0);
    const passed = new Set(results.filter((r) => r.status === "pass").map((r) => r.id));
    if (ids.length > 0 && ids.every((x) => passed.has(x))) onComplete();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [results, lesson.data, onComplete]);

  const neighbours = useMemo(() => {
    if (!flat) return { prev: undefined, next: undefined };
    return { prev: lessons[flat.index - 1], next: lessons[flat.index + 1] };
  }, [flat, lessons]);

  const l = lesson.data;
  const state = lessonState(p, id);
  const complete = state === "done";
  const crumbs = flat ? [
    { label: flat.pack.title, to: "/", hideSm: true },
    { label: flat.module.title, hideSm: true },
    { label: flat.title },
  ] : [];
  const locked = flat?.pack.locked;
  const posInModule = flat ? flat.module.lessons.findIndex((x) => x.id === id) + 1 : 0;

  const prose = (
    <div className="lesson-pane">
      {lesson.error && <Empty title="Lesson not found">{lesson.error.message}</Empty>}
      {l && (
        <article className="lesson-inner">
          <div className="lesson-meta">
            {flat && <span>{flat.module.title} {posInModule}/{flat.module.lessons.length}</span>}
            <span>{l.minutes} min</span>
            {l.assumes.length > 0 && <span>Assumes: {l.assumes.join(", ")}</span>}
          </div>
          <h1>{l.title}</h1>
          <div className="lesson-actions">
            {state === "known" ? (
              <button className="btn btn-ghost btn-sm" onClick={() => progress.setKnown([id], false)}><RotateCcw />Unmark known</button>
            ) : !complete && (
              <button className="btn btn-ghost btn-sm" onClick={() => { progress.setKnown([id], true); if (neighbours.next) nav(`/learn/${neighbours.next.id}`); }} title="Mark as known and move on"><SkipForward />I know this</button>
            )}
            {l.solution && (l.kind === "code" || l.kind === "collector") && <button className="btn btn-ghost btn-sm" onClick={() => window.dispatchEvent(new Event("sl:show-solution"))}><Eye />Solution</button>}
          </div>
          {locked && (
            <div className="scenario-banner"><Lock /><span>This track needs the <b>{flat?.pack.missing.backends.join(", ")}</b> backend plugin. You can read along, but queries and checks won't work until it's enabled.</span></div>
          )}
          {scenarioNote && scenarioNote.length > 0 && (
            <div className="scenario-banner">
              <FlaskConical />
              <span>{l.scenario?.note ?? "This lesson changed the scenario."} Faults are active on <b>{scenarioNote.join(", ")}</b>. <a href="#" onClick={(e) => { e.preventDefault(); setScenarioOpen(true); }} style={{ textDecoration: "underline" }}>Open scenario</a></span>
            </div>
          )}
          <Goals lesson={l} results={results} />
          <Markdown>{l.body}</Markdown>
          {l.kind === "code" && l.tools.length > 0 && <div style={{ margin: "8px 0 20px" }}><ToolLinks tools={l.tools} /></div>}
          <Hints key={l.id} hints={l.hints} />
          <nav className="pager" aria-label="Lesson navigation">
            {neighbours.prev ? <Link className="prev" to={`/learn/${neighbours.prev.id}`}><ArrowLeft />{neighbours.prev.title}</Link> : <span />}
            {neighbours.next && <Link className={`next ${complete ? "highlight" : ""}`} to={`/learn/${neighbours.next.id}`}>{neighbours.next.title}<ArrowRight /></Link>}
          </nav>
        </article>
      )}
    </div>
  );

  let workbench: React.ReactNode = null;
  if (l) {
    if (l.kind === "code" || l.kind === "collector") workbench = <CodeWorkbench lesson={l} onChecks={onChecks} />;
    else if (l.kind === "query" && l.query) workbench = <QueryWorkbench lesson={l} onChecks={onChecks} />;
    else if (l.kind === "quiz") workbench = <QuizWorkbench lesson={l} onChecks={onChecks} />;
    else if (l.kind === "task") workbench = <TaskWorkbench lesson={l} onChecks={onChecks} />;
  }

  return (
    <div className="app">
      <TopBar crumbs={crumbs} onToggleSidebar={toggleSidebar} />
      <div className={`lesson-layout ${sidebarOpen ? "sidebar-open" : "collapsed"}`}>
        {flat ? <Sidebar current={flat} /> : <div />}
        {workbench ? (
          <Split id="lesson-h" initial={0.42} min={0.26} max={0.7} className="responsive" first={prose} second={workbench} secondClass="workbench-pane" />
        ) : prose}
      </div>
      {!meta && <div />}
    </div>
  );
}
