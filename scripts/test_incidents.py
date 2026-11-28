#!/usr/bin/env python3
"""Check that each incident's fault produces the evidence its lesson asks for.

Applies the incident's faults directly (skipping the slow timeline), waits,
then grades a known-good evidence query through the lesson's answer endpoint.
Takes a few minutes per incident.

    python scripts/test_incidents.py                       # all incidents
    python scripts/test_incidents.py incident-retry-storm  # one
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request

LAB = os.getenv("LAB_URL", "http://localhost:8000").rstrip("/")
WAIT = int(os.getenv("WAIT_S", "100"))

SOLUTIONS = {
    "incident-tail-latency": 'histogram_quantile(0.99, sum by (le, http_route) (rate(http_server_request_duration_seconds_bucket{service_name="inventory"}[2m])))',
    "incident-retry-storm": 'sum(rate(http_server_request_duration_seconds_count{service_name="payments",http_route="/charge"}[2m])) / sum(rate(http_server_request_duration_seconds_count{service_name="checkout",http_route="/checkout"}[2m]))',
    "incident-saturation": "max_over_time(db_client_connection_pending_requests[5m])",
    "incident-bad-deploy": 'sum by (app_user_tier) (rate(shop_checkouts_total{outcome="failed"}[2m]))',
    "incident-silent-failure": 'sum(rate(shop_order_value_USD_count[2m])) / sum(rate(shop_checkouts_total{outcome="ok"}[2m]))',
    "incident-memory-leak": 'max_over_time(process_memory_usage_bytes{service_name="inventory"}[10m])',
    "incident-cardinality": "count(shop_checkouts_total)",
}

# Wrong evidence queries that passed before the incident audit. Each must be
# rejected while the fault is active (when the right answer passes).
H = "http_server_request_duration_seconds"
MISTAKES = {
    "incident-tail-latency": [
        f'histogram_quantile(0.5, sum by (le, http_route) (rate({H}_bucket{{service_name="inventory"}}[2m])))',
        f'histogram_quantile(0.99, sum by (le, http_route) ({H}_bucket{{service_name="inventory"}}))',
        f'histogram_quantile(0.9, sum by (le, http_route) (increase({H}_bucket{{service_name="inventory"}}[1h])))',
    ],
    "incident-retry-storm": [
        f'sum by (service_name) (rate({H}_count{{service_name=~"payments|checkout"}}[2m]))',
        f'sum(rate({H}_count{{service_name=~"payments|checkout"}}[2m])) / sum(rate({H}_count{{service_name="checkout"}}[2m]))',
        f'sum(rate(http_client_request_duration_seconds_count{{service_name="checkout"}}[2m])) / sum(rate({H}_count{{service_name="checkout"}}[2m])) # payments',
    ],
    "incident-saturation": [
        "count(db_client_connection_pending_requests)",
        "sum(rate(db_client_connection_pending_requests[5m]))",
        'sum(db_client_connection_pending_requests) + sum(db_client_connection_count{state="used"})',
        "max_over_time(db_client_connection_pending_requests[1h])",
    ],
    "incident-bad-deploy": [
        'count by (app_user_tier) (shop_checkouts_total{outcome="failed"})',
        'bottomk(1, sum by (app_user_tier) (rate(shop_checkouts_total{outcome="ok"}[2m])))',
    ],
    "incident-silent-failure": [
        f'sum(rate(shop_order_value_USD_count[2m])) / sum(rate({H}_count{{service_name="storefront"}}[2m]))',
        'sum by (app_user_tier) (rate(shop_order_value_USD_count[2m])) < 1',
        'shop_checkouts_total{outcome="ok"} and 1 - (sum(rate(shop_order_value_USD_count[2m])) / sum(rate(shop_checkouts_total{outcome="ok"}[2m])))',
    ],
    "incident-memory-leak": [
        "sum(process_memory_usage_bytes)",
        'sum_over_time(process_memory_usage_bytes{service_name="inventory"}[10m])',
    ],
    "incident-cardinality": [
        'count({__name__=~"shop_.*"})',
        f"sum({H}_count)",
        f"count({H}_bucket)",
        "count_over_time(shop_checkouts_total[5m])",
    ],
}


def call(path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(LAB + path, data=json.dumps(body).encode() if body is not None else None, headers={"content-type": "application/json"}, method="POST" if body is not None else "GET")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def main() -> int:
    import yaml

    root = os.path.join(os.path.dirname(__file__), "..", "plugins", "lessons", "practice")
    wanted = set(sys.argv[1:]) or set(SOLUTIONS)
    failures = 0
    for slug in SOLUTIONS:
        if slug not in wanted:
            continue
        text = open(os.path.join(root, slug, "lesson.md")).read()
        meta = yaml.safe_load(text.split("---")[1])
        call("/api/scenario/reset", {})
        time.sleep(5)
        baseline = call(f"/api/lessons/practice/{slug}/answer", {"question": "evidence", "answer": SOLUTIONS[slug]})
        for step in meta["incident"]["timeline"]:
            if "load" in step:
                call("/api/scenario/load", {"rps": step["load"]})
            for svc, faults in (step.get("set") or {}).items():
                call(f"/api/scenario/services/{svc}/chaos", faults)
        time.sleep(WAIT)
        during = call(f"/api/lessons/practice/{slug}/answer", {"question": "evidence", "answer": SOLUTIONS[slug]})
        passed_wrong = [q for q in MISTAKES.get(slug, []) if call(f"/api/lessons/practice/{slug}/answer", {"question": "evidence", "answer": q})["correct"]]
        call("/api/scenario/reset", {})
        call("/api/scenario/load", {"rps": 2})
        ok = during["correct"] and not baseline["correct"] and not passed_wrong
        failures += not ok
        print(f"{'PASS' if ok else 'FAIL'} {slug}: during={during['correct']} baseline={baseline['correct']}")
        if not during["correct"]:
            print("     ", during["explanation"])
        for q in passed_wrong:
            print("      wrong query passed:", q)
        time.sleep(20)
    print(f"\n{failures} failing incident(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
