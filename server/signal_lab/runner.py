"""Execute learner code with real OpenTelemetry auto-configuration.

Code runs as ``opentelemetry-instrument python main.py`` in a throwaway
directory: the same way you'd run a service in production. The SDK is
configured entirely through ``OTEL_*`` environment variables, which the lab
shows to the learner.

The runner can work in-process (dev) or as its own service (compose / Helm),
so untrusted code can be isolated from the API with its own security context,
resource limits and network policy.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import AsyncIterator

import httpx

MAX_OUTPUT_LINES = 1500
MAX_LINE_CHARS = 4000


def _instrument_cmd() -> list[str]:
    exe = Path(sys.executable)
    script = exe.with_name("opentelemetry-instrument")
    if script.exists():
        return [str(script), str(exe)]
    found = shutil.which("opentelemetry-instrument")
    if found:
        return [found, str(exe)]
    return [str(exe), "-c", "from opentelemetry.instrumentation.auto_instrumentation import run; run()", str(exe)]


def _limits(memory_mb: int, cpu_s: int):
    def apply() -> None:  # pragma: no cover - runs in the child
        try:
            import resource

            resource.setrlimit(resource.RLIMIT_AS, (memory_mb * 1024 * 1024,) * 2)
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_s, cpu_s))
            resource.setrlimit(resource.RLIMIT_NPROC, (256, 256))
        except Exception:
            pass
        os.setsid()

    return apply


async def execute_local(code: str, env: dict[str, str], *, timeout: float = 20, auto_instrument: bool = True, memory_mb: int = 768) -> AsyncIterator[dict]:
    workdir = Path(tempfile.mkdtemp(prefix="signal-lab-run-"))
    (workdir / "main.py").write_text(code)
    child_env = {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "HOME": str(workdir),
        "LANG": "C.UTF-8",
        "PYTHONUNBUFFERED": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    } | env
    cmd = (_instrument_cmd() if auto_instrument else [sys.executable]) + ["main.py"]
    started = time.monotonic()
    yield {"type": "start", "command": " ".join(["opentelemetry-instrument python" if auto_instrument else "python", "main.py"])}
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=workdir,
        env=child_env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        preexec_fn=_limits(memory_mb, int(timeout) + 5),
    )
    queue: asyncio.Queue = asyncio.Queue()
    lines = 0

    async def pump(stream: asyncio.StreamReader, name: str) -> None:
        while True:
            raw = await stream.readline()
            if not raw:
                break
            await queue.put({"type": "output", "stream": name, "text": raw.decode(errors="replace").rstrip("\n")[:MAX_LINE_CHARS], "t": round((time.monotonic() - started) * 1000)})
        await queue.put(None)

    tasks = [asyncio.create_task(pump(proc.stdout, "stdout")), asyncio.create_task(pump(proc.stderr, "stderr"))]  # type: ignore[arg-type]
    done_streams = 0
    timed_out = False
    deadline = started + timeout
    try:
        while done_streams < 2:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                break
            try:
                item = await asyncio.wait_for(queue.get(), timeout=remaining)
            except asyncio.TimeoutError:
                timed_out = True
                break
            if item is None:
                done_streams += 1
                continue
            lines += 1
            if lines <= MAX_OUTPUT_LINES:
                yield item
            elif lines == MAX_OUTPUT_LINES + 1:
                yield {"type": "output", "stream": "system", "text": f"… output truncated after {MAX_OUTPUT_LINES} lines"}
        if timed_out:
            try:
                os.killpg(proc.pid, 9)
            except ProcessLookupError:
                pass
            yield {"type": "output", "stream": "system", "text": f"Stopped: the program ran longer than {timeout:g}s."}
        code_ = await proc.wait()
    finally:
        for t in tasks:
            t.cancel()
        shutil.rmtree(workdir, ignore_errors=True)
    yield {"type": "exit", "code": -9 if timed_out else code_, "duration_ms": round((time.monotonic() - started) * 1000, 1)}


async def execute_remote(url: str, code: str, env: dict[str, str], *, timeout: float = 20, auto_instrument: bool = True) -> AsyncIterator[dict]:
    payload = {"code": code, "env": env, "timeout": timeout, "auto_instrument": auto_instrument}
    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout + 15, connect=5)) as client:
        try:
            async with client.stream("POST", url.rstrip("/") + "/exec", json=payload) as r:
                if r.status_code != 200:
                    yield {"type": "output", "stream": "system", "text": f"Runner returned HTTP {r.status_code}"}
                    yield {"type": "exit", "code": -1, "duration_ms": 0}
                    return
                async for line in r.aiter_lines():
                    if line.strip():
                        yield json.loads(line)
        except httpx.HTTPError as e:
            yield {"type": "output", "stream": "system", "text": f"Could not reach the runner at {url}: {type(e).__name__}"}
            yield {"type": "exit", "code": -1, "duration_ms": 0}


from pydantic import BaseModel


class ExecRequest(BaseModel):
    code: str
    env: dict[str, str] = {}
    timeout: float = 20
    auto_instrument: bool = True


def create_runner_app():
    """Stand-alone runner service: ``python -m signal_lab runner``."""
    from fastapi import FastAPI
    from fastapi.responses import StreamingResponse

    app = FastAPI(title="Signal Lab runner")
    max_timeout = float(os.getenv("SIGNAL_LAB_RUN_TIMEOUT", "30"))
    semaphore = asyncio.Semaphore(int(os.getenv("SIGNAL_LAB_RUNNER_CONCURRENCY", "4")))

    @app.get("/healthz")
    async def healthz() -> dict:
        return {"ok": True}

    @app.post("/exec")
    async def exec_(req: ExecRequest):
        async def stream():
            async with semaphore:
                async for ev in execute_local(req.code, req.env, timeout=min(req.timeout, max_timeout), auto_instrument=req.auto_instrument):
                    yield json.dumps(ev) + "\n"

        return StreamingResponse(stream(), media_type="application/x-ndjson")

    return app
