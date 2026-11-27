#!/usr/bin/env python3
"""Check every lesson folder: front matter, required files, checks, assumes, sources, prose.

Usage:
    python tools/lint_lessons.py plugins/lessons
    python tools/lint_lessons.py plugins/lessons --adapter course/adapter.md   # also validate check types
    python tools/lint_lessons.py plugins/lessons --skip sources   # e.g. for a course about a public technology
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import PLACEHOLDER, Report, column, front_matter, lesson_files, sections, tables  # noqa: E402

NEEDS_FILES = {"code", "config", "collector", "query"}      # starter.* and solution.*
NEEDS_CHECKS = {"code", "config", "collector", "query", "task"}
NEEDS_QUESTIONS = {"quiz", "incident", "experiment"}
NEEDS_HINTS = NEEDS_CHECKS | {"incident"}
KINDS = NEEDS_FILES | NEEDS_CHECKS | NEEDS_QUESTIONS
SLOP = [
    r"\bin this lesson,? (we|you) will\b", r"\bwelcome to\b", r"\blet's dive\b", r"\bdive (deep|into)\b",
    r"\bsupercharge\b", r"\bunlock\b", r"\bseamless(ly)?\b", r"\bjourney\b", r"\bgame[- ]changer\b",
    r"\bin today's\b",
]
GENERIC = [r"\bfoo\b", r"\bacme\b", r"\bjohn doe\b", r"\bexample\.com\b", r"\bmy[-_]service\b"]
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿⭐✅]")


def lint_lesson(path: Path, root: Path, skip: set[str], rep: Report, packed: set[str], types: set[str]) -> None:
    folder = path.parent
    where = str(folder.relative_to(root))
    text = path.read_text(encoding="utf-8")
    fm, body = front_matter(text)
    if fm is None:
        rep.error(where, "lesson.md has no valid front matter")
        return
    # {{...}} inside code is legitimate (e.g. a Grafana legend template); outside it is an unfilled template
    for m in PLACEHOLDER.finditer(re.sub(r"```.*?```|`[^`]*`", "", text, flags=re.S)):
        rep.error(where, f"unfilled placeholder {m.group(0)}")

    required = ["title", "summary", "kind", "minutes", "concepts", "assumes", "sources"]
    for key in required:
        if key in skip:
            continue
        if key not in fm:
            rep.error(where, f"front matter has no '{key}'")
        elif key not in ("assumes",) and fm[key] in (None, "", []):
            rep.error(where, f"'{key}' is empty")

    kind = str(fm.get("kind", "code"))
    if kind not in KINDS:
        rep.error(where, f"kind '{kind}' not one of {sorted(KINDS)}")
    title = str(fm.get("title", ""))
    if re.search(r"\b[A-Z][a-z]+ [A-Z][a-z]+ [A-Z][a-z]+", title) and title.istitle():
        rep.warn(where, f"title looks like Title Case: '{title}' (use sentence case)")
    minutes = fm.get("minutes")
    if isinstance(minutes, int) and not 2 <= minutes <= 20:
        rep.warn(where, f"minutes {minutes} is outside 2-20")

    if kind in NEEDS_CHECKS and "checks" not in skip:
        checks = fm.get("checks") or []
        if not checks:
            rep.error(where, f"a {kind} lesson needs checks")
        for c in checks if isinstance(checks, list) else []:
            if isinstance(c, dict) and "_raw" not in c and not c.get("title"):
                rep.error(where, f"check {c.get('id', '?')} has no title")
    if kind in NEEDS_QUESTIONS:
        quiz = fm.get("quiz")
        has_questions = isinstance(quiz, dict) and (quiz.get("questions") or "_raw" in quiz)
        if not has_questions:
            where_q = " (found top-level `questions:`; move it under `quiz:`)" if "questions" in fm else ""
            rep.error(where, f"a {kind} lesson needs `quiz: {{questions: [...]}}`{where_q}")
        if kind in ("incident", "experiment") and not fm.get(kind):
            rep.error(where, f"an {kind} lesson needs an `{kind}:` block")
    if types:
        fm_raw = text.split("\n---", 1)[0]
        checks_raw = fm_raw.split("\nchecks:", 1)[1] if "\nchecks:" in fm_raw else ""
        checks_raw = re.split(r"\n[A-Za-z_]", checks_raw, maxsplit=1)[0]
        for t in re.findall(r"^\s*(?:-\s+)?type:\s*[\"']?([\w.-]+)", checks_raw, re.M):
            if t not in types:
                rep.error(where, f"check type '{t}' is not defined in adapter.md Check types ({', '.join(sorted(types))})")
    if kind in NEEDS_HINTS and "hints" not in skip and not fm.get("hints"):
        rep.error(where, "no hints")

    if kind in NEEDS_FILES:
        starters = sorted(folder.glob("starter.*"))
        solutions = sorted(folder.glob("solution.*"))
        if not starters:
            rep.error(where, "no starter.* file")
        if not solutions:
            rep.error(where, "no solution.* file")
        if starters and solutions:
            s, sol = starters[0].read_text(encoding="utf-8"), solutions[0].read_text(encoding="utf-8")
            if s.strip() == sol.strip():
                rep.error(where, "starter is identical to solution")
            if kind in {"code", "config", "collector"} and "TODO" not in s:
                rep.warn(where, "starter has no TODO marking where to work")
            if starters[0].suffix == ".py":
                try:
                    compile(s, str(starters[0]), "exec")
                except SyntaxError as e:
                    rep.error(where, f"starter does not parse: {e.msg} (line {e.lineno})")
                try:
                    compile(sol, str(solutions[0]), "exec")
                except SyntaxError as e:
                    rep.error(where, f"solution does not parse: {e.msg} (line {e.lineno})")

    prose = re.sub(r"```.*?```", "", body, flags=re.S)
    if len(prose.split()) < 40:
        rep.warn(where, f"prose is very short ({len(prose.split())} words)")
    for pattern in SLOP:
        m = re.search(pattern, prose, re.I)
        if m:
            rep.error(where, f"slop phrase: '{m.group(0)}'")
    for pattern in GENERIC:
        m = re.search(pattern, text, re.I)
        if m:
            rep.warn(where, f"generic example name '{m.group(0)}'; use names from the target system")
    if EMOJI.search(text):
        rep.error(where, "emoji in lesson")
    callouts = len(re.findall(r"^> \[!(NOTE|TIP|WARNING|IMPORTANT|CAUTION)\]", body, re.M))
    if callouts > 1:
        rep.warn(where, f"{callouts} callouts; use at most one")
    if packed and folder.name not in packed:
        rep.warn(where, "not listed in any pack.yaml module")


def packed_lessons(root: Path) -> set[str]:
    names: set[str] = set()
    for pack in root.rglob("pack.yaml"):
        for m in re.finditer(r"lessons:\s*\[([^\]]*)\]", pack.read_text(encoding="utf-8")):
            names.update(x.strip() for x in m.group(1).split(",") if x.strip())
        for block in re.finditer(r"lessons:\s*\n((?:\s+-\s*\S+\n?)+)", pack.read_text(encoding="utf-8")):
            names.update(re.findall(r"-\s*(\S+)", block.group(1)))
    return names


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", type=Path, help="folder that contains the lesson folders")
    ap.add_argument("--skip", action="append", default=[], help="front-matter key not to require (repeatable)")
    ap.add_argument("--adapter", type=Path, help="course/adapter.md: check types must be listed in its Check types table")
    args = ap.parse_args()
    rep = Report("lint_lessons")
    types: set[str] = set()
    if args.adapter:
        body = sections(args.adapter.read_text(encoding="utf-8")).get("Check types", "")
        types = {column(r, "type").replace("`", "").strip() for t in tables(body) for r in t} - {""}
        if not types:
            rep.error(str(args.adapter), "no Check types table rows")
    files = lesson_files(args.root)
    if not files:
        rep.error(str(args.root), "no lesson.md files found")
    packed = packed_lessons(args.root)
    for f in files:
        lint_lesson(f, args.root, set(args.skip), rep, packed, types)
    return rep.finish(f"{len(files)} lessons")


if __name__ == "__main__":
    sys.exit(main())
