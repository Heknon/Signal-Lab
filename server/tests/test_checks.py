from signal_lab import checks


def span(name, parent=None, sid="s1", **kw):
    base = {"trace_id": "t1", "span_id": sid, "parent_span_id": parent, "name": name, "kind": "internal", "duration_ms": 5,
            "status": {"code": "unset", "message": ""}, "attributes": {}, "events": [], "links": [], "resource": {}, "service": "svc"}
    return base | kw


def run(check, spans=(), metrics=(), logs=(), **ctx):
    check = {"id": "c"} | check
    return checks.evaluate([check], {"spans": list(spans), "metrics": list(metrics), "logs": list(logs)}, ctx)[0]


def test_span_name_suggestion():
    r = run({"type": "span", "where": {"name": "say-hello"}}, [span("say_hello")])
    assert r["status"] == "fail" and "say_hello" in r["detail"]


def test_span_parent_and_attributes():
    spans = [span("process", sid="a"), span("inner", parent="a", sid="b", attributes={"n": 3})]
    assert run({"type": "span", "where": {"name": "inner", "parent": "process", "attributes": {"n": {"gte": 2}}}}, spans)["status"] == "pass"
    r = run({"type": "span", "where": {"name": "process", "parent": "inner"}}, spans)
    assert r["status"] == "fail" and "no parent" in r["detail"]


def test_trace_services():
    spans = [span("a", sid="a"), span("b", parent="a", sid="b", service="other")]
    assert run({"type": "trace", "services": {"min": 2}}, spans)["status"] == "pass"


def test_metric_cardinality():
    m = {"name": "api.requests", "unit": "", "instrument": "counter", "series": [{"attributes": {"user.id": str(i)}, "value": 1} for i in range(10)]}
    r = run({"type": "metric", "name": "api.requests", "series": {"max": 6}}, metrics=[m])
    assert r["status"] == "fail" and "10 time series" in r["detail"]


def test_log_uncorrelated():
    logs = [{"body": "x", "severity_text": "INFO", "attributes": {}, "trace_id": None, "span_id": None}]
    assert run({"type": "log", "correlated": False, "count": {"max": 0}}, logs=logs)["status"] == "fail"


def test_pending_while_collecting():
    assert run({"type": "span", "where": {"name": "x"}}, collecting=True)["status"] == "pending"


def test_map_external_dependencies_and_peer_service():
    def get(sid, host, peer=None):
        attrs = {"server.address": host} | ({"peer.service": peer} if peer else {})
        return span("GET", sid=sid, kind="client", service="price-fetcher", attributes=attrs)
    by_host = [get("a", "eu.prices.example"), get("b", "us.prices.example")]
    r = run({"type": "map", "edge": {"from": "price-fetcher", "to": "price-api"}}, by_host)
    assert r["status"] == "fail" and "eu.prices.example" in r["detail"]
    assert run({"type": "map", "nodes_absent": ["eu.prices.example"]}, by_host)["status"] == "fail"
    named = [get("a", "eu.prices.example", "price-api"), get("b", "us.prices.example", "price-api")]
    assert run({"type": "map", "edge": {"from": "price-fetcher", "to": "price-api", "external": True, "calls": 2},
                "nodes_absent": ["eu.prices.example", "us.prices.example"]}, named)["status"] == "pass"


def test_map_instrumented_callee_and_same_service_server_span():
    client = span("GET", sid="c", kind="client", service="price-fetcher", attributes={"server.address": "api"})
    same = span("handle", sid="s", parent="c", kind="server", service="price-fetcher")
    r = run({"type": "map", "edge": {"from": "price-fetcher", "to": "price-api", "external": False}}, [client, same])
    assert r["status"] == "fail"  # a server span in the caller's own service isn't a dependency
    other = span("handle", sid="s", parent="c", kind="server", service="price-api")
    assert run({"type": "map", "edge": {"from": "price-fetcher", "to": "price-api", "external": False}}, [client, other])["status"] == "pass"
    dashed = run({"type": "map", "edge": {"from": "price-fetcher", "to": "api", "external": False}}, [client])
    assert dashed["status"] == "fail" and "dashed" in dashed["detail"]


def test_map_producer_names_its_queue():
    p = span("send price-updates", sid="p", kind="producer", service="price-fetcher", attributes={"messaging.destination.name": "price-updates"})
    assert run({"type": "map", "edge": {"from": "price-fetcher", "to": "price-updates"}}, [p])["status"] == "pass"
    unnamed = span("send price-updates", sid="p", kind="producer", service="price-fetcher")
    assert checks.service_map([unnamed])["edges"][0]["to"] == "price-updates"
