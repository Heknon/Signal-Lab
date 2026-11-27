#!/usr/bin/env python3
"""Check that phase artifacts exist, have every required section, and are filled in.

Usage:
    python tools/lint_artifacts.py course/concept-map.md [course/outline.md ...]
    python tools/lint_artifacts.py course/          # every artifact present in the folder
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import PLACEHOLDER, Report, column, sections, split_list, tables  # noqa: E402

REQUIRED = {
    "concept-map.md": ["Subject", "Inventory", "Concepts", "Failure modes", "Observable surface", "Deliberate gaps"],
    "outline.md": ["Tracks", "Lessons", "Progression", "Capstone incidents", "Decisions"],
    "adapter.md": ["Learner outputs", "Execution", "Observable state", "Check types", "Scenario",
                   "Fault catalogue", "Isolation", "Spike"],
    "platform.md": ["Decision", "Start", "Content", "Lesson kinds", "Check types", "Runner isolation", "Smoke lesson"],
    "verification-report.md": ["Run", "Summary", "Lessons", "Incidents", "Failures found and fixed", "Not verified"],
    "ui-review.md": ["Coverage", "Rounds", "Final pass"],
}
KINDS = {"code", "config", "collector", "query", "quiz", "task", "experiment", "incident"}


def lint(path: Path, rep: Report) -> None:
    name = path.name
    if name not in REQUIRED:
        rep.error(str(path), f"unknown artifact; expected one of {', '.join(REQUIRED)}")
        return
    if not path.exists():
        rep.error(str(path), "missing")
        return
    text = path.read_text(encoding="utf-8")
    for m in PLACEHOLDER.finditer(text):
        line = text[: m.start()].count("\n") + 1
        rep.error(f"{path}:{line}", f"unfilled placeholder {m.group(0)}")
    secs = sections(text)
    for title in REQUIRED[name]:
        if title not in secs:
            rep.error(str(path), f'missing section "## {title}"')
        elif not secs[title].strip():
            rep.error(str(path), f'section "## {title}" is empty')
    check = CONTENT_CHECKS.get(name)
    if check:
        check(path, secs, rep)


def _rows(section_text: str) -> list[dict[str, str]]:
    return [row for table in tables(section_text) for row in table]


def concept_map(path: Path, secs: dict[str, str], rep: Report) -> None:
    rows = _rows(secs.get("Concepts", ""))
    if not rows:
        rep.error(str(path), "Concepts has no table rows")
        return
    high = 0
    seen = set()
    for row in rows:
        cid = column(row, "id")
        where = f"{path} concept {cid or '?'}"
        if not cid:
            rep.error(where, "row has no id")
        if cid in seen:
            rep.error(where, "duplicate id")
        seen.add(cid)
        try:
            scores = [int(column(row, k)) for k in ("freq", "blast", "confusion")]
            priority = int(column(row, "priority"))
        except ValueError:
            rep.error(where, "scores and priority must be integers")
            continue
        if any(not 1 <= s <= 5 for s in scores):
            rep.error(where, "scores must be 1-5")
        if priority != sum(scores):
            rep.error(where, f"priority {priority} != {sum(scores)} (freq + blast + confusion)")
        if priority >= 12:
            high += 1
        if "`" not in column(row, "artifacts"):
            rep.error(where, "no backticked artifact citation")
        if scores[2] >= 3 and not column(row, "confusion evidence").strip():
            rep.warn(where, "confusion >= 3 but no evidence given")
    if len(rows) < 10:
        rep.warn(str(path), f"only {len(rows)} concepts; a medium system usually has 25-80")
    if high > len(rows) / 4:
        rep.error(str(path), f"{high}/{len(rows)} concepts have priority >= 12; at most a quarter may. Spread the scores.")
    blast = {column(r, "id") for r in rows if column(r, "blast").isdigit() and int(column(r, "blast")) >= 3}
    covered = {column(r, "concept") for r in _rows(secs.get("Failure modes", ""))}
    for cid in sorted(blast - covered):
        rep.error(f"{path} concept {cid}", "blast >= 3 but no row in Failure modes")


def outline(path: Path, secs: dict[str, str], rep: Report) -> None:
    rows = _rows(secs.get("Lessons", ""))
    if not rows:
        rep.error(str(path), "Lessons has no table rows")
    ids = set()
    for row in rows:
        lid = column(row, "id")
        where = f"{path} lesson {lid or '?'}"
        if not re.fullmatch(r"[a-z0-9-]+/[a-z0-9-]+", lid):
            rep.error(where, "id must be track-id/lesson-slug")
        if lid in ids:
            rep.error(where, "duplicate id")
        ids.add(lid)
        kind = column(row, "kind").strip().lower()
        if kind not in KINDS:
            rep.error(where, f"kind '{kind}' not one of {sorted(KINDS)}")
        minutes = column(row, "min")
        if not minutes.isdigit() or not 3 <= int(minutes) <= 15:
            rep.error(where, "minutes must be 3-15")
        for col in ("concepts", "assumes", "checks observe"):
            if not column(row, col).strip():
                rep.error(where, f"empty {col}")
        if "`" not in column(row, "sources"):
            rep.error(where, "no backticked source citation")
    for mod, body in sections(secs.get("Lessons", ""), level=3).items():
        if "**Assumes:**" not in body:
            rep.error(f"{path} {mod}", "module has no **Assumes:** line")
    incidents = _rows(secs.get("Capstone incidents", ""))
    if len(incidents) < 4:
        rep.error(str(path), f"{len(incidents)} capstone incidents; need at least 4")
    for row in incidents:
        for col in ("symptom", "hidden fault", "misleading", "signals", "evidence"):
            if not column(row, col).strip():
                rep.error(f"{path} incident {column(row, 'id')}", f"empty {col}")


def adapter(path: Path, secs: dict[str, str], rep: Report) -> None:
    spike = secs.get("Spike", "")
    blocks = re.findall(r"```[^\n]*\n(.*?)```", spike, re.S)
    if len(blocks) < 2 or not all(b.strip() for b in blocks[:2]):
        rep.error(str(path), "Spike needs the command and its pasted output in code blocks")
    for row in _rows(secs.get("Fault catalogue", "")):
        for col in ("removed", "time limit", "evidence"):
            if not column(row, col).strip():
                rep.error(f"{path} fault {column(row, 'fault')}", f"empty {col}: faults must be reversible, time-boxed and observable")
    for row in _rows(secs.get("Observable state", "")):
        if not column(row, "attribution").strip():
            rep.error(f"{path} source {column(row, 'source')}", "no run attribution")


def verification(path: Path, secs: dict[str, str], rep: Report) -> None:
    for row in _rows(secs.get("Summary", "")):
        if re.search(r"\bFAIL\b", column(row, "result")):
            rep.error(f"{path} suite {column(row, 'suite')}", "result is FAIL")
    for row in _rows(secs.get("Lessons", "")) + _rows(secs.get("Incidents", "")):
        cells = " ".join(row.values())
        if re.search(r"\bFAIL\b(?! as expected)|\bFAILS\b(?! as expected)", cells):
            rep.error(f"{path} {column(row, 'lesson', 'incident')}", "unexpected failure")


def ui_review(path: Path, secs: dict[str, str], rep: Report) -> None:
    final = secs.get("Final pass", "")
    unticked = re.findall(r"^\s*- \[ \] (.*)$", final, re.M)
    for item in unticked:
        rep.error(f"{path} final pass", f"not ticked: {item}")
    if not re.search(r"^\s*- \[x\]", final, re.M | re.I):
        rep.error(f"{path} final pass", "no ticked checklist items")
    widths = set(re.findall(r"\b(390|768|1024|1280|1440)\b", secs.get("Coverage", "")))
    if len(widths) < 5:
        rep.error(f"{path} coverage", "must cover widths 390, 768, 1024, 1280 and 1440")


CONTENT_CHECKS = {
    "concept-map.md": concept_map,
    "outline.md": outline,
    "adapter.md": adapter,
    "verification-report.md": verification,
    "ui-review.md": ui_review,
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+", type=Path)
    args = ap.parse_args()
    rep = Report("lint_artifacts")
    files: list[Path] = []
    for p in args.paths:
        if p.is_dir():
            files += [p / n for n in REQUIRED if (p / n).exists()]
        else:
            files.append(p)
    for f in files:
        lint(f, rep)
    return rep.finish(f"{len(files)} artifacts")


if __name__ == "__main__":
    sys.exit(main())
