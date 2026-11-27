#!/usr/bin/env bash
# Copy the Collector configs (and any Grafana dashboards) the Helm chart ships
# from their single source of truth into charts/signal-lab/files/.
#
#   scripts/sync-chart.sh          # copy
#   scripts/sync-chart.sh --check  # exit 1 if the chart's copies are stale (for CI)
set -euo pipefail
cd "$(dirname "$0")/.."

chart=charts/signal-lab/files
check=false
[ "${1:-}" = "--check" ] && check=true

stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
mkdir -p "$stage/collector" "$stage/grafana/dashboards"

cp deploy/collector/base.yaml "$stage/collector/base.yaml"
for f in plugins/backends/*/collector.yaml; do
  id=$(basename "$(dirname "$f")")
  [ "$id" = "base" ] && { echo "a backend may not be called 'base'" >&2; exit 1; }
  cp "$f" "$stage/collector/$id.yaml"
done
for f in plugins/backends/*/grafana/dashboards/*.json; do
  [ -f "$f" ] && cp "$f" "$stage/grafana/dashboards/"
done
touch "$stage/grafana/dashboards/.gitkeep"

if $check; then
  if diff -r "$stage" "$chart" >/dev/null 2>&1; then
    echo "chart files are in sync"
  else
    diff -r "$stage" "$chart" || true
    echo "chart files are stale: run scripts/sync-chart.sh" >&2
    exit 1
  fi
  exit 0
fi

rm -rf "$chart/collector" "$chart/grafana"
mkdir -p "$chart"
cp -R "$stage/collector" "$stage/grafana" "$chart/"
echo "synced $(ls "$chart/collector" | wc -l | tr -d ' ') collector configs into $chart/collector"
