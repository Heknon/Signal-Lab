"""The Signal Lab API: lessons, runs, the telemetry tap, queries and the scenario."""

from __future__ import annotations

import asyncio
import json
import logging
import math
import time
from pathlib import Path
from typing import Any

import httpx
import yaml
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import __version__, auth, checks, otlp, runner
from .config import Settings
from .db import create_db
from .drills import Drills, scalar
from .plugins import Registry
from .store import RUN_ATTR, Run, Store

log = logging.getLogger("signal_lab")


class RunRequest(BaseModel):
    lesson: str
    code: str


class QueryRequest(BaseModel):
    backend: str
    language: str
    query: str
    lesson: str | None = None
    range_s: int = 900


class AnswerRequest(BaseModel):
    question: str
    answer: str | list[str]


class ChaosRequest(BaseModel):
    """Fault settings, passed through to the scenario service (see the shop's Chaos model)."""

    model_config = {"extra": "allow"}
    latency_ms: int | None = None
    error_rate: float | None = None


class LoadRequest(BaseModel):
    rps: float


def deep_merge(a: dict, b: dict) -> dict:
    out = dict(a)
    for k, v in b.items():
        out[k] = deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    registry = Registry.load(settings.plugins_dir, settings.backends, settings.lesson_packs, settings.scenarios)
    store = Store()
    http = httpx.AsyncClient(timeout=3.0)
    health_cache: dict[str, Any] = {"t": 0.0, "value": None}

    app = FastAPI(title="Signal Lab", version=__version__)
    db = create_db(settings.database_url)
    app.state.settings, app.state.registry, app.state.store, app.state.db = settings, registry, store, db
    auth.install(app, settings, db)
    # Who changed the shared scenario, and when lesson-applied faults expire.
    scenario_changes: dict[str, dict] = {}

    for err in registry.errors:
        log.error("plugin error: %s", err)

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        await http.aclose()
        for b in registry.enabled_backends:
            if b.adapter:
                await b.adapter.close()

    # ------------------------------------------------------------ helpers
    mtime = {"v": registry.lessons_mtime() if settings.reload else 0.0}

    def maybe_reload() -> None:
        if not settings.reload:
            return
        current = registry.lessons_mtime()
        if current != mtime["v"]:
            mtime["v"] = current
            registry.reload_packs(settings.lesson_packs)
            log.info("lesson packs reloaded")

    def lesson_or_404(lesson_id: str):
        maybe_reload()
        lesson = registry.lesson(lesson_id)
        if not lesson:
            raise HTTPException(404, f"No lesson {lesson_id}")
        return lesson

    def run_env(lesson, run_id: str) -> dict[str, str]:
        rt = lesson.meta.get("runtime") or {}
        service = rt.get("service", "lab-app")
        resource = {RUN_ATTR: run_id, "signal_lab.lesson": lesson.id, "deployment.environment.name": settings.environment, "service.version": "1.0.0"}
        env = {
            "OTEL_SERVICE_NAME": service,
            "OTEL_RESOURCE_ATTRIBUTES": ",".join(f"{k}={v}" for k, v in resource.items()),
            "OTEL_EXPORTER_OTLP_ENDPOINT": settings.effective_otlp_endpoint,
            "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
            "OTEL_TRACES_EXPORTER": "otlp",
            "OTEL_METRICS_EXPORTER": "otlp",
            "OTEL_LOGS_EXPORTER": "otlp",
            "OTEL_METRIC_EXPORT_INTERVAL": "1000",
            "OTEL_BSP_SCHEDULE_DELAY": "200",
            "OTEL_BLRP_SCHEDULE_DELAY": "200",
            "OTEL_SEMCONV_STABILITY_OPT_IN": "http",
            "OTEL_PYTHON_DISABLED_INSTRUMENTATIONS": "",
        }
        scenario = registry.scenario()
        if scenario:
            env |= scenario.runner_env()
        env |= {k: str(v) for k, v in (rt.get("env") or {}).items()}
        return env

    def visible_env(lesson) -> dict[str, str]:
        env = run_env(lesson, "<run-id>")
        return {k: v for k, v in env.items() if v != ""}

    async def finish_with_checks(run: Run, lesson) -> None:
        lesson_checks = [c for c in lesson.checks() if c["type"] not in checks.DEFERRED]
        exit_seen = time.monotonic()
        min_settle, max_settle = 1.2, float(lesson.meta.get("settle_s", 6))
        needs_telemetry = any(c["type"] in ("span", "trace", "metric", "log") for c in lesson_checks)
        while True:
            ctx = {"collecting": True, "output": run.output, "exit_code": run.exit_code}
            run.checks = checks.evaluate(lesson_checks, run.telemetry(), ctx)
            run.emit("status")
            elapsed = time.monotonic() - exit_seen
            all_pass = all(c["status"] == checks.PASS for c in run.checks)
            if elapsed >= max_settle or (elapsed >= min_settle and (all_pass or not needs_telemetry)):
                break
            await asyncio.sleep(0.3)
        ctx = {"collecting": False, "output": run.output, "exit_code": run.exit_code}
        run.checks = checks.evaluate(lesson_checks, run.telemetry(), ctx)
        run.status = "done" if run.exit_code == 0 else "error"
        run.emit("status")
        try:
            await db.save_run(run.user_id, run.summary() | {"code": run.code})
        except Exception:
            log.exception("could not save run %s", run.id)
        asyncio.create_task(confirm_backends(run))

    async def confirm_backends(run: Run) -> None:
        """Ask each backend whether this run's telemetry landed there."""
        targets = []
        trace_id = run.spans[0]["trace_id"] if run.spans else None
        metric = next(iter(run.series.values()), None)
        for b in registry.enabled_backends:
            caps = set(b.manifest.get("capabilities", []))
            entry: dict[str, Any] = {"title": b.title, "signals": {}}
            if trace_id and "traces" in caps:
                entry["signals"]["traces"] = {"state": "pending", "trace_id": trace_id, "url": b.adapter.link("trace", {"trace_id": trace_id})}
            if metric and "metrics" in caps:
                entry["signals"]["metrics"] = {"state": "pending", "metric": metric["name"], "url": b.adapter.link("metric", {"name": metric["name"]})}
            if run.logs and "logs" in caps:
                entry["signals"]["logs"] = {"state": "pending", "url": b.adapter.link("logs", {"run_id": run.id})}
            if entry["signals"]:
                run.backends[b.id] = entry
                targets.append(b)
        if not targets:
            return
        run.emit("status")
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            pending = False
            for b in targets:
                for signal, st in run.backends[b.id]["signals"].items():
                    if st["state"] != "pending":
                        continue
                    try:
                        if signal == "traces":
                            found = await b.adapter.find_trace(st["trace_id"])
                        elif signal == "metrics":
                            found = await b.adapter.find_metric(st["metric"], metric["service"])
                        else:
                            found = await b.adapter.find_logs(run.id)
                    except Exception as e:
                        log.debug("confirm %s/%s failed: %s", b.id, signal, e)
                        found = False
                    if found is None:
                        st["state"] = "unsupported"
                    elif found:
                        st["state"] = "found"
                        st["after_ms"] = round((time.time() - run.created) * 1000)
                    else:
                        pending = True
            run.emit("status")
            if not pending:
                return
            await asyncio.sleep(2)
        for b in targets:
            for st in run.backends[b.id]["signals"].values():
                if st["state"] == "pending":
                    st["state"] = "missing"
        run.emit("status")

    async def drive(run: Run, lesson) -> None:
        rt = lesson.meta.get("runtime") or {}
        timeout = min(float(rt.get("timeout", settings.run_timeout)), settings.run_timeout * 2)
        auto = bool(rt.get("auto_instrument", True))
        env = run_env(lesson, run.id)
        run.status = "running"
        run.emit("status")
        code, extra = run.code, {}
        if lesson.kind == "collector":
            # The learner wrote a Collector config; the lesson's traffic script runs through it.
            traffic = lesson.files.get("traffic")
            code = traffic["content"] if traffic else "print('this lesson has no traffic.py')"
            extra = {"collector_config": run.code, "tap_url": settings.effective_tap_url, "settle_s": float((lesson.meta.get("collector") or {}).get("settle_s", 3))}
        events = (
            runner.execute_remote(settings.runner_url, code, env, timeout=timeout, auto_instrument=auto, **extra)
            if settings.runner_url
            else runner.execute_local(code, env, timeout=timeout, auto_instrument=auto, **extra)
        )
        try:
            async for ev in events:
                if ev["type"] == "output":
                    line = {"stream": ev["stream"], "text": ev["text"], "t": ev.get("t")}
                    run.output.append(line)
                    run.emit("output", line)
                elif ev["type"] == "start":
                    line = {"stream": "system", "text": f"$ {ev['command']}", "t": 0}
                    run.output.append(line)
                    run.emit("output", line)
                elif ev["type"] == "exit":
                    run.exit_code = ev["code"]
                    run.duration_ms = ev["duration_ms"]
        except Exception as e:  # runner crashed
            log.exception("run %s failed", run.id)
            line = {"stream": "system", "text": f"Runner error: {e}"}
            run.output.append(line)
            run.emit("output", line)
            run.exit_code = -1
        run.status = "collecting"
        run.emit("status")
        await finish_with_checks(run, lesson)

    # ------------------------------------------------------------ meta
    @app.get("/api/meta")
    async def meta() -> dict:
        scenario = registry.scenario()
        return {
            "version": __version__,
            "backends": [b.public() for b in registry.backends.values()],
            "scenario": scenario.public() if scenario else None,
            "runs_enabled": settings.runs_enabled,
            "runner": "remote" if settings.runner_url else "local",
            "otlp_endpoint": settings.effective_otlp_endpoint,
            "collector": bool(settings.collector_health_url or settings.collector_configs),
            "plugin_errors": registry.errors,
            "capabilities": sorted(registry.capabilities()),
        }

    @app.get("/api/health")
    async def health() -> dict:
        if health_cache["value"] and time.monotonic() - health_cache["t"] < 3:
            return health_cache["value"]

        async def collector() -> dict:
            if not settings.collector_health_url:
                return {"ok": True, "detail": "direct (no collector)", "mode": "direct"}
            try:
                r = await http.get(settings.collector_health_url, timeout=2)
                return {"ok": r.status_code == 200, "detail": f"HTTP {r.status_code}", "mode": "collector"}
            except httpx.HTTPError as e:
                return {"ok": False, "detail": type(e).__name__, "mode": "collector"}

        async def backend(b) -> tuple[str, dict]:
            try:
                return b.id, await asyncio.wait_for(b.adapter.health(), timeout=4)
            except Exception as e:
                return b.id, {"_": {"ok": False, "detail": type(e).__name__}}

        async def runner_health() -> dict:
            if not settings.runner_url:
                return {"ok": True, "detail": "in-process", "mode": "local"}
            try:
                r = await http.get(settings.runner_url.rstrip("/") + "/healthz", timeout=2)
                return {"ok": r.status_code == 200, "detail": f"HTTP {r.status_code}", "mode": "remote"}
            except httpx.HTTPError as e:
                return {"ok": False, "detail": type(e).__name__, "mode": "remote"}

        results = await asyncio.gather(collector(), runner_health(), *(backend(b) for b in registry.enabled_backends))
        value = {"collector": results[0], "runner": results[1], "backends": dict(results[2:]), "tap": store.stats}
        health_cache.update(t=time.monotonic(), value=value)
        return value

    @app.get("/api/course")
    async def course() -> list[dict]:
        maybe_reload()
        return registry.course()

    @app.get("/api/lessons/{pack}/{slug}")
    async def lesson(pack: str, slug: str) -> dict:
        lesson = lesson_or_404(f"{pack}/{slug}")
        return lesson.public() | {"env": visible_env(lesson) if lesson.kind in ("code", "collector") else {}}

    @app.get("/api/collector")
    async def collector_config() -> dict:
        files, merged = [], {}
        for path in settings.collector_configs:
            p = Path(path)
            if p.exists():
                text = p.read_text()
                files.append({"name": p.name, "path": str(p), "content": text})
                try:
                    merged = deep_merge(merged, yaml.safe_load(text) or {})
                except yaml.YAMLError:
                    pass
        pipelines = (merged.get("service") or {}).get("pipelines") or {}
        return {"files": files, "pipelines": pipelines, "components": {k: list((merged.get(k) or {}).keys()) for k in ("receivers", "processors", "exporters", "connectors", "extensions")}}

    @app.get("/api/plugins")
    async def plugins() -> dict:
        return {
            "backends": [b.public() | {"path": str(b.path.relative_to(settings.plugins_dir))} for b in registry.backends.values()],
            "lesson_packs": [
                {"id": p.id, "title": p.manifest.get("title", p.id), "description": p.manifest.get("description", ""), "lessons": len(p.lessons), "requires": p.manifest.get("requires", {}), "path": str(p.path.relative_to(settings.plugins_dir))}
                for p in registry.packs.values()
            ],
            "scenarios": [s.public() | {"path": str(s.path.relative_to(settings.plugins_dir))} for s in registry.scenarios.values()],
            "check_types": sorted(set(checks.CHECKS) | checks.DEFERRED),
            "errors": registry.errors,
        }

    # ------------------------------------------------------------ runs
    def own_run(run_id: str, request: Request) -> Run:
        run = store.get(run_id)
        user = getattr(request.state, "user", None)
        if not run or (user and run.user_id not in (None, user.id) and user.role != "admin"):
            raise HTTPException(404, "Unknown run")
        return run

    @app.post("/api/runs")
    async def create_run(req: RunRequest, request: Request) -> dict:
        if not settings.runs_enabled:
            raise HTTPException(403, "Code execution is disabled on this deployment.")
        lesson = lesson_or_404(req.lesson)
        if len(req.code) > 100_000:
            raise HTTPException(413, "Code is too large.")
        user = request.state.user
        if settings.auth == "accounts" and store.active_for(user.id):
            raise HTTPException(429, "Your previous run is still going. Wait for it to finish.")
        run = store.create(lesson.id, req.code, user.id)
        asyncio.create_task(drive(run, lesson))
        return run.summary()

    @app.get("/api/runs/{run_id}")
    async def get_run(run_id: str, request: Request) -> dict:
        return own_run(run_id, request).snapshot()

    @app.get("/api/runs/{run_id}/events")
    async def run_events(run_id: str, request: Request):
        run = own_run(run_id, request)

        async def stream():
            q = run.subscribe()
            try:
                yield f"event: snapshot\ndata: {json.dumps(run.snapshot())}\n\n"
                last_tel, dirty_tel, dirty_status = 0.0, False, False
                while True:
                    try:
                        kind, data = await asyncio.wait_for(q.get(), timeout=0.25)
                        if kind == "output":
                            yield f"event: output\ndata: {json.dumps(data)}\n\n"
                        elif kind == "telemetry":
                            dirty_tel = True
                        elif kind == "status":
                            dirty_status = True
                    except asyncio.TimeoutError:
                        pass
                    now = time.monotonic()
                    if dirty_tel and now - last_tel > 0.25:
                        yield f"event: telemetry\ndata: {json.dumps(run.telemetry())}\n\n"
                        dirty_tel, last_tel = False, now
                    if dirty_status:
                        yield f"event: status\ndata: {json.dumps(run.summary())}\n\n"
                        dirty_status = False
                    if await request.is_disconnected():
                        break
                    finished = run.status in ("done", "error") and all(
                        st["state"] != "pending" for b in run.backends.values() for st in b["signals"].values()
                    )
                    if finished and not dirty_tel and q.empty() and time.time() - run.created > 2:
                        # keep the stream open a little for late telemetry
                        await asyncio.sleep(1)
                        yield f"event: telemetry\ndata: {json.dumps(run.telemetry())}\n\n"
                        yield f"event: status\ndata: {json.dumps(run.summary())}\n\n"
                        yield "event: end\ndata: {}\n\n"
                        break
            finally:
                run.unsubscribe(q)

        return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    # ------------------------------------------------------------ tap (OTLP/HTTP receiver)
    @app.post("/tap/v1/{signal}")
    async def tap(signal: str, request: Request) -> Response:
        if signal not in otlp.DECODERS:
            raise HTTPException(404)
        body = otlp.decompress(await request.body(), request.headers.get("content-encoding"))
        ctype = request.headers.get("content-type", "")
        if "json" in ctype:
            return JSONResponse({"error": "The lab tap accepts OTLP protobuf; set encoding: proto on the exporter."}, status_code=415)
        try:
            items = otlp.DECODERS[signal](body)
        except Exception as e:
            log.warning("tap: could not decode %s payload: %s", signal, e)
            return Response(status_code=400)
        {"traces": store.ingest_spans, "metrics": store.ingest_points, "logs": store.ingest_logs}[signal](items)
        return Response(content=otlp.EMPTY_RESPONSES[signal], media_type="application/x-protobuf")

    # ------------------------------------------------------------ queries
    def backend_or_404(backend_id: str):
        b = registry.backends.get(backend_id)
        if not b or not b.enabled or not b.adapter:
            raise HTTPException(404, f"Backend {backend_id} is not enabled")
        return b

    @app.post("/api/query")
    async def query(req: QueryRequest) -> dict:
        b = backend_or_404(req.backend)
        at_ms = int(time.time() * 1000)
        res = await b.adapter.query(req.language, req.query, at_ms=at_ms, range_s=req.range_s)
        if res is None:
            raise HTTPException(400, f"{b.title} does not support {req.language}")
        out = {"result": res.to_dict(), "checks": []}
        if req.lesson and not res.error:
            lesson = lesson_or_404(req.lesson)
            for c in lesson.checks():
                if c["type"] != "query":
                    continue
                out["checks"].append(await grade_query(c, b, req, res, at_ms))
        return out

    async def grade_query(c: dict, b, req: QueryRequest, res, at_ms: int) -> dict:
        must = c.get("must_include", [])
        missing = [m for m in must if m.lower() not in req.query.lower()]
        if missing:
            return checks.result(c, checks.FAIL, f"Your query should use {', '.join(f'`{m}`' for m in missing)}.")
        expect = c.get("expect", {})
        if "rows" in expect:
            ok, need = checks._count_ok(len(res.rows), expect["rows"])
            if not ok:
                return checks.result(c, checks.FAIL, f"Got {len(res.rows)} row(s), expected {need}. {c.get('hint', '')}".strip())
        for col in expect.get("columns", []):
            if col not in res.columns:
                return checks.result(c, checks.FAIL, f"Result has no `{col}` column (columns: {', '.join(res.columns) or 'none'}).")
        if expect.get("top") or "value" in expect:
            vcol = res.columns.index("value") if "value" in res.columns else len(res.columns) - 1
            numeric = [r for r in res.rows if isinstance(r[vcol], (int, float))]
            if not numeric:
                return checks.result(c, checks.FAIL, "The query returned no numbers.")
            top = max(numeric, key=lambda r: r[vcol])
            for label, want in (expect.get("top") or {}).items():
                if label not in res.columns:
                    return checks.result(c, checks.FAIL, f"Group by `{label}` so the answer shows which one stands out.")
                got = top[res.columns.index(label)]
                if str(got) != str(want):
                    return checks.result(c, checks.FAIL, f"Your query points at `{label}={got}`. " + c.get("hint", "Look again."))
            if "value" in expect and not checks._value_matches(top[vcol], expect["value"]):
                return checks.result(c, checks.FAIL, f"Your query returns {top[vcol]:.3g}. " + c.get("hint", "That doesn't show the problem yet."))
        if c.get("reference"):
            ref = await b.adapter.query(c.get("language", req.language), c["reference"], at_ms=at_ms, range_s=req.range_s)
            if ref is None or ref.error:
                return checks.result(c, checks.FAIL, "The reference query failed; is there data yet? Check the scenario traffic is running.")
            same, why = compare_results(res, ref, c)
            if not same:
                return checks.result(c, checks.FAIL, why + (f" {c['hint']}" if c.get("hint") else ""))
        return checks.result(c, checks.PASS, c.get("success", "Your query returns the right answer."))

    def compare_results(res, ref, c: dict) -> tuple[bool, str]:
        tol = float(c.get("tolerance", 0.02))
        ignore = set(c.get("ignore_columns", []))

        def norm(r) -> dict[tuple, list[float]]:
            idx = [i for i, col in enumerate(r.columns) if col not in ignore]
            value_cols = [i for i in idx if r.columns[i] in ("value",) or r.columns[i] in c.get("value_columns", [])]
            key_cols = [i for i in idx if i not in value_cols]
            out: dict[tuple, list[float]] = {}
            for row in r.rows:
                key = tuple(str(row[i]) for i in key_cols)
                vals = []
                for i in value_cols:
                    try:
                        vals.append(float(row[i]))
                    except (TypeError, ValueError):
                        vals.append(math.nan)
                out[key] = vals
            return out

        a, b_ = norm(res), norm(ref)
        if len(a) != len(b_):
            return False, f"Your query returns {len(a)} row(s); the expected answer has {len(b_)}."
        if set(a) != set(b_):
            return False, "The rows (label sets) differ from the expected answer. Check your grouping."
        for k, vals in a.items():
            for x, y in zip(vals, b_[k]):
                if math.isnan(x) and math.isnan(y):
                    continue
                if not math.isclose(x, y, rel_tol=tol, abs_tol=1e-9):
                    return False, f"Values differ (got {x:.4g}, expected {y:.4g})."
        return True, ""

    @app.api_route("/api/proxy/{backend_id}/{path:path}", methods=["GET", "POST"])
    async def proxy(backend_id: str, path: str, request: Request) -> Response:
        """Read-only passthrough declared by a backend's ``proxy`` manifest block."""
        b = backend_or_404(backend_id)
        spec = b.manifest.get("proxy") or {}
        if not spec or not any(path.startswith(prefix) for prefix in spec.get("allow", [])):
            raise HTTPException(403, "Path not allowed by the plugin's proxy rules")
        target = b.settings.get(spec.get("target", ""), "").rstrip("/")
        body = await request.body() if request.method == "POST" else None
        try:
            r = await http.request(request.method, f"{target}/{path}", params=dict(request.query_params), content=body, headers={"content-type": request.headers.get("content-type", "")} if body else None, timeout=8)
        except httpx.HTTPError as e:
            raise HTTPException(502, f"{b.title} unreachable: {type(e).__name__}")
        return Response(content=r.content, status_code=r.status_code, media_type=r.headers.get("content-type"))

    @app.get("/api/suggest/{backend_id}")
    async def suggest(backend_id: str, language: str, kind: str = "metric", prefix: str = "") -> list[str]:
        b = backend_or_404(backend_id)
        return await b.adapter.suggest(language, kind, prefix)

    # ------------------------------------------------------------ quiz & verify
    @app.post("/api/lessons/{pack}/{slug}/answer")
    async def answer(pack: str, slug: str, req: AnswerRequest, request: Request) -> dict:
        lesson = lesson_or_404(f"{pack}/{slug}")
        out = await _answer(lesson, req)
        if out.get("correct") and lesson.kind in ("experiment", "incident"):
            drills.record(lesson.id, request.state.user.display_name, req.question)
        return out

    @app.get("/api/admin/gameday")
    async def gameday() -> dict:
        act = drills.current
        lesson_id = act.lesson if act else None
        lesson = registry.lesson(lesson_id) if lesson_id else None
        questions = [{"id": q.get("id", f"q{i}"), "prompt": q.get("prompt", "")} for i, q in enumerate(((lesson.meta.get("quiz") or {}).get("questions", [])) if lesson else [])]
        return {"activity": act.public(reveal=True) if act else None, "questions": questions, "board": drills.board(lesson_id) if lesson_id else {}}

    async def _answer(lesson, req: AnswerRequest) -> dict:
        questions = (lesson.meta.get("quiz") or {}).get("questions", [])
        for i, q in enumerate(questions):
            if q.get("id", f"q{i}") == req.question and q.get("kind") == "time":
                act = drills.last.get(lesson.id)
                if not act or act.fault_started is None:
                    return {"correct": False, "explanation": "Start the incident and let it run first."}
                try:
                    picked = float(req.answer if isinstance(req.answer, str) else req.answer[0]) / 1000
                except (TypeError, ValueError, IndexError):
                    return {"correct": False, "explanation": "Enter a time."}
                off = picked - act.fault_started
                tol = float(q.get("tolerance_s", 120))
                if abs(off) <= tol:
                    return {"correct": True, "explanation": q.get("explanation", f"It started at {time.strftime('%H:%M:%S', time.localtime(act.fault_started))}.")}
                return {"correct": False, "explanation": f"About {abs(off) / 60:.0f} min too {'late' if off > 0 else 'early'}. " + q.get("hint", "Look for where the line first leaves its usual band.")}
            if q.get("id", f"q{i}") == req.question and q.get("kind") == "outcome":
                act = drills.last.get(lesson.id)
                if not act or act.status == "running":
                    return {"correct": False, "explanation": "Run the experiment to the end first."}
                actual = "aborted" if act.status == "aborted" else "held" if act.hypothesis_held else "rejected"
                if act.status == "stopped":
                    return {"correct": False, "explanation": "The run was stopped early. Run it again to the end."}
                ok = str(req.answer if isinstance(req.answer, str) else req.answer[0]) == actual
                return {"correct": ok, "explanation": q.get("explanation", "") if ok else "Look at the chart again: compare the line to the limit during the fault window."}
            if q.get("id", f"q{i}") == req.question and q.get("kind") == "query":
                b = backend_or_404(q.get("backend", "victoriametrics"))
                learner_q = req.answer if isinstance(req.answer, str) else " ".join(req.answer)
                at_ms = int(time.time() * 1000)
                res = await b.adapter.query(q.get("language", "metricsql"), learner_q, at_ms=at_ms, range_s=900)
                if res is None or res.error:
                    return {"correct": False, "explanation": f"The query failed: {res.error if res else 'unsupported'}"}
                check = {"id": q.get("id"), "type": "query", "title": q.get("prompt", "")} | {k: q[k] for k in ("reference", "must_include", "expect", "tolerance", "value_columns", "ignore_columns", "hint") if k in q}
                graded = await grade_query(check, b, QueryRequest(backend=b.id, language=q.get("language", "metricsql"), query=learner_q), res, at_ms)
                ok = graded["status"] == checks.PASS
                return {"correct": ok, "explanation": q.get("explanation", "That query shows it.") if ok else graded["detail"]}
            if q.get("id", f"q{i}") == req.question:
                expected = q["answer"]
                correct = sorted(map(str, expected)) == sorted(map(str, req.answer)) if isinstance(expected, list) else str(req.answer).strip().lower() == str(expected).strip().lower()
                return {"correct": correct, "explanation": q.get("explanation", "") if correct else q.get("hint", "Not quite. Look again.")}
        raise HTTPException(404, "Unknown question")

    @app.post("/api/lessons/{pack}/{slug}/verify")
    async def verify(pack: str, slug: str) -> dict:
        lesson = lesson_or_404(f"{pack}/{slug}")
        out = []
        for c in lesson.checks():
            if c["type"] != "backend":
                continue
            b = registry.backends.get(c.get("backend", ""))
            if not b or not b.enabled or not b.adapter:
                out.append(checks.result(c, checks.FAIL, f"The `{c.get('backend')}` backend isn't enabled."))
                continue
            try:
                v = await b.adapter.verify(c, {"lesson": lesson.id})
            except Exception as e:
                v = None
                out.append(checks.result(c, checks.FAIL, f"Could not verify: {type(e).__name__}"))
                continue
            if v is None:
                out.append(checks.result(c, checks.FAIL, f"{b.title} can't verify `{c.get('verify')}`."))
            else:
                out.append(checks.result(c, checks.PASS if v.passed else checks.FAIL, v.detail))
        return {"checks": out}

    # ------------------------------------------------------------ scenario
    def scenario_or_404():
        s = registry.scenario()
        if not s:
            raise HTTPException(404, "No scenario enabled")
        return s

    @app.get("/api/scenario")
    async def scenario_state() -> dict:
        s = scenario_or_404()

        async def one(svc: dict) -> dict:
            try:
                r = await http.get(svc["url"].rstrip("/") + "/_stats", timeout=1.5)
                return {k: v for k, v in svc.items() if k != "url"} | {"online": r.status_code == 200, "stats": r.json() if r.status_code == 200 else None}
            except (httpx.HTTPError, ValueError):
                return {k: v for k, v in svc.items() if k != "url"} | {"online": False, "stats": None}

        services = await asyncio.gather(*(one(svc) for svc in s.services()))
        for svc in services:
            if svc["id"] in scenario_changes:
                svc["changed"] = scenario_changes[svc["id"]]
        return s.public() | {"services": services}

    @app.post("/api/scenario/services/{service_id}/chaos")
    async def set_chaos(service_id: str, req: ChaosRequest, ttl_s: float | None = None) -> dict:
        s = scenario_or_404()
        svc = next((x for x in s.services() if x["id"] == service_id), None)
        if not svc:
            raise HTTPException(404, "Unknown service")
        try:
            r = await http.post(svc["url"].rstrip("/") + "/_chaos", json=req.model_dump(exclude_none=True))
            if r.status_code != 200:
                raise HTTPException(502, f"{service_id} rejected the change (HTTP {r.status_code}).")
            state = r.json()
            user = auth.current_user.get()
            active = bool(state.get("active", state.get("latency_ms") or state.get("error_rate")))
            if active:
                scenario_changes[service_id] = {"by": user.display_name if user else "lab", "at": time.time(), "expires": time.time() + ttl_s if ttl_s else None}
            else:
                scenario_changes.pop(service_id, None)
            return state
        except httpx.HTTPError as e:
            raise HTTPException(502, f"{service_id} is unreachable: {type(e).__name__}")

    @app.post("/api/scenario/load")
    async def set_load(req: LoadRequest) -> dict:
        s = scenario_or_404()
        gen = next((x for x in s.services() if x["role"] == "loadgen"), None)
        if not gen:
            raise HTTPException(404, "Scenario has no load generator")
        try:
            r = await http.post(gen["url"].rstrip("/") + "/_load", json={"rps": max(0.0, min(req.rps, 50.0))})
            return r.json()
        except httpx.HTTPError as e:
            raise HTTPException(502, f"Load generator unreachable: {type(e).__name__}")

    async def expire_faults() -> None:
        """Clear faults that lessons injected once their time is up, so a shared lab heals itself."""
        while True:
            await asyncio.sleep(10)
            now = time.time()
            for service_id, change in list(scenario_changes.items()):
                if change.get("expires") and change["expires"] < now:
                    try:
                        await set_chaos(service_id, ChaosRequest(reset=True))
                        log.info("fault on %s expired", service_id)
                    except HTTPException:
                        scenario_changes.pop(service_id, None)

    @app.on_event("startup")
    async def _start_expiry() -> None:
        if registry.scenario():
            asyncio.create_task(expire_faults())

    @app.post("/api/scenario/reset")
    async def reset_scenario() -> dict:
        s = scenario_or_404()
        scenario_changes.clear()
        for svc in s.services():
            if svc["role"] != "loadgen":
                try:
                    await http.post(svc["url"].rstrip("/") + "/_chaos", json={"reset": True})
                except httpx.HTTPError:
                    pass
        return {"ok": True}

    # ------------------------------------------------------------ experiments & incidents
    async def _apply(faults: dict[str, dict]) -> None:
        for service_id, settings_ in faults.items():
            try:
                await set_chaos(service_id, ChaosRequest(**settings_))
            except HTTPException as e:
                log.warning("could not apply fault to %s: %s", service_id, e.detail)

    async def _load(rps: float) -> None:
        try:
            await set_load(LoadRequest(rps=rps))
        except HTTPException:
            pass

    async def _reset() -> None:
        try:
            await reset_scenario()
            await _load(2)
        except HTTPException:
            pass

    async def _query(backend_id: str, language: str, q: str) -> float | None:
        b = registry.backends.get(backend_id)
        if not b or not b.enabled or not b.adapter:
            return None
        try:
            return scalar(await b.adapter.query(language, q, range_s=60))
        except Exception:
            return None

    drills = Drills(_apply, _load, _reset, _query)
    app.state.drills = drills

    @app.get("/api/activity")
    async def activity(lesson: str | None = None) -> dict:
        last = drills.last.get(lesson) if lesson else None
        return {"current": drills.state(), "last": last.public() if last and last is not drills.current else None}

    @app.post("/api/lessons/{pack}/{slug}/start")
    async def start_activity(pack: str, slug: str, request: Request) -> dict:
        lesson = lesson_or_404(f"{pack}/{slug}")
        if lesson.kind not in ("experiment", "incident"):
            raise HTTPException(400, "This lesson has nothing to start.")
        user = request.state.user
        if settings.scenario_control == "admins" and user.role != "admin":
            raise HTTPException(403, "On this deployment, only admins start experiments and incidents.")
        if not registry.scenario():
            raise HTTPException(400, "No scenario is enabled.")
        try:
            act = drills.start(lesson.kind, lesson.id, lesson.meta.get("title", lesson.id), user.display_name, lesson.meta.get(lesson.kind) or {})
        except RuntimeError as e:
            raise HTTPException(409, str(e))
        return act.public()

    @app.post("/api/activity/stop")
    async def stop_activity(request: Request) -> dict:
        user = request.state.user
        cur = drills.current
        if cur and cur.status == "running" and cur.by != user.display_name and user.role != "admin":
            raise HTTPException(403, f"Only {cur.by} or an admin can stop this.")
        await drills.stop(f"Stopped by {user.display_name}")
        return {"ok": True}

    @app.post("/api/lessons/{pack}/{slug}/setup")
    async def setup_lesson(pack: str, slug: str) -> dict:
        """Apply the scenario state a lesson needs (e.g. inject a fault to investigate)."""
        lesson = lesson_or_404(f"{pack}/{slug}")
        spec = lesson.meta.get("scenario") or {}
        s = registry.scenario()
        if not s or not spec:
            return {"applied": []}
        applied = []
        if spec.get("reset", True):
            await reset_scenario()
        for service_id, chaos in (spec.get("chaos") or {}).items():
            try:
                await set_chaos(service_id, ChaosRequest(**chaos), ttl_s=settings.fault_ttl_s)
                applied.append(service_id)
            except HTTPException:
                pass
        if "load" in spec:
            try:
                await set_load(LoadRequest(rps=spec["load"]))
            except HTTPException:
                pass
        return {"applied": applied}

    # ------------------------------------------------------------ static UI
    @app.get("/healthz")
    async def healthz() -> dict:
        return {"ok": True}

    static = settings.static_dir
    if (static / "index.html").exists():
        app.mount("/assets", StaticFiles(directory=static / "assets"), name="assets")

        @app.get("/{path:path}")
        async def spa(path: str):
            if path.startswith(("api/", "tap/")):
                raise HTTPException(404)
            candidate = static / path
            if path and candidate.is_file() and static in candidate.resolve().parents:
                return FileResponse(candidate)
            return FileResponse(static / "index.html", headers={"Cache-Control": "no-cache"})

    return app
