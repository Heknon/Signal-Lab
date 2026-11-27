"""Check engine: grade a lesson against the telemetry a run produced.

Checks are declared in lesson front matter. They describe *what the telemetry
should look like*, never which backend it lives in, so the same lesson works
whatever backends are enabled. Each failing check explains what it saw, so
the learner gets a nudge rather than a red cross.
"""

from __future__ import annotations

import difflib
import re
from collections import defaultdict
from typing import Any, Callable

PASS, FAIL, PENDING = "pass", "fail", "pending"


def result(check: dict, status: str, detail: str = "") -> dict:
    return {"id": check["id"], "title": check.get("title", check["id"]), "type": check["type"], "status": status, "detail": detail}


def _fmt_list(items: list[str], limit: int = 6) -> str:
    items = list(dict.fromkeys(items))
    shown = ", ".join(f"`{i}`" for i in items[:limit])
    return shown + (f" and {len(items) - limit} more" if len(items) > limit else "")


def _closest(name: str, options: list[str]) -> str:
    match = difflib.get_close_matches(name, options, n=1, cutoff=0.5)
    return f" Did you mean `{match[0]}`?" if match else ""


def _value_matches(actual: Any, expected: Any) -> bool:
    if expected == "*":
        return actual is not None
    if isinstance(expected, dict):
        try:
            a = float(actual)
        except (TypeError, ValueError):
            return False
        return all(
            {"gt": a > v, "gte": a >= v, "lt": a < v, "lte": a <= v}.get(op, True) for op, v in expected.items()
        )
    if isinstance(expected, bool) or isinstance(actual, bool):
        return str(actual).lower() == str(expected).lower()
    if isinstance(expected, str) and expected.startswith("~"):
        return re.search(expected[1:], str(actual)) is not None
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return float(actual) == float(expected)
    return str(actual) == str(expected)


def _count_ok(n: int, spec: dict | int | None, default_min: int = 1) -> tuple[bool, str]:
    if spec is None:
        spec = {"min": default_min}
    if isinstance(spec, int):
        spec = {"min": spec, "max": spec}
    lo, hi = spec.get("min", 0), spec.get("max")
    if n < lo:
        return False, f"at least {lo}"
    if hi is not None and n > hi:
        return False, f"at most {hi}"
    return True, ""


# ------------------------------------------------------------------ spans


def _span_matches(span: dict, where: dict, spans_by_id: dict[str, dict]) -> tuple[bool, str]:
    """Return (matches, reason-it-didn't) for one span."""
    if "name" in where and not _value_matches(span["name"], where["name"]):
        return False, "name"
    if "service" in where and span["service"] != where["service"]:
        return False, "service"
    if "kind" in where and span["kind"] != where["kind"]:
        return False, f"kind is `{span['kind']}`, expected `{where['kind']}`"
    if "status" in where and span["status"]["code"] != where["status"]:
        return False, f"status is `{span['status']['code']}`, expected `{where['status']}`"
    for key, expected in (where.get("attributes") or {}).items():
        if key not in span["attributes"]:
            have = list(span["attributes"].keys())
            hint = _closest(key, have)
            return False, f"missing attribute `{key}`." + (hint or (f" It has {_fmt_list(have)}." if have else " It has no attributes."))
        if not _value_matches(span["attributes"][key], expected):
            return False, f"attribute `{key}` is `{span['attributes'][key]}`, expected `{expected}`"
    for key in where.get("attributes_absent") or []:
        if key in span["attributes"]:
            return False, f"attribute `{key}` should not be set"
    parent = where.get("parent")
    if parent == "root" and span["parent_span_id"]:
        return False, "it has a parent, expected a root span"
    if parent and parent not in ("root", "any"):
        p = spans_by_id.get(span["parent_span_id"] or "")
        if parent == "child" and not span["parent_span_id"]:
            return False, "it is a root span; expected it to have a parent"
        if parent not in ("child",) and (not p or not _value_matches(p["name"], parent)):
            if not span["parent_span_id"]:
                return False, f"it has no parent; expected it to be a child of `{parent}`"
            got = f"`{p['name']}`" if p else "a span that wasn't exported"
            return False, f"its parent is {got}, expected `{parent}`"
    for ev in where.get("events") or []:
        names = [e["name"] for e in span["events"]]
        if ev not in names:
            return False, f"no event `{ev}`" + (f" (events: {_fmt_list(names)})" if names else " (it has no events)")
    if "links" in where:
        ok, need = _count_ok(len(span["links"]), where["links"])
        if not ok:
            return False, f"it has {len(span['links'])} link(s), expected {need}"
    if "exception" in where:
        has = any(e["name"] == "exception" for e in span["events"])
        if bool(where["exception"]) != has:
            return False, "no exception was recorded on it" if where["exception"] else "an exception was recorded"
    if "min_duration_ms" in where and span["duration_ms"] < where["min_duration_ms"]:
        return False, f"it took {span['duration_ms']:.1f} ms, expected at least {where['min_duration_ms']} ms"
    return True, ""


