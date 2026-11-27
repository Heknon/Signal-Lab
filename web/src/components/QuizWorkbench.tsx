import { useEffect, useState } from "react";
import { ArrowUpRight, CheckCircle2, ClipboardCheck, XCircle } from "lucide-react";
import { api, type Backend, type CheckResult, type Lesson } from "../api";
import { useLab } from "../context";
import { BackendLogo, Empty, InlineCode } from "./ui";

/** Links into backend UIs that a lesson asks you to use, e.g. `elastic:apm`. */
export function ToolLinks({ tools }: { tools: string[] }) {
  const { meta } = useLab();
  const resolved = tools.flatMap((t) => {
    const [bid, lid] = t.split(":");
    const b = meta?.backends.find((x) => x.id === bid && x.enabled);
    const l = b?.links.find((x) => x.id === lid) ?? (lid ? undefined : b?.links[0]);
    return b && l ? [{ b, l }] : [];
  });
  if (!resolved.length) return null;
  return (
    <div className="tools">
      {resolved.map(({ b, l }) => (
        <a key={b.id + l.id} className="tool-link" href={l.url} target="_blank" rel="noreferrer">
          <BackendLogo backend={b as Backend} />
          <span className="stack" style={{ minWidth: 0 }}><span className="t">{l.label}</span>{l.description && <span className="d">{l.description}</span>}</span>
          <ArrowUpRight />
        </a>
      ))}
    </div>
  );
}

export function QuizWorkbench({ lesson, onChecks }: { lesson: Lesson; onChecks: (c: CheckResult[]) => void }) {
  const questions = lesson.quiz?.questions ?? [];
  const [answers, setAnswers] = useState<Record<string, string[]>>({});
  const [text, setText] = useState<Record<string, string>>({});
  const [results, setResults] = useState<Record<string, { correct: boolean; explanation: string; picked: string[] }>>({});

  useEffect(() => { setAnswers({}); setResults({}); setText({}); }, [lesson.id]);
  useEffect(() => {
    onChecks(questions.map((q, i) => ({
      id: q.id, title: `Question ${i + 1}`, type: "answer",
      status: results[q.id]?.correct ? "pass" : results[q.id] ? "fail" : "pending",
      detail: results[q.id] && !results[q.id].correct ? results[q.id].explanation : "",
    })));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [results]);

  const submit = async (qid: string, multiple?: boolean, isText?: boolean) => {
    const picked = isText ? [text[qid] ?? ""] : answers[qid] ?? [];
    const res = await api.answer(lesson.id, qid, multiple ? picked : picked[0] ?? "");
    setResults((r) => ({ ...r, [qid]: { ...res, picked } }));
  };

  return (
    <div className="workbench" style={{ overflow: "auto" }}>
      <div className="quiz">
        {lesson.tools.length > 0 && (
          <div>
            <div className="eyebrow" style={{ marginBottom: 8 }}>Investigate with</div>
            <ToolLinks tools={lesson.tools} />
          </div>
        )}
        {questions.map((q, i) => {
          const res = results[q.id];
          const picked = answers[q.id] ?? [];
          return (
            <div key={q.id} className="card question">
              <h4><span className="n">{i + 1}.</span><span><InlineCode text={q.prompt} /></span></h4>
              {q.input === "text" ? (
                <div className="row">
                  <input className="input grow" value={text[q.id] ?? ""} placeholder="Your answer" onChange={(e) => setText((t) => ({ ...t, [q.id]: e.target.value }))} onKeyDown={(e) => { if (e.key === "Enter") submit(q.id, false, true); }} />
                  <button className="btn" onClick={() => submit(q.id, false, true)} disabled={!text[q.id]}>Check</button>
                </div>
              ) : (
                <>
                  <div className="options" role={q.multiple ? "group" : "radiogroup"}>
                    {q.options?.map((o) => {
                      const sel = picked.includes(o.id);
                      const state = res && sel ? (res.correct ? "correct" : "wrong") : sel ? "selected" : "";
                      return (
                        <div key={o.id} role={q.multiple ? "checkbox" : "radio"} aria-checked={sel} tabIndex={0} className={`option ${state} ${sel ? "selected" : ""}`}
                          onClick={() => {
                            setResults((r) => { const n = { ...r }; delete n[q.id]; return n; });
                            setAnswers((a) => ({ ...a, [q.id]: q.multiple ? (sel ? picked.filter((x) => x !== o.id) : [...picked, o.id]) : [o.id] }));
                          }}
                          onKeyDown={(e) => { if (e.key === " " || e.key === "Enter") (e.currentTarget as HTMLElement).click(); }}>
                          <span className="radio" style={q.multiple ? { borderRadius: 4 } : undefined} />
                          <span><InlineCode text={o.label} /></span>
                        </div>
                      );
                    })}
                  </div>
                  <div className="row" style={{ marginTop: 10 }}>
                    <button className="btn" onClick={() => submit(q.id, q.multiple)} disabled={!picked.length}>Check answer</button>
                    {q.multiple && <span className="subtle" style={{ fontSize: 12 }}>Select all that apply</span>}
                  </div>
                </>
              )}
              {res && (
                <div className={`feedback ${res.correct ? "ok" : "err"}`}>
                  {res.correct ? <CheckCircle2 /> : <XCircle />}
                  <span><InlineCode text={res.explanation || (res.correct ? "Correct." : "Not quite.")} /></span>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function TaskWorkbench({ lesson, onChecks }: { lesson: Lesson; onChecks: (c: CheckResult[]) => void }) {
  const [busy, setBusy] = useState(false);
  const [checks, setChecks] = useState<CheckResult[] | null>(null);
  useEffect(() => setChecks(null), [lesson.id]);
  const verify = async () => {
    setBusy(true);
    try {
      const res = await api.verify(lesson.id);
      setChecks(res.checks);
      onChecks(res.checks);
    } finally { setBusy(false); }
  };
  return (
    <div className="workbench" style={{ overflow: "auto" }}>
      <div className="quiz">
        <div>
          <div className="eyebrow" style={{ marginBottom: 8 }}>Open the tools</div>
          <ToolLinks tools={lesson.tools} />
          {!lesson.tools.length && <Empty title="No tools linked" />}
        </div>
        <div className="card question">
          <h4><ClipboardCheck style={{ width: 16, height: 16, color: "var(--accent)" }} />When you're done, verify your work</h4>
          <p className="muted" style={{ margin: "0 0 12px", fontSize: 13 }}>Signal Lab checks the result through the backend's API. Nothing is uploaded from your browser.</p>
          <button className="btn btn-primary" onClick={verify} disabled={busy}>{busy ? <span className="spinner" /> : <ClipboardCheck />}Verify</button>
          {checks && checks.map((c) => (
            <div key={c.id} className={`feedback ${c.status === "pass" ? "ok" : "err"}`}>
              {c.status === "pass" ? <CheckCircle2 /> : <XCircle />}
              <span><b><InlineCode text={c.title} /></b><br /><InlineCode text={c.detail} /></span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
