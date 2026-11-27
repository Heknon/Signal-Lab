#!/usr/bin/env bash
# Run Signal Lab without Docker: the API (serving the built UI), the shop
# scenario services, and optionally a Collector you run yourself.
#
#   scripts/dev.sh            # telemetry goes straight to the lab's tap
#   OTLP=http://localhost:4318 scripts/dev.sh   # send through your Collector
set -euo pipefail
cd "$(dirname "$0")/.."
P=${PY:-.venv/bin/python}; PY="$(cd "$(dirname "$P")" && pwd)/$(basename "$P")"
BIN=$(dirname "$PY")
OTLP=${OTLP:-http://127.0.0.1:8000/tap}
export SIGNAL_LAB_RELOAD=true
export SHOP_STOREFRONT_URL=http://127.0.0.1:8081 SHOP_CHECKOUT_URL=http://127.0.0.1:8082 \
       SHOP_INVENTORY_URL=http://127.0.0.1:8083 SHOP_PAYMENTS_URL=http://127.0.0.1:8084 SHOP_LOADGEN_URL=http://127.0.0.1:8085

pids=()
cleanup() { kill "${pids[@]}" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

port=8081
for svc in storefront checkout inventory payments loadgen; do
  (cd plugins/scenarios/shop && SHOP_SERVICE=$svc OTEL_SERVICE_NAME=$svc OTEL_EXPORTER_OTLP_ENDPOINT=$OTLP \
    OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf OTEL_LOGS_EXPORTER=otlp OTEL_METRIC_EXPORT_INTERVAL=5000 OTEL_SEMCONV_STABILITY_OPT_IN=http OTEL_PYTHON_DISABLED_INSTRUMENTATIONS=fastapi \
    OTEL_RESOURCE_ATTRIBUTES=deployment.environment.name=lab,service.version=1.4.2 \
    "$BIN/opentelemetry-instrument" "$PY" -m uvicorn app:app --host 127.0.0.1 --port $port --log-level warning) &
  pids+=($!)
  port=$((port + 1))
done

PYTHONPATH=server SIGNAL_LAB_SCENARIOS=shop "$PY" -m signal_lab api &
pids+=($!)
echo "Signal Lab: http://localhost:8000  (UI dev server: cd web && bun run dev)"
wait
