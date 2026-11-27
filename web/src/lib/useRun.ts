import { useCallback, useEffect, useRef, useState } from "react";
import { api, type OutputLine, type RunSummary, type Telemetry } from "../api";

const EMPTY: Telemetry = { spans: [], metrics: [], logs: [] };

/** Start a run and follow it over server-sent events. */
export function useRun(lessonId: string) {
  const [run, setRun] = useState<RunSummary | null>(null);
  const [output, setOutput] = useState<OutputLine[]>([]);
  const [telemetry, setTelemetry] = useState<Telemetry>(EMPTY);
  const [error, setError] = useState<string | null>(null);
  const es = useRef<EventSource | null>(null);

  const close = () => { es.current?.close(); es.current = null; };
  useEffect(() => () => close(), []);
  useEffect(() => { close(); setRun(null); setOutput([]); setTelemetry(EMPTY); setError(null); }, [lessonId]);

  const start = useCallback(async (code: string) => {
    close();
    setError(null);
    setOutput([]);
    setTelemetry(EMPTY);
    let summary: RunSummary;
    try {
      summary = await api.run(lessonId, code);
    } catch (e) {
      setError((e as Error).message);
      return;
    }
    setRun(summary);
    const source = new EventSource(`/api/runs/${summary.id}/events`);
    es.current = source;
    source.addEventListener("snapshot", (e) => {
      const d = JSON.parse((e as MessageEvent).data);
      setOutput(d.output); setTelemetry(d.telemetry);
      const { output: _o, telemetry: _t, ...rest } = d;
      setRun(rest);
    });
    source.addEventListener("output", (e) => setOutput((o) => [...o, JSON.parse((e as MessageEvent).data)]));
    source.addEventListener("telemetry", (e) => setTelemetry(JSON.parse((e as MessageEvent).data)));
    source.addEventListener("status", (e) => setRun(JSON.parse((e as MessageEvent).data)));
    source.addEventListener("end", () => close());
    source.onerror = () => {
      // The server closes the stream once a run is settled; only report real failures.
      if (source.readyState === EventSource.CLOSED) close();
    };
  }, [lessonId]);

  const busy = !!run && (run.status === "queued" || run.status === "running" || run.status === "collecting");
  return { run, output, telemetry, error, start, busy };
}
