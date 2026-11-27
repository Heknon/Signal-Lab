"""VictoriaLogs adapter: LogsQL over the HTTP query API.

OTLP logs land with every resource and log attribute as a field under its
OpenTelemetry name: ``service.name``, ``signal_lab.run_id``,
``app.chaos.error_rate``. The body is ``_msg``, the timestamp ``_time``, and
the severity ``severity_text`` / ``severity_number``. Logs written inside a
span carry ``trace_id`` and ``span_id``.

Queries run over ``[at - range_s, at]`` via the ``start``/``end`` args.
Relative filters such as ``_time:5m`` count back from ``end``, so a learner's
query and the reference query see exactly the same logs.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from urllib.parse import quote

from signal_lab.backends import BackendAdapter, QueryResult

# Columns shown first, in this order, when present.
LEADING = ["_time", "_msg", "service.name", "severity_text", "severity", "trace_id", "span_id"]
# Internal fields that only add noise unless asked for by name.
HIDDEN = {"_stream", "_stream_id"}
MAX_ROWS = 1000
# Logs reach VictoriaLogs a second or two after they're written (SDK and
# Collector batching). Ending the window a little in the past keeps late
# arrivals from making two runs of the same query disagree.
LAG_S = 5


class Adapter(BackendAdapter):
    timeout = 10.0

    @property
    def vl(self) -> str:
        return self.settings["victorialogs_url"].rstrip("/")

    async def health(self) -> dict[str, dict]:
        return {"victorialogs": await self.probe(f"{self.vl}/health")}

    async def _hits(self, query: str, window_s: int = 900) -> int:
        end = int(time.time())
        r = await self.client.post(f"{self.vl}/select/logsql/query", data={"query": f"{query} | stats count() hits", "start": end - window_s, "end": end})
        if r.status_code != 200:
            return 0
        for line in r.text.splitlines():
            try:
                return int(json.loads(line).get("hits", 0))
            except (ValueError, TypeError):
                continue
        return 0

    async def find_logs(self, run_id: str) -> bool:
        return await self._hits(f"signal_lab.run_id:={_quote(run_id)}") > 0

    async def suggest(self, language: str, kind: str, prefix: str = "") -> list[str]:
        end = int(time.time())
        params = {"query": "*", "start": end - 3600, "end": end}
        if kind in ("field", "label", "metric"):
            url = f"{self.vl}/select/logsql/field_names"
        else:  # kind is a field name: suggest its values
            url, params["field"] = f"{self.vl}/select/logsql/field_values", kind
            params["limit"] = 200
        try:
            r = await self.client.get(url, params=params)
        except Exception:
            return []
        if r.status_code != 200:
            return []
        values = [v["value"] for v in r.json().get("values", [])]
        return [v for v in values if v.startswith(prefix) and v not in HIDDEN][:500]

    async def query(self, language: str, query: str, *, at_ms: int | None = None, range_s: int = 900) -> QueryResult | None:
        if language != "logsql":
            return None
        end = (at_ms or int(time.time() * 1000)) / 1000 - LAG_S
        params = {"query": query, "start": _rfc3339(end - range_s), "end": _rfc3339(end), "limit": MAX_ROWS}
        try:
            r = await self.client.post(f"{self.vl}/select/logsql/query", data=params)
        except Exception as e:
            return QueryResult(error=f"Could not reach VictoriaLogs: {type(e).__name__}")
        if r.status_code != 200:
            return QueryResult(error=_error(r.text) or f"HTTP {r.status_code}")
        records = []
        for line in r.text.splitlines():
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except ValueError:
                    continue

        asked = set(re.findall(r"[\w.]+", query))
        seen: dict[str, None] = {}
        for rec in records:
            for k in rec:
                if k not in HIDDEN or k in asked:
                    seen.setdefault(k)
        cols = [c for c in LEADING if c in seen] + sorted(c for c in seen if c not in LEADING)
        is_logs = "_msg" in seen
        if not re.search(r"\|\s*sort\b", query, re.I):
            # Newest first for raw logs, oldest first for time buckets.
            records.sort(key=lambda rec: rec.get("_time", ""), reverse=is_logs)
        rows = [[_value(c, rec.get(c, "")) for c in cols] for rec in records]
        res = QueryResult(columns=cols, rows=rows, stats={"rows": len(rows)})
        if len(rows) >= MAX_ROWS:
            res.stats["truncated"] = True

        # Chart time-bucketed stats: `stats by (_time:1m, ...) count() ...`.
        if not is_logs and "_time" in cols and len(rows) > 1:
            ti = cols.index("_time")
            nums = [i for i, c in enumerate(cols) if i != ti and all(isinstance(row[i], (int, float)) for row in rows)]
            keys = [i for i, c in enumerate(cols) if i != ti and i not in nums]
            groups: dict[tuple, dict] = {}
            for row in rows:
                t = _ms(row[ti])
                if t is None:
                    continue
                labels = {cols[i]: str(row[i]) for i in keys}
                for i in nums:
                    gk = (cols[i],) + tuple(labels.values())
                    g = groups.setdefault(gk, {"name": _series_name(cols[i], labels, len(nums) > 1), "labels": labels, "points": []})
                    g["points"].append([t, row[i]])
            for g in list(groups.values())[:30]:
                g["points"].sort()
                res.series.append(g)
        return res

    def link(self, kind: str, params: dict) -> str | None:
        public = self.settings["victorialogs_public_url"].rstrip("/")
        if kind == "logs" and params.get("run_id"):
            q = f"signal_lab.run_id:={_quote(params['run_id'])}"
        elif kind == "trace" and params.get("trace_id"):
            q = f"trace_id:={_quote(params['trace_id'])}"
        elif kind == "query" and params.get("query"):
            q = params["query"]
        else:
            return super().link(kind, params)
        return f"{public}/select/vmui/#/?query={quote(q, safe='')}&g0.range_input=15m"


def _quote(s: str) -> str:
    return json.dumps(str(s))


def _rfc3339(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _error(text: str) -> str:
    # VictoriaLogs answers errors in plain text, sometimes prefixed with the request.
    text = text.strip()
    m = re.match(r"cannot parse `query` arg \[.*?\]: (.*)", text, re.S)
    return (m.group(1) if m else text)[:600]


def _value(col: str, v):
    """Numbers as numbers (stats results), except for ids and internal fields."""
    if not isinstance(v, str) or col.startswith("_") or col.endswith("id") or not v:
        return v
    try:
        f = float(v)
    except ValueError:
        return v
    if f != f or f in (float("inf"), float("-inf")):
        return v
    return int(f) if f == int(f) and abs(f) < 1e15 and "." not in v and "e" not in v.lower() else f


def _ms(v) -> int | None:
    # Python parses at most 6 fractional digits; VictoriaLogs writes up to 9.
    s = re.sub(r"(\.\d{6})\d+", r"\1", str(v)).replace("Z", "+00:00")
    try:
        return int(datetime.fromisoformat(s).timestamp() * 1000)
    except ValueError:
        return None


def _series_name(col: str, labels: dict, prefix: bool) -> str:
    rest = ", ".join(f'{k}="{v}"' for k, v in labels.items())
    if not rest:
        return col
    return f"{col}{{{rest}}}" if prefix else rest
