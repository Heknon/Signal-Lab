"""Warm start for learner runs.

``opentelemetry-instrument python main.py`` spends ~1.5 s importing the SDK, the
exporters and every instrumentation package before the first line of learner
code runs. This helper does those imports once, then forks a ready interpreter
per run. Each child does exactly what ``opentelemetry-instrument`` does: it takes
the run's ``OTEL_*`` environment, calls ``auto_instrumentation.initialize()``
(the same function its sitecustomize calls), and runs ``main.py`` as __main__.

Nothing is configured in the parent: no TracerProvider, no logging handlers,
no instrumentation applied. Children start from the same clean state as a cold
start, minus the import time.

Protocol (SOCK_SEQPACKET on the fd given as argv[1], one JSON message per packet):
    request:  {"id", "cwd", "env", "auto", "memory_mb", "cpu_s"} + 2 fds (stdout, stderr)
    replies:  {"id", "pid"} after the fork, {"id", "exit"} when the child ends
"""

from __future__ import annotations

import json
import os
import resource
import runpy
import select
import signal
import socket
import sys
import traceback


def preload() -> None:
    """Import what sitecustomize would import, without initialising anything."""
    from importlib.metadata import entry_points

    import opentelemetry.instrumentation.auto_instrumentation  # noqa: F401
    import opentelemetry.sdk._logs  # noqa: F401
    import opentelemetry.sdk.metrics  # noqa: F401
    import opentelemetry.sdk.trace  # noqa: F401

    for group in ("opentelemetry_distro", "opentelemetry_configurator", "opentelemetry_instrumentor",
                  "opentelemetry_traces_exporter", "opentelemetry_metrics_exporter", "opentelemetry_logs_exporter",
                  "opentelemetry_propagator", "opentelemetry_resource_detector", "opentelemetry_id_generator"):
        for ep in entry_points(group=group):
            try:
                ep.load()  # imports the module; nothing is instrumented or configured yet
            except Exception:
                pass


def serve(sock: socket.socket):
    """Fork a child per request; report pids and exit codes. Returns only in a child."""
    children: dict[int, str] = {}
    signal.signal(signal.SIGCHLD, lambda *_: None)  # wake select() when a child exits
    while True:
        try:
            ready, _, _ = select.select([sock], [], [], 0.05)
        except InterruptedError:
            ready = []
        if ready:
            msg, fds, _, _ = socket.recv_fds(sock, 1 << 20, 2)
            if not msg:
                return None  # the runner went away
            req = json.loads(msg)
            pid = os.fork()
            if pid == 0:
                sock.close()
                return req, fds
            for fd in fds:
                os.close(fd)
            children[pid] = req["id"]
            sock.send(json.dumps({"id": req["id"], "pid": pid}).encode())
        while children:
            try:
                pid, status = os.waitpid(-1, os.WNOHANG)
            except ChildProcessError:
                break
            if pid == 0:
                break
            rid = children.pop(pid, None)
            if rid is not None:
                sock.send(json.dumps({"id": rid, "exit": os.waitstatus_to_exitcode(status)}).encode())


def _user_traceback(exc: BaseException, main: str) -> None:
    """Print a traceback starting at main.py, like a plain `python main.py` would."""
    tb = exc.__traceback__
    while tb is not None and tb.tb_frame.f_code.co_filename != main:
        tb = tb.tb_next
    traceback.print_exception(type(exc), exc, tb or exc.__traceback__)


def run_child(req: dict, fds: list[int]) -> None:
    signal.signal(signal.SIGCHLD, signal.SIG_DFL)
    os.setsid()  # own process group, so the runner can kill the whole run
    try:
        if req.get("memory_mb"):
            resource.setrlimit(resource.RLIMIT_AS, (req["memory_mb"] * 1024 * 1024,) * 2)
        resource.setrlimit(resource.RLIMIT_CPU, (req["cpu_s"], req["cpu_s"]))
        resource.setrlimit(resource.RLIMIT_NPROC, (256, 256))
    except Exception:
        pass
    devnull = os.open(os.devnull, os.O_RDONLY)
    os.dup2(devnull, 0)
    os.dup2(fds[0], 1)
    os.dup2(fds[1], 2)
    os.closerange(3, 65536)
    sys.stdin = open(0, closefd=False)
    sys.stdout = open(1, "w", buffering=1, encoding="utf-8", errors="replace", closefd=False)
    sys.stderr = open(2, "w", buffering=1, encoding="utf-8", errors="replace", closefd=False)

    os.chdir(req["cwd"])
    os.environ.clear()
    os.environ.update(req["env"])
    main = os.path.join(req["cwd"], "main.py")
    sys.argv = [main]
    sys.path[0] = req["cwd"]

    code = 0
    try:
        if req.get("auto"):
            from opentelemetry.instrumentation.auto_instrumentation import initialize

            initialize()
        runpy.run_path(main, run_name="__main__")
    except SystemExit as e:
        if e.code is None or isinstance(e.code, int):
            code = e.code or 0
        else:
            print(e.code, file=sys.stderr)
            code = 1
    except BaseException as e:  # noqa: BLE001 - report like the interpreter would
        _user_traceback(e, main)
        code = 1
    sys.stdout.flush()
    sys.stderr.flush()
    raise SystemExit(code)  # normal interpreter exit: atexit hooks flush the SDK


def main() -> None:
    sock = socket.socket(fileno=int(sys.argv[1]))
    preload()
    sock.send(b'{"ready": true}')
    job = serve(sock)
    if job is not None:
        run_child(*job)


if __name__ == "__main__":
    main()
