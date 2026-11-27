"""Jaeger adapter: confirms traces through the Jaeger query API."""

from __future__ import annotations

from signal_lab.backends import BackendAdapter


class Adapter(BackendAdapter):
    @property
    def base(self) -> str:
        return self.settings["jaeger_url"].rstrip("/")

    async def health(self) -> dict[str, dict]:
        return {"jaeger": await self.probe(f"{self.base}/api/services")}

    async def find_trace(self, trace_id: str) -> bool:
        r = await self.client.get(f"{self.base}/api/traces/{trace_id}")
        return r.status_code == 200 and bool(r.json().get("data"))
