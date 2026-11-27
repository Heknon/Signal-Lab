"""Shared helpers for the course-builder tools. Standard library only (Python 3.9+)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

PLACEHOLDER = re.compile(r"\{\{.*?\}\}")
BACKTICK = re.compile(r"`([^`]+)`")
# Citations with these prefixes are not repo paths and are not checked on disk.
NON_PATH_PREFIXES = ("metric:", "cmd:", "key:", "api:", "doc:", "url:", "http://", "https://")


class Report:
    """Collects errors and warnings and prints them in one consistent format."""

    def __init__(self, tool: str) -> None:
        self.tool = tool
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, where: str, msg: str) -> None:
        self.errors.append(f"{where}: {msg}")

    def warn(self, where: str, msg: str) -> None:
        self.warnings.append(f"{where}: {msg}")

    def finish(self, summary: str = "") -> int:
        for w in self.warnings:
            print(f"warning  {w}")
        for e in self.errors:
            print(f"error    {e}")
        status = "FAIL" if self.errors else "PASS"
        tail = f" ({summary})" if summary else ""
        print(f"{self.tool}: {status}, {len(self.errors)} errors, {len(self.warnings)} warnings{tail}")
        return 1 if self.errors else 0


# ---------------------------------------------------------------- Markdown


def sections(text: str, level: int = 2) -> dict[str, str]:
    """Map each heading of the given level to the text under it (until the next heading of that level or higher)."""
    out: dict[str, str] = {}
    current = None
    buf: list[str] = []
    in_code = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_code = not in_code
        m = None if in_code else re.match(r"^(#{1,6})\s+(.*?)\s*$", line)
        if m and len(m.group(1)) <= level:
            if current is not None:
                out[current] = "\n".join(buf).strip()
            current = m.group(2) if len(m.group(1)) == level else None
            buf = []
        elif current is not None:
            buf.append(line)
    if current is not None:
        out[current] = "\n".join(buf).strip()
    return out


def tables(text: str) -> list[list[dict[str, str]]]:
    """Every pipe table in the text, as a list of rows keyed by lower-cased header."""
    result: list[list[dict[str, str]]] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines) - 1:
        if lines[i].strip().startswith("|") and re.match(r"^\s*\|?\s*:?-{3,}", lines[i + 1]):
            header = [c.strip().lower() for c in _cells(lines[i])]
            rows = []
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = _cells(lines[i])
                cells += [""] * (len(header) - len(cells))
                rows.append(dict(zip(header, cells)))
                i += 1
            result.append(rows)
        else:
            i += 1
    return result


def _cells(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    # split on pipes that are not escaped and not inside backticks
    cells, buf, tick = [], [], False
    j = 0
    while j < len(line):
        ch = line[j]
        if ch == "\\" and j + 1 < len(line) and line[j + 1] == "|":
            buf.append("|")
            j += 2
            continue
        if ch == "`":
            tick = not tick
        if ch == "|" and not tick:
            cells.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
        j += 1
    cells.append("".join(buf).strip())
    return cells


def column(row: dict[str, str], *names: str) -> str:
    """The first cell whose header starts with any of the given names."""
    for key, value in row.items():
        if any(key.startswith(n) for n in names):
            return value
    return ""


def split_list(cell: str) -> list[str]:
    cell = cell.replace("`", "")
    return [p.strip() for p in re.split(r"[,;]", cell) if p.strip()]


# ---------------------------------------------------------------- front matter


def front_matter(text: str) -> tuple[dict[str, Any] | None, str]:
    """Parse YAML front matter. Uses PyYAML when installed, otherwise a small parser
    that understands top-level keys, scalars, inline lists and block lists."""
    m = re.match(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", text, re.S)
    if not m:
        return None, text
    raw, body = m.group(1), text[m.end():]
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(raw) or {}
        return (data if isinstance(data, dict) else None), body
    except ImportError:
        return _mini_yaml(raw), body
    except Exception:  # invalid YAML
        return None, body


def _mini_yaml(raw: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    key = None
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        top = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if top:
            key, value = top.group(1), top.group(2).strip()
            data[key] = _scalar(value) if value else []
            continue
        if key is None:
            continue
        item = re.match(r"^\s+-\s*(.*)$", line)
        if isinstance(data[key], list) and item and _indent(line) == _first_indent(raw, key):
            data[key].append(_scalar(item.group(1)) if ":" not in item.group(1) else {"_raw": item.group(1)})
        elif data[key] == []:
            data[key] = {"_raw": line.strip()}  # nested mapping
    return data


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def _first_indent(raw: str, key: str) -> int:
    lines = raw.splitlines()
    for i, line in enumerate(lines):
        if re.match(rf"^{re.escape(key)}:", line):
            for nxt in lines[i + 1:]:
                if nxt.strip():
                    return _indent(nxt)
    return 2


def _scalar(value: str) -> Any:
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        return [_scalar(v) for v in _split_inline(inner)] if inner else []
    if value.startswith("{"):
        return {"_raw": value}
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if value in ("true", "false"):
        return value == "true"
    return value


def _split_inline(inner: str) -> list[str]:
    parts, buf, depth, quote = [], [], 0, None
    for ch in inner:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
        elif ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    if "".join(buf).strip():
        parts.append("".join(buf).strip())
    return parts


def lesson_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("lesson.md") if "templates" not in p.parts)


def is_path_citation(citation: str) -> bool:
    return not citation.lower().startswith(NON_PATH_PREFIXES)
