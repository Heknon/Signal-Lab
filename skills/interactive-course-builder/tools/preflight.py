#!/usr/bin/env python3
"""Phase 0: record what this machine has, so every later phase uses only what is installed.

Makes no network connections unless --probe is given. Writes course/environment.md
(or --out) and prints the same report.

Usage:
    python tools/preflight.py --target ../target-repo
    python tools/preflight.py --target ../target-repo --probe pypi.org:443   # optional one-off reachability test
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

TOOLS = [
    # (command, version args, what it enables)
    ("git", ["--version"], "history-based evidence in phase 1"),
    ("docker", ["--version"], "container runner, Compose packaging"),
    ("podman", ["--version"], "container runner (Docker alternative)"),
    ("node", ["--version"], "web UI build"),
    ("bun", ["--version"], "web UI build"),
    ("npm", ["--version"], "web UI build"),
    ("go", ["version"], "building Go components (e.g. a custom Collector)"),
    ("helm", ["version", "--short"], "chart lint and render"),
    ("kubectl", ["version", "--client"], "Kubernetes checks"),
    ("psql", ["--version"], "team mode against Postgres"),
    ("pg_ctl", ["--version"], "a local Postgres for team-mode tests"),
    ("unshare", ["--version"], "running verification with networking disabled"),
]
PY_MODULES = ["yaml", "fastapi", "uvicorn", "pydantic", "psycopg", "httpx", "requests", "pytest", "playwright"]
CHROME_GLOBS = [
    os.environ.get("CHROME_PATH", ""),
    "/opt/pw-browsers/chromium-*/chrome-linux*/chrome",
    os.path.expanduser("~/.cache/ms-playwright/chromium-*/chrome-linux*/chrome"),
    "/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]


def run(cmd: list[str], timeout: int = 10) -> str | None:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    text = (out.stdout or out.stderr).strip().splitlines()
    return text[0][:100] if out.returncode == 0 and text else None


def find_chrome() -> str | None:
    for pattern in CHROME_GLOBS:
        if not pattern:
            continue
        for path in sorted(glob.glob(pattern), reverse=True):
            if os.access(path, os.X_OK):
                return path
    return None


def node_has(module: str) -> bool:
    if not shutil.which("node"):
        return False
    return subprocess.run(["node", "-e", f"require('{module}')"], capture_output=True).returncode == 0


def docker_images() -> list[str]:
    if not shutil.which("docker"):
        return []
    try:
        out = subprocess.run(["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"],
                             capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return []
    return sorted({l for l in out.stdout.splitlines() if l and "<none>" not in l}) if out.returncode == 0 else []


def package_sources() -> list[tuple[str, str]]:
    """Local package sources: mirrors, wheelhouses and caches that work without internet."""
    found = []
    for var in ("PIP_INDEX_URL", "PIP_EXTRA_INDEX_URL", "PIP_FIND_LINKS", "UV_INDEX_URL",
                "npm_config_registry", "NPM_CONFIG_REGISTRY", "BUN_CONFIG_REGISTRY", "GOPROXY", "GOFLAGS"):
        if os.environ.get(var):
            found.append((var, os.environ[var]))
    for conf in ("~/.config/pip/pip.conf", "~/.pip/pip.conf", "/etc/pip.conf", "~/.npmrc", "~/.bunfig.toml", "bunfig.toml"):
        p = Path(os.path.expanduser(conf))
        if p.exists():
            keys = [l.strip() for l in p.read_text(errors="replace").splitlines()
                    if any(k in l for k in ("index", "find-links", "registry"))]
            found.append((str(p), "; ".join(keys) or "present"))
    for d in ("wheelhouse", "vendor", "~/.cache/pip/wheels", "~/.bun/install/cache", "~/.npm/_cacache",
              "~/go/pkg/mod", "/opt/wheels"):
        p = Path(os.path.expanduser(d))
        if p.is_dir():
            n = sum(1 for _ in p.iterdir())
            found.append((str(p), f"{n} entries"))
    return found


def probe(hostport: str) -> str:
    host, _, port = hostport.rpartition(":")
    try:
        with socket.create_connection((host, int(port)), timeout=3):
            return f"{hostport} reachable"
    except OSError as e:
        return f"{hostport} not reachable ({e.__class__.__name__})"


CODE_SUFFIXES = {".py", ".go", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".java", ".kt", ".scala", ".rs", ".rb",
                 ".c", ".h", ".cpp", ".cc", ".cs", ".php", ".swift", ".sh", ".ex", ".exs", ".erl", ".hs"}
SKIP_DIRS = {"node_modules", "vendor", "dist", "build", "venv", "env", "site-packages", "__pycache__",
             "target", "coverage", "htmlcov"}


def target_facts(target: Path) -> list[tuple[str, str]]:
    facts = [("path", str(target.resolve()))]
    if (target / ".git").exists() and shutil.which("git"):
        facts.append(("commit", run(["git", "-C", str(target), "rev-parse", "--short", "HEAD"]) or "?"))
        count = run(["git", "-C", str(target), "rev-list", "--count", "HEAD"])
        facts.append(("history", f"{count} commits available" + (" (shallow clone)" if (target / ".git" / "shallow").exists() else "")))
    else:
        facts.append(("history", "no git history: phase 1 uses docs, tests, changelog and code comments"))
    for name in ("docs", "doc", "tests", "test", "examples", "CHANGELOG.md", "CHANGES.rst", "HISTORY.md"):
        if (target / name).exists():
            facts.append((name, "present"))
    exts: dict[str, int] = {}
    lines = 0
    for p in target.rglob("*"):
        rel = p.relative_to(target).parts
        skip = any(part.startswith(".") or part in SKIP_DIRS for part in rel[:-1])
        if p.is_file() and not skip:
            exts[p.suffix] = exts.get(p.suffix, 0) + 1
            if p.suffix in CODE_SUFFIXES:
                try:
                    lines += sum(1 for _ in p.open(errors="replace"))
                except OSError:
                    pass
    top = ", ".join(f"{k or '(none)'}: {v}" for k, v in sorted(exts.items(), key=lambda kv: -kv[1])[:6])
    facts += [("source lines", f"{lines} (code files; hidden, vendored and build folders excluded)"), ("file types", top)]
    return facts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", type=Path, required=True, help="the target system's source folder")
    ap.add_argument("--out", type=Path, default=Path("course/environment.md"))
    ap.add_argument("--probe", action="append", default=[], help="host:port to test once (default: no network use)")
    args = ap.parse_args()

    tools = []
    for cmd, vargs, use in TOOLS:
        ver = run([cmd, *vargs]) if shutil.which(cmd) else None
        tools.append((cmd, ver or "missing", use))
    tools.append((f"python {sys.version.split()[0]}", sys.executable, "tools, server code"))
    chrome = find_chrome()
    tools.append(("chromium", chrome or "missing", "phase 7 screenshots (tools/screenshots.py)"))
    tools.append(("playwright (node)", "present" if node_has("playwright") else "missing", "phase 7 overflow measurement"))
    mods = [(m, "present" if importlib.util.find_spec(m) else "missing") for m in PY_MODULES]
    images = docker_images()
    sources = package_sources()
    network = [probe(h) for h in args.probe] or ["not probed: treat as offline (air-gapped)"]

    md = [f"# Environment\n\nGenerated by `tools/preflight.py` on {dt.date.today()}. Re-run it if the machine changes.\n",
          "## Network\n", *[f"- {n}" for n in network],
          "\nEvery later phase assumes no network unless a probe above says otherwise.\n",
          "## Target\n", "| Fact | Value |", "|---|---|", *[f"| {k} | {v} |" for k, v in target_facts(args.target)],
          "\n## Tools\n", "| Tool | Version or path | Enables |", "|---|---|---|", *[f"| {a} | {b} | {c} |" for a, b, c in tools],
          "\n## Python modules\n", "| Module | Status |", "|---|---|", *[f"| {a} | {b} |" for a, b in mods],
          "\n## Container images\n", *([f"- `{i}`" for i in images] or ["- none available locally"]),
          "\n## Package sources\n", *([f"- `{a}`: {b}" for a, b in sources] or ["- none found: only what is already installed can be used"]),
          "\n## Decisions\n", "- {{what this machine can and cannot do, and the choices it forces for phases 4, 6 and 7}}\n"]
    text = "\n".join(md)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    print(text)
    print(f"wrote {args.out}. Fill in Decisions, then run lint_artifacts.py on it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
