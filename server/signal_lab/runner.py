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
import logging
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid
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


def _limits(memory_mb: int | None, cpu_s: int):
    def apply() -> None:  # pragma: no cover - runs in the child
        try:
            import resource

            if memory_mb:  # Go programs reserve huge virtual memory; they use GOMEMLIMIT instead
                resource.setrlimit(resource.RLIMIT_AS, (memory_mb * 1024 * 1024,) * 2)
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_s, cpu_s))
            resource.setrlimit(resource.RLIMIT_NPROC, (256, 256))
        except Exception:
            pass
        os.setsid()

    return apply


log = logging.getLogger(__name__)


class WarmProcess:
    """A run forked from the warm helper; quacks like asyncio.subprocess.Process."""

    def __init__(self, pid: int, exit_future: asyncio.Future, stdout: asyncio.StreamReader, stderr: asyncio.StreamReader):
        self.pid, self.stdout, self.stderr = pid, stdout, stderr
        self._exit = exit_future
        self.returncode: int | None = None
        exit_future.add_done_callback(lambda f: setattr(self, "returncode", f.result()))

    async def wait(self) -> int:
        return await asyncio.shield(self._exit)


class WarmStarter:
    """Client for signal_lab.warm: a helper that has imported OpenTelemetry once and
    forks a ready interpreter per run (~0.1 s instead of ~1.5 s). See warm.py."""

    def __init__(self) -> None:
        self.sock: socket.socket | None = None
        self.proc: subprocess.Popen | None = None
        self.loop: asyncio.AbstractEventLoop | None = None
        self.pending: dict[str, dict[str, asyncio.Future]] = {}
        self.lock: asyncio.Lock | None = None
        self.disabled = os.getenv("SIGNAL_LAB_WARM_START", "1") == "0"

    def _start(self) -> bool:
        parent, child = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        env = {k: v for k, v in os.environ.items() if not k.startswith("OTEL_")}
        env["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent) + os.pathsep + env.get("PYTHONPATH", "")
        proc = subprocess.Popen([sys.executable, "-m", "signal_lab.warm", str(child.fileno())],
                                pass_fds=(child.fileno(),), env=env)
        child.close()
        parent.settimeout(30)
        try:
            if json.loads(parent.recv(4096)).get("ready") is not True:
                raise RuntimeError("bad hello")
        except Exception as e:
            log.warning("warm start unavailable, using cold starts: %s", e)
            proc.kill()
            return False
        parent.settimeout(None)
        self.sock, self.proc = parent, proc
        threading.Thread(target=self._read, args=(parent,), daemon=True).start()
        log.info("warm start ready (pid %s)", proc.pid)
        return True

    def _read(self, sock: socket.socket) -> None:
        while True:
            try:
                msg = sock.recv(4096)
            except OSError:
                msg = b""
            if not msg:
                break
            data = json.loads(msg)
            futs = self.pending.get(data["id"])
            if not futs or not self.loop:
                continue
            key = "pid" if "pid" in data else "exit"
            self.loop.call_soon_threadsafe(lambda f=futs[key], v=data[key]: f.done() or f.set_result(v))
            if key == "exit":
                self.pending.pop(data["id"], None)
        # helper died: fail whatever is still waiting, and start a new one next time
        self.sock = None
        for futs in list(self.pending.values()):
            for f in futs.values():
                if self.loop:
                    self.loop.call_soon_threadsafe(lambda f=f: f.done() or f.set_result(-1))
        self.pending.clear()

    async def ensure(self) -> socket.socket | None:
        """Start the helper if it isn't running (also called at runner start-up)."""
        if self.disabled:
            return None
        self.loop = asyncio.get_running_loop()
        self.lock = self.lock or asyncio.Lock()
        async with self.lock:
            if self.sock is None and not await asyncio.to_thread(self._start):
                self.disabled = True
            return self.sock

    async def spawn(self, cwd: Path, env: dict[str, str], memory_mb: int | None, cpu_s: int) -> WarmProcess | None:
        sock = await self.ensure()
        if sock is None:
            return None
        rid = uuid.uuid4().hex
        futs = {"pid": self.loop.create_future(), "exit": self.loop.create_future()}
        self.pending[rid] = futs
        out_r, out_w = os.pipe()
        err_r, err_w = os.pipe()
        try:
            socket.send_fds(sock, [json.dumps({"id": rid, "cwd": str(cwd), "env": env, "auto": True,
                                                "memory_mb": memory_mb, "cpu_s": cpu_s}).encode()], [out_w, err_w])
        except OSError as e:
            log.warning("warm start failed, using a cold start: %s", e)
            self.pending.pop(rid, None)
            self.sock = None
            for fd in (out_r, out_w, err_r, err_w):
                os.close(fd)
            return None
        finally:
            for fd in (out_w, err_w):
                try:
                    os.close(fd)
                except OSError:
                    pass
        pid = await asyncio.wait_for(futs["pid"], timeout=10)
        return WarmProcess(pid, futs["exit"], await _fd_reader(out_r), await _fd_reader(err_r))


async def _fd_reader(fd: int) -> asyncio.StreamReader:
    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader()
    await loop.connect_read_pipe(lambda: asyncio.StreamReaderProtocol(reader), os.fdopen(fd, "rb", 0))
    return reader


warm = WarmStarter()


COLLECTOR_BIN = os.getenv("SIGNAL_LAB_COLLECTOR_BIN", "otelcol-lab")


def _free_port() -> int:
    import socket

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


async def _port_open(port: int, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            _, writer = await asyncio.open_connection("127.0.0.1", port)
            writer.close()
            return True
        except OSError:
            await asyncio.sleep(0.1)
    return False


def _collector_base(port: int, tap_url: str) -> str:
    """Wiring every hands-on lesson shares: the learner adds processors and pipelines."""
    return f"""receivers:
  otlp:
    protocols:
      http:
        endpoint: 127.0.0.1:{port}
exporters:
  otlphttp/lab:
    endpoint: {tap_url}
    encoding: proto
    retry_on_failure:
      enabled: false
  debug:
    verbosity: basic
service:
  telemetry:
    logs:
      level: warn
      encoding: console
    metrics:
      level: none
"""


async def execute_local(
    code: str,
    env: dict[str, str],
    *,
    timeout: float = 20,
    auto_instrument: bool = True,
    memory_mb: int = 768,
    collector_config: str | None = None,
    tap_url: str | None = None,
    settle_s: float = 3,
) -> AsyncIterator[dict]:
    """Run learner code. With ``collector_config``, ``code`` is the lesson's
    traffic script and it is sent through a Collector built from the learner's config."""
    workdir = Path(tempfile.mkdtemp(prefix="signal-lab-run-"))
    (workdir / "main.py").write_text(code)
    child_env = {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "HOME": str(workdir),
        "LANG": "C.UTF-8",
        "PYTHONUNBUFFERED": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    } | env
    started = time.monotonic()
    queue: asyncio.Queue = asyncio.Queue()
    lines = 0
    procs: list[asyncio.subprocess.Process] = []
    pumps: list[asyncio.Task] = []

    async def pump(stream: asyncio.StreamReader, name: str) -> None:
        while True:
            raw = await stream.readline()
            if not raw:
                break
            await queue.put({"type": "output", "stream": name, "text": raw.decode(errors="replace").rstrip("\n")[:MAX_LINE_CHARS], "t": round((time.monotonic() - started) * 1000)})

    async def spawn(cmd: list[str], out_name: str, err_name: str, proc_env: dict[str, str], limit_memory: bool = True) -> asyncio.subprocess.Process:
        proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=workdir, env=proc_env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            preexec_fn=_limits(memory_mb if limit_memory else None, int(timeout) + 15),
        )
        procs.append(proc)
        pumps.append(asyncio.create_task(pump(proc.stdout, out_name)))  # type: ignore[arg-type]
        pumps.append(asyncio.create_task(pump(proc.stderr, err_name)))  # type: ignore[arg-type]
        return proc

    def drain() -> list[dict]:
        nonlocal lines
        out = []
        while not queue.empty():
            item = queue.get_nowait()
            lines += 1
            if lines <= MAX_OUTPUT_LINES:
                out.append(item)
            elif lines == MAX_OUTPUT_LINES + 1:
                out.append({"type": "output", "stream": "system", "text": f"… output truncated after {MAX_OUTPUT_LINES} lines"})
        return out

    collector = None
    try:
        if collector_config is not None:
            port = _free_port()
            (workdir / "base.yaml").write_text(_collector_base(port, tap_url or "http://127.0.0.1:8000/tap"))
            (workdir / "collector.yaml").write_text(collector_config)
            configs = ["--config=base.yaml", "--config=collector.yaml"]
            yield {"type": "start", "command": "otelcol " + " ".join(configs)}
            check = await asyncio.create_subprocess_exec(
                COLLECTOR_BIN, "validate", *configs, cwd=workdir, env={"PATH": child_env["PATH"], "HOME": str(workdir), "GOMEMLIMIT": "256MiB"},
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
            )
            out, _ = await check.communicate()
            if check.returncode != 0:
                for line in out.decode(errors="replace").splitlines():
                    if line.strip():
                        yield {"type": "output", "stream": "stderr", "text": "collector: " + line.strip()[:MAX_LINE_CHARS]}
                yield {"type": "exit", "code": 2, "duration_ms": round((time.monotonic() - started) * 1000, 1)}
                return
            collector = await spawn([COLLECTOR_BIN, *configs], "collector", "collector", {"PATH": child_env["PATH"], "HOME": str(workdir), "GOMEMLIMIT": "256MiB"}, limit_memory=False)
            if not await _port_open(port, 10):
                await asyncio.sleep(0.2)
                for item in drain():
                    yield item
                yield {"type": "output", "stream": "system", "text": "The Collector didn't start. See its output above."}
                yield {"type": "exit", "code": 2, "duration_ms": round((time.monotonic() - started) * 1000, 1)}
                return
            child_env = child_env | {"OTEL_EXPORTER_OTLP_ENDPOINT": f"http://127.0.0.1:{port}"}
            yield {"type": "output", "stream": "system", "text": f"Collector listening on :{port}. Sending the lesson's traffic through it…"}
        else:
            yield {"type": "start", "command": ("opentelemetry-instrument python" if auto_instrument else "python") + " main.py"}

        program = None
        if auto_instrument:
            # Same as `opentelemetry-instrument python main.py`, forked from a warm interpreter.
            program = await warm.spawn(workdir, child_env, memory_mb, int(timeout) + 15)
            if program is not None:
                procs.append(program)  # type: ignore[arg-type]
                pumps.append(asyncio.create_task(pump(program.stdout, "stdout")))
                pumps.append(asyncio.create_task(pump(program.stderr, "stderr")))
        if program is None:
            cmd = (_instrument_cmd() if auto_instrument else [sys.executable]) + ["main.py"]
            program = await spawn(cmd, "stdout", "stderr", child_env)
        deadline = started + timeout
        timed_out = False
        while True:
            try:
                code_ = await asyncio.wait_for(program.wait(), timeout=0.1)
                break
            except asyncio.TimeoutError:
                for item in drain():
                    yield item
                if time.monotonic() > deadline:
                    timed_out = True
                    try:
                        os.killpg(program.pid, 9)
                    except ProcessLookupError:
                        pass
                    code_ = -9
                    break
        await asyncio.sleep(0.1)
        for item in drain():
            yield item
        if timed_out:
            yield {"type": "output", "stream": "system", "text": f"Stopped: the program ran longer than {timeout:g}s."}

        if collector is not None:
            # Give processors with buffers (batch, tail_sampling) time, then shut down cleanly so they flush.
            settle_deadline = time.monotonic() + settle_s
            while time.monotonic() < settle_deadline:
                await asyncio.sleep(0.2)
                for item in drain():
                    yield item
            if collector.returncode is None:
                collector.terminate()
                try:
                    await asyncio.wait_for(collector.wait(), timeout=10)
                except asyncio.TimeoutError:
                    collector.kill()
            await asyncio.sleep(0.1)
            for item in drain():
                yield item
    finally:
        for p in procs:
            if p.returncode is None:
                try:
                    os.killpg(p.pid, 9)
                except ProcessLookupError:
                    pass
        for t in pumps:
            t.cancel()
        shutil.rmtree(workdir, ignore_errors=True)
    yield {"type": "exit", "code": code_, "duration_ms": round((time.monotonic() - started) * 1000, 1)}


async def execute_remote(url: str, code: str, env: dict[str, str], *, timeout: float = 20, auto_instrument: bool = True, **extra) -> AsyncIterator[dict]:
    payload = {"code": code, "env": env, "timeout": timeout, "auto_instrument": auto_instrument} | extra
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
    collector_config: str | None = None
    tap_url: str | None = None
    settle_s: float = 3


def create_runner_app():
    """Stand-alone runner service: ``python -m signal_lab runner``."""
    from fastapi import FastAPI
    from fastapi.responses import StreamingResponse

    app = FastAPI(title="Signal Lab runner")
    max_timeout = float(os.getenv("SIGNAL_LAB_RUN_TIMEOUT", "30"))
    semaphore = asyncio.Semaphore(int(os.getenv("SIGNAL_LAB_RUNNER_CONCURRENCY", "4")))

    @app.on_event("startup")
    async def prewarm() -> None:
        asyncio.create_task(warm.ensure())  # the first run shouldn't pay for the imports

    @app.get("/healthz")
    async def healthz() -> dict:
        return {"ok": True, "warm_start": warm.sock is not None}

    @app.post("/exec")
    async def exec_(req: ExecRequest):
        async def stream():
            async with semaphore:
                async for ev in execute_local(
                    req.code, req.env, timeout=min(req.timeout, max_timeout), auto_instrument=req.auto_instrument,
                    collector_config=req.collector_config, tap_url=req.tap_url, settle_s=min(req.settle_s, 15),
                ):
                    yield json.dumps(ev) + "\n"

        return StreamingResponse(stream(), media_type="application/x-ndjson")

    return app
