"""Chaos experiments and incidents: timed fault timelines on the shared scenario.

Both run on the one Signal Shop, so only one can be active at a time; everyone
else can watch it. On a team deployment that makes an incident a *game day*:
an admin starts it and everybody investigates the same live system.

Experiment (``kind: experiment``)::

    experiment:
      hypothesis: Checkout p95 stays under 1 s when inventory adds 300 ms.
      steady_state: {backend: victoriametrics, query: "...", label: "checkout p95 (s)", threshold: 1.0, abort_above: 3}
      baseline_s: 30
      inject: {inventory: {latency_ms: 300}}
      duration_s: 60
      recovery_s: 30

Incident (``kind: incident``)::

    incident:
      duration_s: 900
      timeline:
        - {at: 0, load: 4}
        - {at: 90, fault: true, set: {payments: {error_rate: 0.3}, checkout: {retries: 3}}}
"""

from __future__ import annotations

import asyncio
import logging
import math
import random
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

log = logging.getLogger("signal_lab.drills")

ApplyFn = Callable[[dict[str, dict]], Awaitable[None]]
LoadFn = Callable[[float], Awaitable[None]]
ResetFn = Callable[[], Awaitable[None]]
QueryFn = Callable[[str, str, str], Awaitable[float | None]]


@dataclass
class Activity:
    kind: str  # experiment | incident
    lesson: str
    title: str
    by: str
    started: float
    ends: float
    phases: list[dict] = field(default_factory=list)
    phase: str = "starting"
    status: str = "running"  # running | done | aborted | stopped
    samples: list[list[float]] = field(default_factory=list)  # [t_ms, value]
    fault_started: float | None = None
    fault_ended: float | None = None
    reason: str = ""
    steady: dict | None = None
    hypothesis_held: bool | None = None

    def public(self, reveal: bool = False) -> dict:
        out = {
            "kind": self.kind, "lesson": self.lesson, "title": self.title, "by": self.by,
            "started": self.started, "ends": self.ends, "now": time.time(), "phase": self.phase,
            "phases": self.phases, "status": self.status, "reason": self.reason, "samples": self.samples,
            "steady": self.steady, "hypothesis_held": self.hypothesis_held,
        }
        # An incident's true start is the answer to a question, so it is never sent to
        # learners; the answer's explanation reveals it once they get it right.
        if self.kind == "experiment" or reveal:
            out["fault_started"] = self.fault_started
            out["fault_ended"] = self.fault_ended
        return out


