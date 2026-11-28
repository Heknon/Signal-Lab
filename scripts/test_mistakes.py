#!/usr/bin/env python3
"""Grade known learner mistakes (must fail) and valid alternatives (must pass).

A lesson whose goals pass a realistic wrong answer teaches nothing: the learner
sees green and moves on. These cases came from auditing every gradable lesson.

  python3 scripts/test_mistakes.py            # all
  python3 scripts/test_mistakes.py histograms  # only files/lessons matching

Needs a running lab (default http://localhost:8000, or SIGNAL_LAB_URL).
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from pathlib import Path

import yaml

BASE = os.getenv("SIGNAL_LAB_URL", "http://localhost:8000")
HERE = Path(__file__).parent / "mistakes"
# Code files that are valid alternatives and must PASS (everything else must fail).
ALTERNATIVES = {
    "otel-core__errors-status__okOthers.py",      # Status(OK) on successes is allowed
    "otel-core__views__otherBuckets.py",           # any buckets that fit the data
    "otel-core__span-links__addLinkLater.py",      # add_link after start is allowed by the spec
    "otel-core__span-links__lastOnly.py",          # collecting the context after the block is the same
    "otel-core__sampling__noParentBased.py",       # single process: trace-id ratio agrees with itself
    "collector__transform-ottl__nsOnSpan.yaml",    # resource.attributes from span context is valid OTTL
    "otel-core__histograms__extraBoundary.py",     # an extra boundary on the tail is fine
}


def post(path: str, body: dict) -> dict:
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), headers={"content-type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=60))


def grade_code(lesson: str, code: str) -> list[dict]:
    run = post("/api/runs", {"lesson": lesson, "code": code})
    for _ in range(120):
        r = json.load(urllib.request.urlopen(f"{BASE}/api/runs/{run['id']}"))
        if r["status"] in ("done", "error"):
            return r["checks"]
        time.sleep(0.5)
    raise TimeoutError(lesson)


def grade_query(lesson: str, query: str) -> list[dict]:
    backend = "victorialogs" if lesson.startswith("logs") else "victoriametrics"
    lang = "logsql" if backend == "victorialogs" else "metricsql"
    return post("/api/query", {"backend": backend, "language": lang, "query": query, "lesson": lesson, "range_s": 900})["checks"]


def main() -> int:
    wanted = sys.argv[1:]
    cases = []
    for f in sorted(HERE.iterdir()):
        if "__" not in f.name or f.suffix not in (".py", ".yaml"):
            continue
        track, lesson, _ = f.name.split("__", 2)
        cases.append((f"{track}/{lesson}", f.name, "pass" if f.name in ALTERNATIVES else "fail", lambda l=f"{track}/{lesson}", p=f: grade_code(l, p.read_text())))
    for i, q in enumerate(yaml.safe_load((HERE / "queries.yaml").read_text())):
        cases.append((q["lesson"], f"query {i}: {q['why']}", q["expect"], lambda q=q: grade_query(q["lesson"], q["query"])))
    bad = 0
    for lesson, name, want, grade in cases:
        if wanted and not any(w in lesson or w in name for w in wanted):
            continue
        checks = grade()
        got = "pass" if checks and all(c["status"] == "pass" for c in checks) else "fail"
        first = next((c for c in checks if c["status"] != "pass"), None)
        ok = got == want
        bad += not ok
        print(f"{'ok ' if ok else 'BAD'} {lesson:42} {name:58} {got} (want {want})" + (f"\n      {first['title']}: {first['detail'][:140]}" if first and not ok else ""))
    print(f"\n{bad} unexpected result(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