def check_span(check: dict, t: dict, ctx: dict) -> dict:
    spans = t["spans"]
    where = check.get("where", {})
    by_id = {s["span_id"]: s for s in spans}
    matched, near = [], []
    for s in spans:
        ok, why = _span_matches(s, where, by_id)
        if ok:
            matched.append(s)
        elif why != "name" and why != "service":
            near.append((s, why))
    ok, need = _count_ok(len(matched), check.get("count"))
    if ok:
        return result(check, PASS, f"Found {len(matched)} matching span{'s' if len(matched) != 1 else ''}.")
    if not spans:
        return result(check, PENDING if ctx.get("collecting") else FAIL, "No spans have arrived yet." if ctx.get("collecting") else "No spans were exported.")
    if near and not matched:
        s, why = near[0]
        return result(check, FAIL, f"Span `{s['name']}` is close, but {why}")
    if "name" in where and not matched:
        names = [s["name"] for s in spans]
        return result(check, FAIL, f"No span named `{where['name']}`.{_closest(str(where['name']), names)} Spans seen: {_fmt_list(names)}.")
    return result(check, FAIL, f"Found {len(matched)} matching span(s), expected {need}.")


def check_trace(check: dict, t: dict, ctx: dict) -> dict:
    traces: dict[str, list[dict]] = defaultdict(list)
    for s in t["spans"]:
        traces[s["trace_id"]].append(s)
    if not traces:
        return result(check, PENDING if ctx.get("collecting") else FAIL, "No traces yet.")
    best: tuple[int, str] = (-1, "")
    for tid, spans in traces.items():
        services = {s["service"] for s in spans}
        by_id = {s["span_id"]: s for s in spans}

        def depth(s: dict) -> int:
            d, seen = 1, set()
            while s["parent_span_id"] and s["parent_span_id"] in by_id and s["span_id"] not in seen:
                seen.add(s["span_id"])
                s = by_id[s["parent_span_id"]]
                d += 1
            return d

        max_depth = max(depth(s) for s in spans)
        roots = [s for s in spans if not s["parent_span_id"] or s["parent_span_id"] not in by_id]
        problems = []
        for key, value in (("services", len(services)), ("spans", len(spans)), ("depth", max_depth), ("roots", len(roots))):
            if key in check:
                ok, need = _count_ok(value, check[key])
                if not ok:
                    problems.append(f"{value} {key} (expected {need})")
        for svc in check.get("includes_services", []):
            if svc not in services:
                problems.append(f"no spans from `{svc}`")
        if not problems:
            return result(check, PASS, f"Trace spans {len(services)} service(s): {_fmt_list(sorted(services))}.")
        score = len(services) * 10 + len(spans)
        if score > best[0]:
            best = (score, "; ".join(problems))
    n = len(traces)
    prefix = f"{n} traces were produced. " if n > 1 else ""
    if n > 1 and check.get("services"):
        prefix += "Context may not be propagating: spans that should share one trace ended up in separate traces. "
    return result(check, PENDING if ctx.get("collecting") else FAIL, f"{prefix}Best trace has {best[1]}.")


# ---------------------------------------------------------------- metrics