class Drills:
    def __init__(self, apply: ApplyFn, load: LoadFn, reset: ResetFn, query: QueryFn):
        self.apply, self.load, self.reset, self.query = apply, load, reset, query
        self.current: Activity | None = None
        self.last: dict[str, Activity] = {}
        self._task: asyncio.Task | None = None
        # Game-day board: lesson -> person -> question -> seconds since the activity started
        self.solved: dict[str, dict[str, dict[str, float]]] = {}

    def record(self, lesson: str, person: str, question: str) -> None:
        act = self.last.get(lesson)
        if not act:
            return
        board = self.solved.setdefault(lesson, {}).setdefault(person, {})
        board.setdefault(question, round(time.time() - act.started))

    def board(self, lesson: str) -> dict:
        return self.solved.get(lesson, {})

    def busy(self) -> bool:
        return self.current is not None and self.current.status == "running"

    def state(self) -> dict | None:
        return self.current.public() if self.current else None

    async def stop(self, reason: str = "Stopped") -> None:
        if self._task and not self._task.done():
            self._task.cancel()
        if self.current and self.current.status == "running":
            self.current.status = "stopped"
            self.current.reason = reason
            self.current.phase = "stopped"
            await self.reset()

    def start(self, kind: str, lesson: str, title: str, by: str, spec: dict) -> Activity:
        if self.busy():
            raise RuntimeError(f"A {self.current.kind} started by {self.current.by} is still running.")
        now = time.time()
        if kind == "experiment":
            total = spec.get("baseline_s", 30) + spec.get("duration_s", 60) + spec.get("recovery_s", 30)
            phases = [
                {"name": "baseline", "start": now, "end": now + spec.get("baseline_s", 30)},
                {"name": "inject", "start": now + spec.get("baseline_s", 30), "end": now + spec.get("baseline_s", 30) + spec.get("duration_s", 60)},
                {"name": "recovery", "start": now + spec.get("baseline_s", 30) + spec.get("duration_s", 60), "end": now + total},
            ]
        else:
            total = spec.get("duration_s", 600)
            phases = []
        act = Activity(kind=kind, lesson=lesson, title=title, by=by, started=now, ends=now + total, phases=phases, steady=spec.get("steady_state"))
        self.solved.pop(lesson, None)  # a new run starts a fresh board
        self.current = act
        self.last[lesson] = act
        runner = self._experiment(act, spec) if kind == "experiment" else self._incident(act, spec)
        self._task = asyncio.create_task(self._guard(act, runner))
        return act

    async def _guard(self, act: Activity, coro: Awaitable[None]) -> None:
        try:
            await coro
        except asyncio.CancelledError:
            pass
        except Exception as e:  # never leave a fault behind
            log.exception("%s failed", act.kind)
            act.status, act.reason = "stopped", f"Internal error: {e}"
            await self.reset()

    async def _sample(self, act: Activity) -> float | None:
        steady = act.steady or {}
        if not steady.get("query"):
            return None
        value = await self.query(steady.get("backend", "victoriametrics"), steady.get("language", "metricsql"), steady["query"])
        if value is not None and not math.isnan(value):
            act.samples.append([time.time() * 1000, value])
            del act.samples[:-400]
        return value

    async def _experiment(self, act: Activity, spec: dict) -> None:
        await self.reset()
        steady = spec.get("steady_state") or {}
        threshold, abort_at = steady.get("threshold"), steady.get("abort_at", steady.get("abort_above"))
        below = steady.get("direction") == "below"  # e.g. a success ratio: lower is worse

        def breaks(v: float, limit: float) -> bool:
            return v < limit if below else v > limit

        held = True
        while time.time() < act.ends:
            now = time.time()
            phase = next((p["name"] for p in act.phases if p["start"] <= now < p["end"]), "recovery")
            if phase != act.phase:
                act.phase = phase
                if phase == "inject":
                    act.fault_started = now
                    await self.apply(spec.get("inject") or {})
                    if "load" in spec:
                        await self.load(float(spec["load"]))
                elif phase == "recovery" and act.fault_ended is None:
                    act.fault_ended = now
                    await self.reset()
            value = await self._sample(act)
            if phase == "inject" and value is not None:
                if threshold is not None and breaks(value, threshold):
                    held = False
                if abort_at is not None and breaks(value, abort_at):
                    act.status, act.phase = "aborted", "aborted"
                    act.reason = f"Abort condition hit: {steady.get('label', 'steady state')} reached {value:.3g} (limit {abort_at}). Faults removed."
                    act.fault_ended = time.time()
                    act.hypothesis_held = False
                    await self.reset()
                    return
            await asyncio.sleep(steady.get("interval_s", 3))
        act.hypothesis_held = held
        act.status, act.phase = "done", "done"
        await self.reset()

    async def _incident(self, act: Activity, spec: dict) -> None:
        await self.reset()
        # `at` may be a range ({min, max}), drawn once per run, so the fault start has
        # to be read from the data rather than from when Start was pressed.
        def at(s: dict) -> float:
            a = s.get("at", 0)
            return random.uniform(float(a.get("min", 0)), float(a.get("max", a.get("min", 0)))) if isinstance(a, dict) else float(a)

        steps = sorted(({**s, "at": at(s)} for s in spec.get("timeline", [])), key=lambda s: s["at"])
        i = 0
        act.phase = "investigating"
        while time.time() < act.ends:
            elapsed = time.time() - act.started
            while i < len(steps) and steps[i]["at"] <= elapsed:
                step = steps[i]
                if step.get("reset"):
                    await self.reset()
                if "load" in step:
                    await self.load(float(step["load"]))
                if step.get("set"):
                    await self.apply(step["set"])
                if step.get("fault") and act.fault_started is None:
                    act.fault_started = time.time()
                if step.get("resolved") and act.fault_ended is None:
                    act.fault_ended = time.time()
                i += 1
            await self._sample(act)
            await asyncio.sleep(3)
        act.status, act.phase = "done", "done"
        await self.reset()


def scalar(result: Any) -> float | None:
    """First numeric value of a QueryResult (instant vector / scalar)."""
    if result is None or result.error or not result.rows:
        return None
    try:
        idx = result.columns.index("value") if "value" in result.columns else len(result.columns) - 1
        return float(result.rows[0][idx])
    except (TypeError, ValueError, IndexError):
        return None
