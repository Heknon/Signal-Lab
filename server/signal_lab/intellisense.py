"""Editor intelligence for learner code: completions, signature help and hover docs.

Static analysis with Jedi against the packages installed in this image, which are
the same pinned OpenTelemetry packages the runner executes with. Nothing is run
and nothing is fetched, so it works air-gapped. Jedi isn't thread-safe, so every
request goes through one worker thread.
"""

from __future__ import annotations

import asyncio
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any

log = logging.getLogger(__name__)
MAX_CODE = 200_000
MAX_ITEMS = 80
_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="intellisense")

try:
    import jedi
except ImportError:  # optional: the editor simply has no server completions
    jedi = None

_KIND = {"module": "namespace", "class": "class", "instance": "variable", "function": "function", "param": "variable",
         "path": "text", "keyword": "keyword", "property": "property", "statement": "variable"}


def available() -> bool:
    return jedi is not None


def _position(code: str, offset: int) -> tuple[int, int]:
    """Character offset -> Jedi's (1-based line, 0-based column)."""
    offset = max(0, min(offset, len(code)))
    before = code[:offset]
    line = before.count("\n") + 1
    return line, offset - (before.rfind("\n") + 1)


def _reflow(text: str) -> str:
    """Undo the ~72-column hard wrapping of docstrings so a tooltip can wrap them itself.
    Lines that start a list item, a code example or an indented block stay as they are."""
    out = []
    for para in re.split(r"\n\s*\n", text):
        lines = para.split("\n")
        merged = [lines[0]]
        for line in lines[1:]:
            if re.match(r"\s|[-*•]\s|\d+[.)]\s|>>>|\.\.\.|:\w+", line) or merged[-1].rstrip().endswith(":"):
                merged.append(line)
            else:
                merged[-1] = merged[-1].rstrip() + " " + line.strip()
        out.append("\n".join(merged))
    return "\n\n".join(out)


def _doc(text: str, limit: int = 700) -> str:
    """First paragraphs of a docstring, reflowed and trimmed for a tooltip."""
    text = _reflow((text or "").strip())
    if len(text) > limit:
        cut = text.rfind("\n\n", 0, limit)
        text = text[: cut if cut > 200 else limit].rstrip() + " …"
    return text


def _no_self(signature: str) -> str:
    """Jedi shows methods reached through an annotated return type unbound; the
    learner calls them on an instance, so `self` isn't an argument they pass."""
    return signature.replace("(self, ", "(", 1).replace("(self)", "()", 1)


def _script(code: str):
    return jedi.Script(code, path="main.py")


def _complete(code: str, offset: int) -> dict:
    line, col = _position(code, offset)
    prefix = re.search(r"[A-Za-z_][A-Za-z0-9_]*$", code[:offset])
    typed = prefix.group(0) if prefix else ""
    items = []
    for c in _script(code).complete(line, col):
        if c.name.startswith("_") and not typed.startswith("_"):
            continue  # private and dunder names only when asked for
        sigs = c.get_signatures() if c.type in ("function", "class") else []
        items.append({
            "label": c.name,
            "type": _KIND.get(c.type, "text"),
            "detail": _no_self(sigs[0].to_string()) if sigs else (c.description if c.type not in ("keyword",) else ""),
            "doc": _doc(c.docstring(raw=True)) if len(items) < 25 else "",
        })
        if len(items) >= MAX_ITEMS:
            break
    return {"from": offset - len(typed), "items": items}


def _signatures(code: str, offset: int) -> dict | None:
    line, col = _position(code, offset)
    sigs = _script(code).get_signatures(line, col)
    if not sigs:
        return None
    s = sigs[0]
    params = [p.to_string() for p in s.params]
    if params and params[0] == "self":
        params = params[1:]  # Jedi's index already counts arguments without it
    return {
        "name": s.name,
        "params": params,
        "index": s.index,
        "returns": s.to_string().rsplit(")", 1)[-1].replace("->", "").strip(),
        "doc": _doc(s.docstring(raw=True), 500),
    }


def _hover(code: str, offset: int) -> dict | None:
    line, col = _position(code, offset)
    names = _script(code).help(line, col)
    if not names:
        return None
    n = names[0]
    if n.type == "keyword":
        return None
    sigs = n.get_signatures() if n.type in ("function", "class") else []
    head = _no_self(sigs[0].to_string()) if sigs else f"{n.name}: {n.description}"
    full = n.full_name or n.name
    return {"title": head, "where": full if full != n.name else "", "doc": _doc(n.docstring(raw=True))}


async def _run(fn, code: str, offset: int) -> Any:
    if jedi is None or len(code) > MAX_CODE:
        return None
    try:
        return await asyncio.get_running_loop().run_in_executor(_pool, fn, code, offset)
    except Exception as e:  # analysis must never break the editor
        log.debug("intellisense %s failed: %s", fn.__name__, e)
        return None


async def complete(code: str, offset: int) -> dict:
    return await _run(_complete, code, offset) or {"from": offset, "items": []}


async def signatures(code: str, offset: int) -> dict | None:
    return await _run(_signatures, code, offset)


async def hover(code: str, offset: int) -> dict | None:
    return await _run(_hover, code, offset)


async def warm_up() -> None:
    """Index the OpenTelemetry packages once, so the first keystroke is fast."""
    sample = ("from opentelemetry import trace, metrics, propagate\nfrom opentelemetry.trace import SpanKind\n"
              "from opentelemetry.sdk.trace import TracerProvider\n"
              "tracer = trace.get_tracer('x')\nwith tracer.start_as_current_span('x') as span:\n    span.")
    await complete(sample, len(sample))
    await complete("import logging\nlogging.", len("import logging\nlogging."))
