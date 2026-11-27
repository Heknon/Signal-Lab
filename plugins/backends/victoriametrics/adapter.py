"""VictoriaMetrics + Grafana adapter.

VictoriaMetrics implements the Prometheus HTTP API, so everything here is
plain ``/api/v1/query`` calls; Grafana is used for dashboard checks.
"""

from __future__ import annotations

import json
import re
import time
from urllib.parse import quote

from signal_lab.backends import BackendAdapter, QueryResult, Verdict


def prom_name(otel_name: str) -> str:
    """Approximate OTLP -> Prometheus metric name translation."""
    return re.sub(r"[^a-zA-Z0-9_:]", "_", otel_name)


class Adapter(BackendAdapter):
    @property
    def vm(self) -> str:
        return self.settings["victoriametrics_url"].rstrip("/")

    @property
    def grafana(self) -> str:
        return self.settings["grafana_url"].rstrip("/")

    def _grafana_headers(self) -> dict:
        token = self.settings.get("grafana_token")
        return {"Authorization": f"Bearer {token}"} if token else {}

    async def health(self) -> dict[str, dict]:
        return {
            "victoriametrics": await self.probe(f"{self.vm}/health"),
            "grafana": await self.probe(f"{self.grafana}/api/health"),
        }

    async def find_metric(self, name: str, service: str) -> bool:
        base = prom_name(name)
        match = f'{{__name__=~"{re.escape(base)}.*",service_name="{service}"}}'
        r = await self.client.get(f"{self.vm}/api/v1/series", params={"match[]": match, "start": int(time.time()) - 600})
        return r.status_code == 200 and bool(r.json().get("data"))

    async def suggest(self, language: str, kind: str, prefix: str = "") -> list[str]:
        if kind == "metric":
            r = await self.client.get(f"{self.vm}/api/v1/label/__name__/values", params={"start": int(time.time()) - 3600})
        else:
            r = await self.client.get(f"{self.vm}/api/v1/labels", params={"start": int(time.time()) - 3600})
        if r.status_code != 200:
            return []
        return [v for v in r.json().get("data", []) if v.startswith(prefix)][:500]

    async def query(self, language: str, query: str, *, at_ms: int | None = None, range_s: int = 900) -> QueryResult | None:
        if language not in ("metricsql", "promql"):
            return None
        at = (at_ms or int(time.time() * 1000)) / 1000
        try:
            inst = await self.client.get(f"{self.vm}/api/v1/query", params={"query": query, "time": at})
            body = inst.json()
        except Exception as e:
            return QueryResult(error=f"Could not reach VictoriaMetrics: {type(e).__name__}")
        if body.get("status") != "success":
            return QueryResult(error=body.get("error", f"HTTP {inst.status_code}"))
        data = body["data"]
        res = QueryResult(stats={"result_type": data["resultType"]})
        if data["resultType"] == "scalar":
            res.columns, res.rows = ["value"], [[_num(data["result"][1])]]
        elif data["resultType"] in ("vector", "matrix"):
            labels = sorted({k for s in data["result"] for k in s["metric"]})
            res.columns = labels + ["value"]
            for s in data["result"]:
                v = s["value"][1] if "value" in s else (s["values"][-1][1] if s.get("values") else None)
                res.rows.append([s["metric"].get(k, "") for k in labels] + [_num(v)])
        res.stats["series"] = len(res.rows)
        # Range query for the chart.
        if data["resultType"] in ("vector", "scalar"):
            step = max(5, range_s // 120)
            try:
                rng = await self.client.get(f"{self.vm}/api/v1/query_range", params={"query": query, "start": at - range_s, "end": at, "step": step})
                rb = rng.json()
                if rb.get("status") == "success" and rb["data"]["resultType"] == "matrix":
                    for s in rb["data"]["result"][:30]:
                        res.series.append({"name": _series_name(s["metric"]), "labels": s["metric"], "points": [[int(t * 1000), _num(v)] for t, v in s["values"]]})
                    res.stats["step_s"] = step
            except Exception:
                pass
        return res

    def link(self, kind: str, params: dict) -> str | None:
        if kind in ("metric", "query"):
            # OTLP names gain unit and _total suffixes on the way in, so match by prefix.
            expr = params.get("expr") or f'{{__name__=~"{prom_name(params.get("name", ""))}.*"}}'
            panes = {"sl": {"datasource": self.settings["grafana_datasource_uid"], "queries": [{"refId": "A", "expr": expr, "datasource": {"type": "prometheus", "uid": self.settings["grafana_datasource_uid"]}}], "range": {"from": "now-15m", "to": "now"}}}
            return f"{self.settings['grafana_public_url'].rstrip('/')}/explore?schemaVersion=1&orgId=1&panes={quote(json.dumps(panes, separators=(',', ':')))}"
        return super().link(kind, params)

    async def verify(self, check: dict, context: dict) -> Verdict | None:
        if check.get("verify") != "grafana_dashboard":
            return None
        r = await self.client.get(f"{self.grafana}/api/search", params={"type": "dash-db", "query": check.get("title_contains", "")}, headers=self._grafana_headers())
        if r.status_code != 200:
            return Verdict(False, f"Grafana search failed (HTTP {r.status_code}).")
        hits = [h for h in r.json() if h.get("uid") not in check.get("ignore_uids", ["signal-shop"])]
        if not hits:
            return Verdict(False, f"No dashboard found{' matching “' + check['title_contains'] + '”' if check.get('title_contains') else ''}. Save your dashboard first.")
        wanted = [w.lower() for w in check.get("panel_expr_contains", [])]
        best = ""
        for h in hits:
            d = await self.client.get(f"{self.grafana}/api/dashboards/uid/{h['uid']}", headers=self._grafana_headers())
            if d.status_code != 200:
                continue
            dash = d.json()["dashboard"]
            panels = _flatten_panels(dash.get("panels", []))
            exprs = [t.get("expr", "").lower() for p in panels for t in p.get("targets", [])]
            missing = [w for w in wanted if not any(w in e for e in exprs)]
            variables = [v.get("name") for v in dash.get("templating", {}).get("list", [])]
            need_vars = [v for v in check.get("variables", []) if v not in variables]
            if len(panels) >= check.get("min_panels", 1) and not missing and not need_vars:
                return Verdict(True, f"“{dash.get('title')}” has {len(panels)} panel(s) with the right queries.")
            problems = []
            if len(panels) < check.get("min_panels", 1):
                problems.append(f"{len(panels)} panel(s), need {check.get('min_panels', 1)}")
            if missing:
                problems.append("no panel uses " + ", ".join(f"`{m}`" for m in missing))
            if need_vars:
                problems.append("missing variable " + ", ".join(f"`${v}`" for v in need_vars))
            best = best or f"“{dash.get('title')}”: " + "; ".join(problems)
        return Verdict(False, best)


def _flatten_panels(panels: list[dict]) -> list[dict]:
    out = []
    for p in panels:
        if p.get("type") == "row":
            out.extend(_flatten_panels(p.get("panels", [])))
        else:
            out.append(p)
    return out


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return v
    return f if f != int(f) or abs(f) > 1e15 else int(f)


def _series_name(metric: dict) -> str:
    name = metric.get("__name__", "")
    rest = ", ".join(f'{k}="{v}"' for k, v in metric.items() if k != "__name__")
    return f"{name}{{{rest}}}" if rest else name or "{}"
