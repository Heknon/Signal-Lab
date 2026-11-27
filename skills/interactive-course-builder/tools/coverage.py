#!/usr/bin/env python3
"""Check that every concept is taught, or listed as a deliberate gap.

  - priority >= 9 concepts must be taught by at least one lesson
  - every other concept must be taught or appear in "Deliberate gaps"
  - lessons may only use concept ids that exist in the concept map
  - with --lessons: every outline lesson has a folder, and every folder is in the outline

Usage:
    python tools/coverage.py course/concept-map.md course/outline.md [--lessons plugins/lessons]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import Report, column, front_matter, lesson_files, sections, split_list, tables  # noqa: E402

MUST_TEACH = 9


def rows(text: str, section: str) -> list[dict[str, str]]:
    return [r for t in tables(sections(text).get(section, "")) for r in t]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("concept_map", type=Path)
    ap.add_argument("outline", type=Path)
    ap.add_argument("--lessons", type=Path, help="folder with the lesson folders (also reads their `concepts`)")
    args = ap.parse_args()
    rep = Report("coverage")

    cmap = args.concept_map.read_text(encoding="utf-8")
    concepts = {}
    for r in rows(cmap, "Concepts"):
        cid = column(r, "id").strip()
        if cid:
            p = column(r, "priority")
            concepts[cid] = int(p) if p.strip().isdigit() else 0
    gaps = {column(r, "concept").replace("`", "").strip() for r in rows(cmap, "Deliberate gaps")}

    taught: dict[str, list[str]] = {}
    outline_ids = set()
    for r in rows(args.outline.read_text(encoding="utf-8"), "Lessons"):
        lid = column(r, "id").strip()
        outline_ids.add(lid)
        for c in split_list(column(r, "concepts")):
            taught.setdefault(c, []).append(lid)

    if args.lessons:
        folders = {}
        for f in lesson_files(args.lessons):
            lid = f"{f.parent.parent.name}/{f.parent.name}"
            folders[lid] = f
            fm, _ = front_matter(f.read_text(encoding="utf-8"))
            for c in (fm or {}).get("concepts") or []:
                taught.setdefault(str(c), []).append(lid)
        for lid in sorted(outline_ids - set(folders)):
            rep.error(lid, "in the outline but has no lesson folder")
        for lid in sorted(set(folders) - outline_ids):
            rep.error(lid, "lesson folder is not in the outline (update the outline first)")

    for cid, priority in sorted(concepts.items(), key=lambda kv: -kv[1]):
        if cid in taught:
            continue
        if priority >= MUST_TEACH:
            rep.error(cid, f"priority {priority} but no lesson teaches it" + (" (listing it as a gap is not enough)" if cid in gaps else ""))
        elif cid not in gaps:
            rep.error(cid, f"priority {priority}: not taught and not in Deliberate gaps")
    for c in sorted(set(taught) - set(concepts)):
        rep.warn(c, f"used by {', '.join(sorted(set(taught[c])))} but not in the concept map")
    for g in sorted(gaps & set(taught)):
        rep.warn(g, "listed as a deliberate gap but a lesson teaches it")

    covered = sum(1 for c in concepts if c in taught)
    return rep.finish(f"{covered}/{len(concepts)} concepts taught, {len(gaps)} deliberate gaps")


if __name__ == "__main__":
    sys.exit(main())
