"""Elastic adapter: Elasticsearch searches, ES|QL and Kibana saved objects.

OpenTelemetry data sent through APM Server lands in data streams:
``traces-apm*``, ``metrics-apm.app.*`` and ``logs-apm.app.*``. Resource
attributes that aren't mapped to ECS fields become ``labels.*`` (dots
replaced by underscores), e.g. ``labels.signal_lab_run_id``.
"""

from __future__ import annotations

from signal_lab.backends import BackendAdapter, QueryResult, Verdict


class Adapter(BackendAdapter):
    timeout = 8.0

    @property
    def es(self) -> str:
        return self.settings["elasticsearch_url"].rstrip("/")

    @property
    def kibana(self) -> str:
        return self.settings["kibana_url"].rstrip("/")

    def _headers(self) -> dict:
        key = self.settings.get("elasticsearch_api_key")
        return {"Authorization": f"ApiKey {key}"} if key else {}

    async def health(self) -> dict[str, dict]:
        return {
            "elasticsearch": await self.probe(f"{self.es}/_cluster/health"),
            "apm-server": await self.probe(self.settings["apm_server_url"].rstrip("/") + "/"),
            "kibana": await self.probe(f"{self.kibana}/api/status"),
        }

    async def _count(self, index: str, query: dict) -> int:
        r = await self.client.post(f"{self.es}/{index}/_count?ignore_unavailable=true&allow_no_indices=true", json={"query": query}, headers=self._headers())
        return r.json().get("count", 0) if r.status_code == 200 else 0

    async def find_trace(self, trace_id: str) -> bool:
        return await self._count("traces-apm*", {"term": {"trace.id": trace_id}}) > 0

    async def find_metric(self, name: str, service: str) -> bool:
        return await self._count("metrics-apm*", {"bool": {"filter": [{"term": {"service.name": service}}, {"exists": {"field": name}}]}}) > 0

    async def find_logs(self, run_id: str) -> bool:
        return await self._count("logs-apm*", {"term": {"labels.signal_lab_run_id": run_id}}) > 0

    async def query(self, language: str, query: str, *, at_ms: int | None = None, range_s: int = 900) -> QueryResult | None:
        if language != "esql":
            return None
        try:
            r = await self.client.post(f"{self.es}/_query?format=json", json={"query": query}, headers=self._headers())
        except Exception as e:
            return QueryResult(error=f"Could not reach Elasticsearch: {type(e).__name__}")
        body = r.json()
        if r.status_code != 200:
            err = body.get("error", {})
            return QueryResult(error=err.get("reason") if isinstance(err, dict) else str(err))
        cols = [c["name"] for c in body.get("columns", [])]
        rows = body.get("values", [])
        res = QueryResult(columns=cols, rows=rows, stats={"rows": len(rows), "took_ms": body.get("took")})
        # Chart it when it looks like a time bucket + one or more numbers.
        types = [c["type"] for c in body.get("columns", [])]
        if "date" in types and len(rows) > 1:
            ti = types.index("date")
            from datetime import datetime

            for ci, t in enumerate(types):
                if t in ("long", "double", "integer", "unsigned_long") and ci != ti:
                    pts = []
                    for row in rows:
                        try:
                            ts = datetime.fromisoformat(str(row[ti]).replace("Z", "+00:00")).timestamp() * 1000
                            pts.append([int(ts), row[ci]])
                        except (ValueError, TypeError):
                            continue
                    res.series.append({"name": cols[ci], "labels": {}, "points": sorted(pts)})
        return res

    async def verify(self, check: dict, context: dict) -> Verdict | None:
        kind = check.get("verify")
        if kind not in ("kibana_dashboard", "kibana_rule"):
            return None
        headers = self._headers() | {"kbn-xsrf": "signal-lab"}
        if kind == "kibana_rule":
            r = await self.client.get(f"{self.kibana}/api/alerting/rules/_find", params={"search": check.get("name_contains", ""), "per_page": 50}, headers=headers)
            if r.status_code != 200:
                return Verdict(False, f"Kibana returned HTTP {r.status_code}.")
            rules = r.json().get("data", [])
            wanted = check.get("rule_type")
            matches = [x for x in rules if not wanted or x.get("rule_type_id") == wanted]
            return Verdict(bool(matches), f"Found rule “{matches[0]['name']}”." if matches else "No matching alerting rule yet.")
        r = await self.client.get(f"{self.kibana}/api/saved_objects/_find", params={"type": "dashboard", "search": check.get("title_contains", "") + "*", "search_fields": "title"}, headers=headers)
        if r.status_code != 200:
            return Verdict(False, f"Kibana returned HTTP {r.status_code}.")
        objs = r.json().get("saved_objects", [])
        return Verdict(bool(objs), f"Found dashboard “{objs[0]['attributes']['title']}”." if objs else "No matching Kibana dashboard yet.")