def check_metric(check: dict, t: dict, ctx: dict) -> dict:
    metrics = {m["name"]: m for m in t["metrics"]}
    name = check["name"]
    m = metrics.get(name)
    if m is None:
        pend = PENDING if ctx.get("collecting") else FAIL
        if not metrics:
            return result(check, pend, "No metrics have been exported yet." if ctx.get("collecting") else "No metrics were exported. Did the program record a measurement?")
        return result(check, pend, f"No metric named `{name}`.{_closest(name, list(metrics))} Metrics seen: {_fmt_list(list(metrics))}.")
    inst = check.get("instrument")
    if inst and m["instrument"] != inst:
        return result(check, FAIL, f"`{name}` is a {m['instrument']}, expected a {inst}.")
    if "unit" in check and m["unit"] != check["unit"]:
        return result(check, FAIL, f"`{name}` has unit `{m['unit'] or '(none)'}`, expected `{check['unit']}`.")
    series = m["series"]
    if check.get("attributes"):
        missing = [k for k in check["attributes"] if not any(k in s["attributes"] for s in series)]
        if missing:
            have = sorted({k for s in series for k in s["attributes"]})
            return result(check, FAIL, f"`{name}` has no attribute {_fmt_list(missing)}." + (f" Attributes seen: {_fmt_list(have)}." if have else " It has no attributes."))
    for key in check.get("attributes_absent", []):
        if any(key in s["attributes"] for s in series):
            return result(check, FAIL, f"`{name}` still has attribute `{key}`. {check.get('absent_hint', '')}".strip())
    if "series" in check:
        ok, need = _count_ok(len(series), check["series"])
        if not ok:
            hint = check.get("series_hint", "")
            return result(check, FAIL, f"`{name}` has {len(series)} time series, expected {need}. {hint}".strip())
    if "value" in check:
        total = sum(float(s.get("value") or s.get("count") or 0) for s in series)
        if not _value_matches(total, check["value"]):
            return result(check, PENDING if ctx.get("collecting") else FAIL, f"`{name}` totals {total:g}; expected {check['value']}.")
    if "bounds" in check:
        bounds = series[0].get("bounds") if series else None
        if bounds is None:
            return result(check, FAIL, f"`{name}` has no explicit bucket boundaries.")
        if [float(b) for b in bounds] != [float(b) for b in check["bounds"]]:
            return result(check, FAIL, f"`{name}` uses buckets {bounds}; expected {check['bounds']}.")
    if check.get("exemplars"):
        if not any(s.get("exemplars") for s in series):
            return result(check, FAIL, f"`{name}` has no exemplars. Record measurements inside an active span.")
    return result(check, PASS, f"`{name}`: {m['instrument']}, {len(series)} series.")


# ------------------------------------------------------------------- logs


def check_log(check: dict, t: dict, ctx: dict) -> dict:
    logs = t["logs"]
    matched = []
    for r in logs:
        body = str(r["body"])
        if "body" in check and not _value_matches(body, check["body"]):
            continue
        if "body_contains" in check and check["body_contains"].lower() not in body.lower():
            continue
        if "severity" in check and r["severity_text"].upper() != check["severity"].upper():
            continue
        if check.get("correlated") and not (r["trace_id"] and r["span_id"]):
            continue
        if any(k not in r["attributes"] or not _value_matches(r["attributes"][k], v) for k, v in (check.get("attributes") or {}).items()):
            continue
        matched.append(r)
    ok, need = _count_ok(len(matched), check.get("count"))
    if ok:
        return result(check, PASS, f"Found {len(matched)} matching log record(s).")
    if not logs:
        return result(check, PENDING if ctx.get("collecting") else FAIL, "No log records were exported." if not ctx.get("collecting") else "No logs yet.")
    if check.get("correlated") and not any(r["trace_id"] for r in logs):
        return result(check, FAIL, "Logs arrived, but none carry a trace id. Log inside an active span.")
    return result(check, FAIL, f"{len(logs)} log record(s) exported, {len(matched)} matching (expected {need}).")


# ----------------------------------------------------------------- output


def check_output(check: dict, t: dict, ctx: dict) -> dict:
    text = "\n".join(line["text"] for line in ctx.get("output", []) if line.get("stream") == "stdout")
    if "contains" in check and check["contains"] not in text:
        return result(check, FAIL, f"Output doesn't contain `{check['contains']}`.")
    if "regex" in check and not re.search(check["regex"], text, re.M):
        return result(check, FAIL, "Output didn't match the expected pattern.")
    return result(check, PASS, "Output looks right.")


def check_exit(check: dict, t: dict, ctx: dict) -> dict:
    code = ctx.get("exit_code")
    if code is None:
        return result(check, PENDING, "Still running.")
    return result(check, PASS if code == 0 else FAIL, "Program finished cleanly." if code == 0 else f"Program exited with code {code}.")


CHECKS: dict[str, Callable[[dict, dict, dict], dict]] = {
    "span": check_span,
    "trace": check_trace,
    "metric": check_metric,
    "log": check_log,
    "output": check_output,
    "exit": check_exit,
}

# Check types evaluated elsewhere (backend queries, quiz answers, adapter verifications).
DEFERRED = {"query", "answer", "backend"}


def evaluate(checks: list[dict], telemetry: dict, ctx: dict) -> list[dict]:
    out = []
    for c in checks:
        fn = CHECKS.get(c["type"])
        if fn is None:
            if c["type"] not in DEFERRED:
                out.append(result(c, FAIL, f"Unknown check type `{c['type']}`."))
            continue
        try:
            out.append(fn(c, telemetry, ctx))
        except Exception as e:  # a bad check definition shouldn't crash a run
            out.append(result(c, FAIL, f"Check error: {e}"))
    return out


def register(name: str):
    """Decorator for plugins that add check types."""

    def deco(fn: Callable[[dict, dict, dict], dict]):
        CHECKS[name] = fn
        return fn

    return deco
