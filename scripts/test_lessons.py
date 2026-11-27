#!/usr/bin/env python3
"""Smoke-test lessons against a running lab.

For every code lesson: the solution must pass all checks, and the starter
must fail at least one (otherwise the exercise is a no-op). Query lessons run
their solution query.

    python scripts/test_lessons.py                       # all lessons, http://localhost:8000
    python scripts/test_lessons.py otel-core/counters    # just one
    LAB_URL=http://lab.example python scripts/test_lessons.py
    LAB_USER=ci LAB_PASSWORD=... python scripts/test_lessons.py   # labs with accounts
"""

from __future__ import annotations

import json
import os
import sys
import time
import http.cookiejar
import urllib.request

LAB = os.getenv("LAB_URL", "http://localhost:8000").rstrip("/")
OPENER = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def call(path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(LAB + path, data=json.dumps(body).encode() if body is not None else None, headers={"content-type": "application/json"}, method="POST" if body is not None else "GET")
    with OPENER.open(req, timeout=60) as r:
        return json.load(r)


def run(lesson: str, code: str) -> dict:
    run = call("/api/runs", {"lesson": lesson, "code": code})
    deadline = time.time() + 60
    while time.time() < deadline:
        time.sleep(1)
        snap = call(f"/api/runs/{run['id']}")
        if snap["status"] in ("done", "error"):
            return snap
    raise TimeoutError(lesson)


def main() -> int:
    wanted = set(sys.argv[1:])
    if os.getenv("LAB_USER"):
        call("/api/auth/login", {"username": os.environ["LAB_USER"], "password": os.environ.get("LAB_PASSWORD", "")})
    course = call("/api/course")
    failures = 0
    for pack in course:
        for module in pack["modules"]:
            for outline in module["lessons"]:
                lid = outline["id"]
                if wanted and lid not in wanted and pack["id"] not in wanted:
                    continue
                lesson = call(f"/api/lessons/{lid}")
                kind = lesson["kind"]
                if kind in ("code", "collector"):
                    if not lesson.get("solution"):
                        print(f"SKIP {lid}: no solution")
                        continue
                    sol = run(lid, lesson["solution"]["content"])
                    bad = [c for c in sol["checks"] if c["status"] != "pass"]
                    starter = run(lid, lesson["starter"]["content"]) if lesson.get("starter") else None
                    starter_fails = [c for c in (starter or {}).get("checks", []) if c["status"] != "pass"]
                    ok = not bad and (starter is None or starter_fails)
                    failures += not ok
                    print(f"{'PASS' if ok else 'FAIL'} {lid}")
                    for c in bad:
                        print(f"     solution ✗ {c['title']}: {c['detail']}")
                        if c["detail"].startswith("No") or "exit" in c["type"]:
                            print("       output:", " | ".join(o["text"] for o in sol["output"][-6:]))
                    if starter is not None and not starter_fails:
                        print("     starter passes every check; the exercise has nothing to do")
                    for c in starter_fails[:2]:
                        print(f"     starter  ✗ {c['title']}: {c['detail']}")
                elif kind == "query" and lesson.get("solution"):
                    q = lesson["query"]
                    try:
                        res = call("/api/query", {"backend": q["backend"], "language": q["language"], "query": lesson["solution"]["content"], "lesson": lid})
                    except Exception as e:  # backend not enabled
                        print(f"SKIP {lid}: {e}")
                        continue
                    bad = [c for c in res["checks"] if c["status"] != "pass"]
                    err = res["result"].get("error")
                    failures += bool(bad or err)
                    print(f"{'FAIL' if bad or err else 'PASS'} {lid}" + (f": {err}" if err else ""))
                    for c in bad:
                        print(f"     ✗ {c['title']}: {c['detail']}")
                else:
                    print(f"  -  {lid} ({kind})")
    print(f"\n{failures} failing lesson(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
