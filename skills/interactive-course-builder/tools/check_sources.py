#!/usr/bin/env python3
"""Check that every cited artifact exists in the target repository.

Reads citations from:
  - lesson front matter `sources:` (any lesson.md under a folder)
  - backticked cells in "Artifacts" / "Sources" columns of Markdown tables (concept-map.md, outline.md)

Citation forms:
  path                 the file or directory must exist
  path#Symbol          the file must define Symbol: a def/class/assignment in code, a key in YAML/JSON/TOML,
                       a heading or the text itself in other files. Class.method needs both.
  path:120             the file must have at least 120 lines
  metric:/cmd:/key:/api:/doc:/url:   not a file; counted, not checked

Usage:
    python tools/check_sources.py --repo ../target course/concept-map.md course/outline.md plugins/lessons
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import BACKTICK, Report, front_matter, is_path_citation, lesson_files, tables  # noqa: E402


def citations_from_markdown(path: Path) -> list[tuple[str, str]]:
    out = []
    for table in tables(path.read_text(encoding="utf-8")):
        for row in table:
            for header, cell in row.items():
                if header in ("artifacts", "sources"):  # not "source" (e.g. the Observable surface table)
                    out += [(f"{path}", c.strip()) for c in BACKTICK.findall(cell)]
    return out


def citations_from_lessons(root: Path) -> list[tuple[str, str]]:
    out = []
    for f in lesson_files(root):
        fm, _ = front_matter(f.read_text(encoding="utf-8"))
        sources = (fm or {}).get("sources") or []
        if isinstance(sources, str):
            sources = [sources]
        out += [(str(f.parent.relative_to(root)), str(s)) for s in sources]
    return out


def check(repo: Path, where: str, citation: str, rep: Report) -> bool:
    m = re.match(r"^(.*?)(?:#(.+)|:(\d+)(?:-\d+)?)?$", citation)
    rel, symbol, line = m.group(1), m.group(2), m.group(3)
    target = (repo / rel).resolve()
    if repo.resolve() not in target.parents and target != repo.resolve():
        rep.error(where, f"`{citation}` points outside the repository")
        return False
    if not target.exists():
        hint = _nearest(repo, rel)
        rep.error(where, f"`{citation}` not found in {repo}" + (f"; did you mean `{hint}`?" if hint else ""))
        return False
    if target.is_dir():
        rep.warn(where, f"`{citation}` is a directory; cite the file or key the concept lives in")
        return True
    if symbol:
        text = target.read_text(encoding="utf-8", errors="replace")
        missing = [part for part in re.split(r"[.:]", symbol) if part and not defines(target.suffix, text, part)]
        if missing:
            rep.error(where, f"`{citation}`: {rel} does not define '{missing[-1]}'"
                      + (" (it is only used there, not defined)" if missing[-1] in text else ""))
            return False
    if line:
        n = sum(1 for _ in target.open(encoding="utf-8", errors="replace"))
        if int(line) > n:
            rep.error(where, f"`{citation}`: {rel} has only {n} lines")
            return False
    return True


CODE = {".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rb", ".java", ".kt", ".rs", ".c", ".h", ".cpp", ".cs", ".php", ".sh"}
CONFIG = {".yaml", ".yml", ".json", ".toml", ".ini", ".cfg", ".conf", ".env", ".properties"}


def defines(suffix: str, text: str, name: str) -> bool:
    """True if the file defines `name` (not merely uses it)."""
    n = re.escape(name)
    if suffix in CODE:
        patterns = [
            rf"^\s*(async\s+)?(def|class|func|fn|function|interface|type|struct|enum|const|let|var)\s+{n}\b",
            rf"^\s*(export\s+)?(default\s+)?(async\s+)?(function|class|const|let|var|type|interface)\s+{n}\b",
            # assignment or annotated field; a line ending in "," is a function parameter, not a definition
            rf"^\s*(self\.|this\.)?{n}\s*(:[^=\n]+)?=(?!=)(?![^\n]*,\s*$)",
            rf"^\s*{n}\s*:(?![^\n]*,\s*$)",
            rf"\bfunc\s+\([^)]*\)\s+{n}\b",                     # Go method
            rf"^\s*(public|private|protected|static|\w+)\s.*\b{n}\s*\(",  # Java/C#-style method
        ]
    elif suffix in CONFIG:
        patterns = [rf"^\s*-?\s*[\"']?{n}[\"']?\s*[:=]", rf"^\s*\[{n}\]"]
    else:
        return name in text
    return any(re.search(p, text, re.M) for p in patterns)


def _nearest(repo: Path, rel: str) -> str:
    name = Path(rel).name
    if not name:
        return ""
    for p in repo.rglob(name):
        if ".git" not in p.parts and "node_modules" not in p.parts:
            return str(p.relative_to(repo))
    return ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", type=Path, required=True, help="root of the target system's repository")
    ap.add_argument("inputs", nargs="+", type=Path, help="artifact .md files and/or lesson folders")
    args = ap.parse_args()
    rep = Report("check_sources")
    cites: list[tuple[str, str]] = []
    for p in args.inputs:
        cites += citations_from_lessons(p) if p.is_dir() else citations_from_markdown(p)
    checked = skipped = 0
    for where, c in cites:
        if is_path_citation(c):
            check(args.repo, where, c, rep)
            checked += 1
        else:
            skipped += 1
    if not cites:
        rep.error(" ".join(map(str, args.inputs)), "no citations found")
    return rep.finish(f"{checked} paths checked, {skipped} non-file citations")


if __name__ == "__main__":
    sys.exit(main())
