"""In-memory store for runs and the telemetry they produced.

Telemetry is attributed to a run in two ways:

* resources carrying ``signal_lab.run_id`` (set by the runner on learner code)
* spans/logs whose trace id belongs to a run, which lets spans emitted by the
  scenario services (called *from* learner code) join the learner's trace.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from typing import Any

RUN_ATTR = "signal_lab.run_id"
MAX_RUNS = 60
MAX_SPANS = 2000
MAX_LOGS = 2000
MAX_POINTS_PER_SERIES = 30
PENDING_TTL_S = 30


def _series_key(point: dict) -> str:
    attrs = sorted((k, str(v)) for k, v in point["attributes"].items())
    return f'{point["service"]}|{point["name"]}|{attrs}'


@dataclass
class Run:
    id: str
    lesson: str
    code: str
    created: float = field(default_factory=time.time)
    status: str = "queued"  # queued | running | collecting | done | error
    exit_code: int | None = None
    duration_ms: float | None = None
    output: list[dict] = field(default_factory=list)
    spans: list[dict] = field(default_factory=list)
    series: "OrderedDict[str, dict]" = field(default_factory=OrderedDict)
    logs: list[dict] = field(default_factory=list)
    checks: list[dict] = field(default_factory=list)
    backends: dict[str, dict] = field(default_factory=dict)
    trace_ids: set[str] = field(default_factory=set)
    version: int = 0
    _listeners: list[asyncio.Queue] = field(default_factory=list)

    # -- event fan-out -------------------------------------------------
    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._listeners.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        if q in self._listeners:
            self._listeners.remove(q)

    def emit(self, kind: str, data: Any = None) -> None:
        self.version += 1
        for q in list(self._listeners):
            q.put_nowait((kind, data))

    # -- telemetry -----------------------------------------------------
    def add_spans(self, spans: list[dict]) -> None:
        seen = {(s["trace_id"], s["span_id"]) for s in self.spans}
        for s in spans:
            if (s["trace_id"], s["span_id"]) in seen:
                continue
            self.spans.append(s)
            self.trace_ids.add(s["trace_id"])
        del self.spans[:-MAX_SPANS]
        self.emit("telemetry")

    def add_points(self, points: list[dict]) -> None:
        for p in points:
            key = _series_key(p)
            entry = self.series.get(key)
            if entry is None:
                entry = {k: v for k, v in p.items() if k not in ("time_ms",)}
                entry["key"] = key
                entry["history"] = []
                self.series[key] = entry
            else:
                entry.update({k: v for k, v in p.items() if k != "time_ms"})
            entry["time_ms"] = p["time_ms"]
            entry["history"].append(_point_value(p) | {"time_ms": p["time_ms"]})
            del entry["history"][:-MAX_POINTS_PER_SERIES]
        self.emit("telemetry")

    def add_logs(self, logs: list[dict]) -> None:
        self.logs.extend(logs)
        del self.logs[:-MAX_LOGS]
        self.emit("telemetry")

    def metrics(self) -> list[dict]:
        """Group series by metric name for display and checks."""
        grouped: "OrderedDict[str, dict]" = OrderedDict()
        for s in self.series.values():
            g = grouped.setdefault(
                s["name"],
                {
                    "name": s["name"],
                    "description": s.get("description", ""),
                    "unit": s.get("unit", ""),
                    "type": s["type"],
                    "instrument": s["instrument"],
                    "temporality": s.get("temporality"),
                    "service": s["service"],
                    "series": [],
                },
            )
            g["series"].append({k: v for k, v in s.items() if k not in ("name", "description", "unit", "resource", "scope")})
        return list(grouped.values())

    def telemetry(self) -> dict:
        return {"spans": self.spans, "metrics": self.metrics(), "logs": self.logs}

    def summary(self) -> dict:
        return {
            "id": self.id,
            "lesson": self.lesson,
            "created": self.created,
            "status": self.status,
            "exit_code": self.exit_code,
            "duration_ms": self.duration_ms,
            "counts": {
                "spans": len(self.spans),
                "traces": len(self.trace_ids),
                "metrics": len({s["name"] for s in self.series.values()}),
                "series": len(self.series),
                "logs": len(self.logs),
            },
            "checks": self.checks,
            "backends": self.backends,
        }

    def snapshot(self) -> dict:
        return self.summary() | {"output": self.output, "telemetry": self.telemetry()}


def _point_value(p: dict) -> dict:
    if p["type"] in ("sum", "gauge"):
        return {"value": p["value"]}
    if p["type"] in ("histogram", "exponential_histogram", "summary"):
        return {"count": p.get("count"), "sum": p.get("sum")}
    return {}


class Store:
    def __init__(self) -> None:
        self.runs: "OrderedDict[str, Run]" = OrderedDict()
        self.trace_index: dict[str, str] = {}
        self.pending_spans: deque[tuple[float, dict]] = deque(maxlen=5000)
        self.pending_logs: deque[tuple[float, dict]] = deque(maxlen=5000)
        self.stats = {"spans": 0, "points": 0, "logs": 0, "dropped": 0}

    def create(self, lesson: str, code: str) -> Run:
        run = Run(id=uuid.uuid4().hex[:12], lesson=lesson, code=code)
        self.runs[run.id] = run
        while len(self.runs) > MAX_RUNS:
            _, old = self.runs.popitem(last=False)
            for t in old.trace_ids:
                self.trace_index.pop(t, None)
        return run

    def get(self, run_id: str) -> Run | None:
        return self.runs.get(run_id)

    # -- ingest ----------------------------------------------------------
    def ingest_spans(self, spans: list[dict]) -> None:
        self.stats["spans"] += len(spans)
        by_run: dict[str, list[dict]] = {}
        now = time.time()
        for s in spans:
            run_id = s["resource"].get(RUN_ATTR) or self.trace_index.get(s["trace_id"])
            if run_id and run_id in self.runs:
                self.trace_index[s["trace_id"]] = run_id
                by_run.setdefault(run_id, []).append(s)
            else:
                self.pending_spans.append((now, s))
        for run_id, items in by_run.items():
            self.runs[run_id].add_spans(items)
        self._adopt_pending()

    def ingest_points(self, points: list[dict]) -> None:
        self.stats["points"] += len(points)
        by_run: dict[str, list[dict]] = {}
        for p in points:
            run_id = p["resource"].get(RUN_ATTR)
            if run_id in self.runs:
                by_run.setdefault(run_id, []).append(p)
            else:
                self.stats["dropped"] += 1
        for run_id, items in by_run.items():
            self.runs[run_id].add_points(items)

    def ingest_logs(self, logs: list[dict]) -> None:
        self.stats["logs"] += len(logs)
        by_run: dict[str, list[dict]] = {}
        now = time.time()
        for r in logs:
            run_id = r["resource"].get(RUN_ATTR) or (r["trace_id"] and self.trace_index.get(r["trace_id"]))
            if run_id and run_id in self.runs:
                by_run.setdefault(run_id, []).append(r)
            elif r["trace_id"]:
                self.pending_logs.append((now, r))
        for run_id, items in by_run.items():
            self.runs[run_id].add_logs(items)
        self._adopt_pending()

    def _adopt_pending(self) -> None:
        """Attach buffered spans/logs whose trace became known after they arrived."""
        cutoff = time.time() - PENDING_TTL_S
        for buf, attr in ((self.pending_spans, "spans"), (self.pending_logs, "logs")):
            keep: list[tuple[float, dict]] = []
            adopted: dict[str, list[dict]] = {}
            for ts, item in buf:
                if ts < cutoff:
                    continue
                run_id = self.trace_index.get(item["trace_id"])
                if run_id and run_id in self.runs:
                    adopted.setdefault(run_id, []).append(item)
                else:
                    keep.append((ts, item))
            if adopted:
                buf.clear()
                buf.extend(keep)
                for run_id, items in adopted.items():
                    run = self.runs[run_id]
                    run.add_spans(items) if attr == "spans" else run.add_logs(items)
