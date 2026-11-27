"""Decode OTLP/HTTP protobuf payloads into plain, UI-friendly dictionaries.

The lab's "tap" receives exactly what the Collector (or the SDK, in dev mode)
exports, so learners see the real data model: resources, scopes, spans,
data points and log records.
"""

from __future__ import annotations

import gzip
import zlib
from typing import Any

from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import (
    ExportLogsServiceRequest,
    ExportLogsServiceResponse,
)
from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import (
    ExportMetricsServiceRequest,
    ExportMetricsServiceResponse,
)
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
    ExportTraceServiceResponse,
)

SPAN_KINDS = {0: "unspecified", 1: "internal", 2: "server", 3: "client", 4: "producer", 5: "consumer"}
STATUS_CODES = {0: "unset", 1: "ok", 2: "error"}
TEMPORALITY = {0: "unspecified", 1: "delta", 2: "cumulative"}


def decompress(body: bytes, encoding: str | None) -> bytes:
    encoding = (encoding or "").lower()
    if encoding == "gzip":
        return gzip.decompress(body)
    if encoding == "deflate":
        return zlib.decompress(body)
    return body


def any_value(v: Any) -> Any:
    kind = v.WhichOneof("value")
    if kind is None:
        return None
    if kind == "array_value":
        return [any_value(x) for x in v.array_value.values]
    if kind == "kvlist_value":
        return {kv.key: any_value(kv.value) for kv in v.kvlist_value.values}
    if kind == "bytes_value":
        return v.bytes_value.hex()
    return getattr(v, kind)


def attrs(kvs: Any) -> dict[str, Any]:
    return {kv.key: any_value(kv.value) for kv in kvs}


def _ns_to_ms(ns: int) -> float:
    return ns / 1_000_000


def decode_traces(body: bytes) -> list[dict]:
    req = ExportTraceServiceRequest.FromString(body)
    spans: list[dict] = []
    for rs in req.resource_spans:
        resource = attrs(rs.resource.attributes)
        for ss in rs.scope_spans:
            scope = {"name": ss.scope.name, "version": ss.scope.version}
            for s in ss.spans:
                spans.append(
                    {
                        "trace_id": s.trace_id.hex(),
                        "span_id": s.span_id.hex(),
                        "parent_span_id": s.parent_span_id.hex() or None,
                        "name": s.name,
                        "kind": SPAN_KINDS.get(s.kind, "unspecified"),
                        "start_ms": _ns_to_ms(s.start_time_unix_nano),
                        "end_ms": _ns_to_ms(s.end_time_unix_nano),
                        "duration_ms": _ns_to_ms(s.end_time_unix_nano - s.start_time_unix_nano),
                        "status": {"code": STATUS_CODES.get(s.status.code, "unset"), "message": s.status.message},
                        "attributes": attrs(s.attributes),
                        "events": [
                            {"name": e.name, "time_ms": _ns_to_ms(e.time_unix_nano), "attributes": attrs(e.attributes)}
                            for e in s.events
                        ],
                        "links": [
                            {"trace_id": l.trace_id.hex(), "span_id": l.span_id.hex(), "attributes": attrs(l.attributes)}
                            for l in s.links
                        ],
                        "resource": resource,
                        "service": resource.get("service.name", "unknown_service"),
                        "scope": scope,
                    }
                )
    return spans


def _number(dp: Any) -> float | int | None:
    kind = dp.WhichOneof("value")
    return getattr(dp, kind) if kind else None


def _exemplars(dp: Any) -> list[dict]:
    out = []
    for ex in dp.exemplars:
        out.append(
            {
                "value": _number(ex),
                "trace_id": ex.trace_id.hex() or None,
                "span_id": ex.span_id.hex() or None,
                "time_ms": _ns_to_ms(ex.time_unix_nano),
            }
        )
    return out


