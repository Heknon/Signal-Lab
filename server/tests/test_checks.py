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


def test_intellisense_completes_and_documents_otel():
    import asyncio

    from signal_lab import intellisense

    if not intellisense.available():
        return
    code = "from opentelemetry import trace\ntracer = trace.get_tracer('x')\nwith tracer.start_as_current_span('a') as span:\n    span.set_"
    res = asyncio.run(intellisense.complete(code, len(code)))
    labels = [i["label"] for i in res["items"]]
    assert "set_attribute" in labels and res["from"] == len(code) - len("set_")
    item = next(i for i in res["items"] if i["label"] == "set_attribute")
    assert "key: str" in item["detail"] and item["doc"]
    call = code.replace("span.set_", "span.set_attribute('k', ")
    sig = asyncio.run(intellisense.signatures(call, len(call)))
    assert sig["name"] == "set_attribute" and sig["index"] == 1 and sig["params"][sig["index"]].startswith("value")
    hov = asyncio.run(intellisense.hover(code, code.index("start_as_current_span") + 3))
    assert hov and "start_as_current_span" in hov["title"]


def test_histogram_spread_and_max():
    def hist(bounds, counts, mx):
        return {"name": "d", "unit": "s", "instrument": "histogram",
                "series": [{"attributes": {}, "bounds": bounds, "bucket_counts": counts, "count": sum(counts), "max": mx}]}
    spread = {"type": "metric", "name": "d", "spread": {"max_share": 0.5, "max_overflow": 0.05, "min_used": 4}}
    good = hist([0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1], [2, 30, 80, 60, 25, 3, 0, 0], 0.4)
    assert run(spread, metrics=[good])["status"] == "pass"
    overflow = run(spread, metrics=[hist([0.01, 0.1, 1], [0, 0, 0, 200], 235)])
    assert overflow["status"] == "fail" and "above your last boundary" in overflow["detail"]
    lumped = run(spread, metrics=[hist([0.1, 0.5, 1, 2], [186, 14, 0, 0, 0], 0.4)])
    assert lumped["status"] == "fail" and "first boundary" in lumped["detail"]
    r = run({"type": "metric", "name": "d", "max": {"lte": 5}}, metrics=[hist([1], [0, 200], 235.3)])
    assert r["status"] == "fail" and "at most 5" in r["detail"]


def test_strict_numbers_and_status_alternatives():
    as_str = span("checkout", attributes={"n": "3"})
    r = run({"type": "span", "where": {"name": "checkout", "attributes": {"n": {"gte": 1}}}}, [as_str])
    assert r["status"] == "fail" and "string" in r["detail"]
    assert run({"type": "span", "where": {"name": "checkout", "attributes": {"n": 3}}}, [as_str])["status"] == "fail"
    assert run({"type": "span", "where": {"name": "checkout", "attributes": {"n": 3}}}, [span("checkout", attributes={"n": 3})])["status"] == "pass"
    ok = span("charge", status={"code": "ok", "message": ""})
    assert run({"type": "span", "where": {"name": "charge", "status": ["unset", "ok"]}}, [ok])["status"] == "pass"


def test_logs_in_span_and_forbidden_pattern():
    spans = [span("batch", sid="b"), span("refund", sid="r", parent="b")]
    log = {"body": "refund rejected", "severity_text": "ERROR", "attributes": {}, "trace_id": "t1", "span_id": "b"}
    r = run({"type": "log", "severity": "ERROR", "in_span": "refund"}, spans, logs=[log])
    assert r["status"] == "fail" and "`batch`" in r["detail"]
    assert run({"type": "log", "severity": "ERROR", "in_span": "refund"}, spans, logs=[log | {"span_id": "r"}])["status"] == "pass"
    card = log | {"body": "declined", "attributes": {"app.card.number": "4111111111110002"}}
    r = run({"type": "log", "forbid_pattern": r"\d{13,16}"}, logs=[card])
    assert r["status"] == "fail" and "app.card.number" in r["detail"]
    assert run({"type": "log", "forbid_pattern": r"\d{13,16}"}, logs=[])["status"] == "pass"


def test_metric_absent_values_changes_mean_gap_and_distinct():
    def m(name, series, inst="counter"):
        return {"name": name, "unit": "", "instrument": inst, "series": series}
    ok_only = m("orders", [{"attributes": {"outcome": "ok"}, "value": 5, "history": []}])
    assert run({"type": "metric", "name": "orders", "attribute_values": {"outcome": ["ok", "failed"]}}, metrics=[ok_only])["status"] == "fail"
    assert run({"type": "metric", "name": "service.started", "absent": True}, metrics=[ok_only])["status"] == "pass"
    assert run({"type": "metric", "name": "orders", "absent": True}, metrics=[ok_only])["status"] == "fail"
    flat = m("queue.length", [{"attributes": {}, "value": 12, "history": [{"value": 12}, {"value": 12}]}], "gauge")
    assert run({"type": "metric", "name": "queue.length", "changes": True}, metrics=[flat])["status"] == "fail"
    hist = m("d", [{"attributes": {"tier": "gold"}, "count": 10, "sum": 0.9, "history": []},
                   {"attributes": {"tier": "silver"}, "count": 10, "sum": 0.2, "history": []}], "histogram")
    assert run({"type": "metric", "name": "d", "mean_gap": {"attribute": "tier", "high": "gold", "min": 0.03}}, metrics=[hist])["status"] == "pass"
    same = [span("GET", sid=str(i), kind="client", attributes={"server.address": "x"}) for i in range(3)]
    r = run({"type": "span", "where": {"kind": "client"}, "count": {"min": 3}, "distinct": {"server.address": {"min": 3}}}, same)
    assert r["status"] == "fail" and "1 different" in r["detail"]
