import { useCallback, useEffect, useRef, useState } from "react";
import { api, type OutputLine, type RunSummary, type Telemetry } from "../api";

const EMPTY: Telemetry = { spans: [], metrics: [], logs: [] };

/**
 * Start a run and follow it over server-sent events.
 *
 * Exactly one run is "current". Every event stream, poll and request is tagged
 * with the generation that started it, and anything from an older generation is
 * dropped. Without this, two runs started close together (a quick second Ctrl+Enter
 * while the first request was still in flight) both streamed into the same goals:
 * they flickered between pass and fail and could settle on the wrong run's result.
 */
export function useRun(lessonId: string) {
  const [run, setRun] = useState<RunSummary | null>(null);
  const [output, setOutput] = useState<OutputLine[]>([]);
  const [telemetry, setTelemetry] = useState<Telemetry>(EMPTY);
  const [error, setError] = useState<string | null>(null);
  // True from the moment Run is pressed until the server has created the run, so a
  // second press in that window queues instead of starting a parallel run.
  const [starting, setStarting] = useState(false);
  const gen = useRef(0);
  const es = useRef<EventSource | null>(null);
  const poll = useRef<number | null>(null);

  /** Make every earlier run stale: close its stream and stop its polling. */
  const retire = () => {
    gen.current += 1;
    es.current?.close();
    es.current = null;
    if (poll.current) window.clearTimeout(poll.current);
    poll.current = null;
  };

  useEffect(() => () => retire(), []);
  useEffect(() => { retire(); setRun(null); setOutput([]); setTelemetry(EMPTY); setError(null); setStarting(false); }, [lessonId]);

  const start = useCallback(async (code: string) => {
    retire();
    const mine = gen.current;
    const current = () => gen.current === mine;
    setStarting(true);
    setError(null);
    setOutput([]);
    // Keep the previous run's telemetry on screen until this run's first data
    // (or its end) arrives, so the inspector doesn't blank out on every run.
    let fresh = false;
    const showTelemetry = (t: Telemetry) => { fresh = true; setTelemetry(t); };
    const hasData = (t: Telemetry) => t.spans.length + t.metrics.length + t.logs.length > 0;

    let summary: RunSummary;
    try {
      summary = await api.run(lessonId, code);
    } catch (e) {
      if (current()) { setError((e as Error).message); setStarting(false); }
      return;
    }
    if (!current()) return;  // superseded while the request was in flight
    setStarting(false);
    setRun(summary);

    // "Arrived in Jaeger / VictoriaMetrics…": backends can take a while to index, so
    // after grading ask every 2 s (up to 45 s) instead of holding a connection open
    // (browsers allow 6 per host, across all tabs).
    const followConfirmations = () => {
      const began = Date.now();
      const tick = async () => {
        try {
          const r = await fetch(`/api/runs/${summary.id}`);
          if (!r.ok || !current()) return;
          const { output: _o, telemetry: t, ...rest } = await r.json();
          if (!current()) return;
          setRun(rest);
          if (t) setTelemetry(t);
          const pending = Object.values((rest as RunSummary).backends ?? {}).some((b) => Object.values(b.signals).some((s) => s.state === "pending"));
          if (pending && Date.now() - began < 45_000) poll.current = window.setTimeout(tick, 2000);
        } catch { /* offline: stop quietly */ }
      };
      poll.current = window.setTimeout(tick, 1000);
    };

    const source = new EventSource(`/api/runs/${summary.id}/events`);
    es.current = source;
    const done = () => { source.close(); if (es.current === source) es.current = null; };
    const on = (name: string, fn: (data: any) => void) =>
      source.addEventListener(name, (e) => { if (current()) fn(JSON.parse((e as MessageEvent).data)); else source.close(); });

    on("snapshot", (d) => {
      setOutput(d.output);
      if (hasData(d.telemetry) || d.status === "done" || d.status === "error") showTelemetry(d.telemetry);
      const { output: _o, telemetry: _t, ...rest } = d;
      setRun(rest);
    });
    on("output", (line) => setOutput((o) => [...o, line]));
    on("telemetry", (t) => showTelemetry(t));
    on("status", (s: RunSummary) => {
      if (!fresh && s.status !== "queued" && s.status !== "running") showTelemetry(EMPTY);
      setRun(s);
      if (s.status === "done" || s.status === "error") { done(); followConfirmations(); }
    });
    source.addEventListener("end", done);
    source.onerror = () => {
      // The server closes the stream once a run is settled; only real failures land here.
      if (source.readyState === EventSource.CLOSED) done();
    };
  }, [lessonId]);

  // `running`: the program is executing (or the run is being created); a new run
  // must wait. `busy` also covers collecting late telemetry, which a new run may replace.
  const running = starting || (!!run && (run.status === "queued" || run.status === "running"));
  const busy = running || run?.status === "collecting";
  return { run, output, telemetry, error, start, busy, running };
}
