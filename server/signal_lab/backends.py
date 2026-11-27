"""Base class for backend adapters.

A backend plugin ships an ``adapter.py`` with ``class Adapter(BackendAdapter)``.
Every method is optional: return ``None`` (or keep the default) for anything
the backend does not support, and the lab will simply not offer it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass
class QueryResult:
    """A backend-neutral query result.

    * ``table``: ``columns`` + ``rows`` (instant vectors, ES|QL tables)
    * ``series``: time series for charting, ``[{"name", "labels", "points": [[t_ms, v], ...]}]``
    """

    columns: list[str] = field(default_factory=list)
    rows: list[list[Any]] = field(default_factory=list)
    series: list[dict] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict:
        return {"columns": self.columns, "rows": self.rows, "series": self.series, "stats": self.stats, "error": self.error}


@dataclass
class Verdict:
    passed: bool
    detail: str = ""


class BackendAdapter:
    timeout = 5.0

    def __init__(self, plugin_id: str, manifest: dict, settings: dict[str, str]):
        self.id = plugin_id
        self.manifest = manifest
        self.settings = settings
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()

    # ---- health ---------------------------------------------------------
    async def health(self) -> dict[str, dict]:
        """Return ``{component_id: {"ok": bool, "detail": str}}``."""
        return {}

    async def probe(self, url: str, ok_status: tuple[int, ...] = (200,)) -> dict:
        try:
            r = await self.client.get(url, timeout=2.5)
            return {"ok": r.status_code in ok_status, "detail": f"HTTP {r.status_code}"}
        except httpx.HTTPError as e:
            return {"ok": False, "detail": type(e).__name__}

    # ---- confirmations: "did my telemetry land in this backend?" --------
    async def find_trace(self, trace_id: str) -> bool | None:
        return None

    async def find_metric(self, name: str, service: str) -> bool | None:
        return None

    async def find_logs(self, run_id: str) -> bool | None:
        return None

    # ---- query playground ---------------------------------------------
    async def query(self, language: str, query: str, *, at_ms: int | None = None, range_s: int = 900) -> QueryResult | None:
        return None

    async def suggest(self, language: str, kind: str, prefix: str = "") -> list[str]:
        """Autocomplete values, e.g. metric names (``kind="metric"``)."""
        return []

    # ---- deep links into the backend's own UI ---------------------------
    def link(self, kind: str, params: dict[str, Any]) -> str | None:
        """Return a URL for ``kind`` (``trace``, ``metric``, ``logs`` ...).

        The default looks for a manifest link with the same id and fills in
        ``{placeholders}`` from settings and ``params``.
        """
        import re
        from urllib.parse import quote

        for l in self.manifest.get("links", []):
            if l["id"] == kind:
                values = self.settings | {k: quote(str(v), safe="") for k, v in params.items()}
                url = re.sub(r"\{(\w+)\}", lambda m: str(values.get(m.group(1), m.group(0))), l["url"])
                return None if "{" in url else url
        return None

    # ---- backend-specific checks (dashboards, saved queries, ...) -------
    async def verify(self, check: dict, context: dict) -> Verdict | None:
        return None