def decode_metrics(body: bytes) -> list[dict]:
    """Return one entry per (metric, data point)."""
    req = ExportMetricsServiceRequest.FromString(body)
    points: list[dict] = []
    for rm in req.resource_metrics:
        resource = attrs(rm.resource.attributes)
        for sm in rm.scope_metrics:
            scope = {"name": sm.scope.name, "version": sm.scope.version}
            for m in sm.metrics:
                data = m.WhichOneof("data")
                base = {
                    "name": m.name,
                    "description": m.description,
                    "unit": m.unit,
                    "resource": resource,
                    "service": resource.get("service.name", "unknown_service"),
                    "scope": scope,
                }
                if data in ("gauge", "sum"):
                    container = getattr(m, data)
                    if data == "sum":
                        instrument = "counter" if container.is_monotonic else "updowncounter"
                        temporality = TEMPORALITY.get(container.aggregation_temporality)
                    else:
                        instrument, temporality = "gauge", None
                    for dp in container.data_points:
                        points.append(
                            base
                            | {
                                "type": data,
                                "instrument": instrument,
                                "temporality": temporality,
                                "attributes": attrs(dp.attributes),
                                "time_ms": _ns_to_ms(dp.time_unix_nano),
                                "value": _number(dp),
                                "exemplars": _exemplars(dp),
                            }
                        )
                elif data == "histogram":
                    for dp in m.histogram.data_points:
                        points.append(
                            base
                            | {
                                "type": "histogram",
                                "instrument": "histogram",
                                "temporality": TEMPORALITY.get(m.histogram.aggregation_temporality),
                                "attributes": attrs(dp.attributes),
                                "time_ms": _ns_to_ms(dp.time_unix_nano),
                                "count": dp.count,
                                "sum": dp.sum if dp.HasField("sum") else None,
                                "min": dp.min if dp.HasField("min") else None,
                                "max": dp.max if dp.HasField("max") else None,
                                "bounds": list(dp.explicit_bounds),
                                "bucket_counts": list(dp.bucket_counts),
                                "exemplars": _exemplars(dp),
                            }
                        )
                elif data == "exponential_histogram":
                    for dp in m.exponential_histogram.data_points:
                        points.append(
                            base
                            | {
                                "type": "exponential_histogram",
                                "instrument": "histogram",
                                "temporality": TEMPORALITY.get(m.exponential_histogram.aggregation_temporality),
                                "attributes": attrs(dp.attributes),
                                "time_ms": _ns_to_ms(dp.time_unix_nano),
                                "count": dp.count,
                                "sum": dp.sum if dp.HasField("sum") else None,
                                "min": dp.min if dp.HasField("min") else None,
                                "max": dp.max if dp.HasField("max") else None,
                                "scale": dp.scale,
                                "zero_count": dp.zero_count,
                                "positive": {"offset": dp.positive.offset, "bucket_counts": list(dp.positive.bucket_counts)},
                                "negative": {"offset": dp.negative.offset, "bucket_counts": list(dp.negative.bucket_counts)},
                                "exemplars": _exemplars(dp),
                            }
                        )
                elif data == "summary":
                    for dp in m.summary.data_points:
                        points.append(
                            base
                            | {
                                "type": "summary",
                                "instrument": "summary",
                                "temporality": None,
                                "attributes": attrs(dp.attributes),
                                "time_ms": _ns_to_ms(dp.time_unix_nano),
                                "count": dp.count,
                                "sum": dp.sum,
                                "quantiles": [{"q": q.quantile, "value": q.value} for q in dp.quantile_values],
                            }
                        )
    return points


def decode_logs(body: bytes) -> list[dict]:
    req = ExportLogsServiceRequest.FromString(body)
    out: list[dict] = []
    for rl in req.resource_logs:
        resource = attrs(rl.resource.attributes)
        for sl in rl.scope_logs:
            scope = {"name": sl.scope.name, "version": sl.scope.version}
            for r in sl.log_records:
                ts = r.time_unix_nano or r.observed_time_unix_nano
                out.append(
                    {
                        "time_ms": _ns_to_ms(ts),
                        "severity_text": r.severity_text or _severity_name(r.severity_number),
                        "severity_number": r.severity_number,
                        "body": any_value(r.body),
                        "attributes": attrs(r.attributes),
                        "trace_id": r.trace_id.hex() or None,
                        "span_id": r.span_id.hex() or None,
                        "resource": resource,
                        "service": resource.get("service.name", "unknown_service"),
                        "scope": scope,
                    }
                )
    return out


def _severity_name(n: int) -> str:
    if n == 0:
        return "UNSPECIFIED"
    for name, lo in (("FATAL", 21), ("ERROR", 17), ("WARN", 13), ("INFO", 9), ("DEBUG", 5), ("TRACE", 1)):
        if n >= lo:
            return name
    return "UNSPECIFIED"


EMPTY_RESPONSES = {
    "traces": ExportTraceServiceResponse().SerializeToString(),
    "metrics": ExportMetricsServiceResponse().SerializeToString(),
    "logs": ExportLogsServiceResponse().SerializeToString(),
}
DECODERS = {"traces": decode_traces, "metrics": decode_metrics, "logs": decode_logs}
