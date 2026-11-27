# Signal Lab

**An interactive OpenTelemetry crash course.** Write Python with the real
OpenTelemetry SDK in your browser, watch traces, metrics and logs flow through
an OpenTelemetry Collector, and find them in real backends: Elastic,
VictoriaMetrics + Grafana, and Jaeger. Every exercise is checked against the
telemetry your code actually produces.

```text
 your code ─OTel SDK─▶ Collector ─┬─▶ Elastic (APM, Kibana, ES|QL)
   (browser editor,               ├─▶ VictoriaMetrics + Grafana (MetricsQL)
    isolated runner)              ├─▶ Jaeger
                                  └─▶ Signal Lab's live inspector (waterfall, metrics, logs)
```

- **Real tools, nothing simulated.** Code runs as `opentelemetry-instrument python main.py`, exactly as in production.
- **Instant feedback.** A live inspector shows each span, metric and log the moment the Collector forwards it, then confirms when each backend has indexed it, with a deep link.
- **Graded by telemetry.** Checks inspect what you exported ("a `client` span whose parent is `checkout`", "at most 6 series"), and failures explain what was seen.
- **Skippable by design.** Tracks → modules → lessons. Each lesson stands alone, lists what it assumes, and can be marked *I know this*.
- **Pluggable.** Backends, lesson packs and scenarios are folders. Add one without touching the core.

## Quick start

Requirements: Docker with Compose v2. The default backends (VictoriaMetrics +
Grafana, VictoriaLogs, Jaeger) run comfortably in 2 GB. Elastic is opt-in and
needs about 4 GB more.

```bash
git clone https://github.com/heknon/signal-lab && cd signal-lab
./lab up            # builds and starts everything
```

Open **http://localhost:8000**. Grafana is on `:3000`, Kibana on `:5601`, Jaeger on `:16686`.

> On Linux, Elasticsearch needs `sudo sysctl -w vm.max_map_count=262144`.

### Choose your backends

```bash
./lab backends                        # list plugins (● = enabled)
./lab use victoriametrics victorialogs jaeger   # the default
./lab use elastic victoriametrics               # add Elastic
./lab up
```

`./lab use` rewrites three lines in `.env` (`SIGNAL_LAB_BACKENDS`, `COMPOSE_FILE`,
`COLLECTOR_CONFIGS`), so plain `docker compose up` works too.

| Command | |
|---|---|
| `./lab up` / `down` / `reset` | start, stop, stop and delete data |
| `./lab status` / `logs [svc]` | health and logs |
| `./lab dev` | run the API and shop on your machine, without Docker |

## The course

| Track | Needs | What you learn |
|---|---|---|
| **OpenTelemetry Foundations** | any backend | spans, nesting, attributes and events, errors, semantic conventions, links, auto-instrumentation, HTTP and queue propagation, baggage, counters, histograms, gauges, cardinality, structured logs, log correlation, manual SDK setup, sampling, views, Collector pipelines |
| **Metrics with VictoriaMetrics & Grafana** | `victoriametrics` | MetricsQL from selectors to `histogram_quantile`, error ratios, building dashboards, finding a slow service |
| **Investigating with Elastic** | `elastic` | Kibana APM, the service map, errors, ES\|QL, dashboards and alerts |

Lessons come in four kinds: **code** (Python, graded on exported telemetry),
**query** (MetricsQL or ES|QL against live data, graded against a reference
query), **quiz**, and **hands-on tasks** in Grafana or Kibana, verified
through their APIs.

The **Signal Shop** scenario (storefront → checkout → inventory/payments, plus
a load generator) provides realistic background traffic. The *Scenario*
drawer lets you inject latency and errors into any service.

## Deploy on Kubernetes

```bash
helm install signal-lab charts/signal-lab
kubectl port-forward svc/signal-lab 8000:8000
```

VictoriaMetrics + Grafana and Jaeger are bundled and enabled by default;
Elastic is opt-in (`--set backends.elastic.enabled=true`), and every backend
can point at an existing installation instead (`mode: external`). See
[`charts/signal-lab/README.md`](charts/signal-lab/README.md).

## Architecture

| Component | Role |
|---|---|
| `lab` | FastAPI app serving the UI, lessons, the check engine and an OTLP/HTTP **tap** that feeds the live inspector |
| `runner` | Executes learner code with the OTel SDK. Separate container: read-only filesystem, no capabilities, resource limits, and (on Kubernetes) a NetworkPolicy |
| `collector` | OpenTelemetry Collector Contrib. `deploy/collector/base.yaml` plus one fragment per enabled backend |
| `storefront`, `checkout`, `inventory`, `payments`, `loadgen` | The Signal Shop scenario, auto-instrumented |
| backends | Defined by plugins in `plugins/backends/` |

Telemetry is attributed to a run through the `signal_lab.run_id` resource
attribute. Spans from shop services join a learner's run by trace id, so a
trace that crosses into the shop shows up whole.

```text
plugins/
  backends/<id>/    plugin.yaml · adapter.py · compose.yaml · collector.yaml
  lessons/<id>/     pack.yaml · <lesson>/lesson.md · starter.* · solution.*
  scenarios/<id>/   plugin.yaml · service code
server/signal_lab/  API, runner, OTLP decoding, check engine, plugin loader
web/                React + Vite UI (Bun)
charts/signal-lab/  Helm chart
deploy/collector/   Collector base config
```

## Extending it

See **[docs/plugins.md](docs/plugins.md)** for lesson packs, check types,
backend plugins and scenarios. In short:

- **A lesson** is a folder with `lesson.md` (front matter + Markdown), `starter.py` and `solution.py`.
  With Compose, lesson files are mounted and hot-reloaded, so edit and refresh.
- **A backend** is a folder with `plugin.yaml`, a Collector fragment, a Compose
  file and an optional `adapter.py` (health, "did my trace arrive?", queries, deep links).

Test every lesson against a running lab:

```bash
python3 scripts/test_lessons.py            # or: python3 scripts/test_lessons.py otel-core/counters
```

## Developing

```bash
python3 -m venv .venv && .venv/bin/pip install -r server/requirements.txt
cd web && bun install && bun run build && cd ..
./lab dev                         # API on :8000 (serves web/dist) + shop services
cd web && bun run dev             # optional: Vite on :5173 with hot reload, proxied to :8000
```

Building the image behind a TLS-intercepting proxy:
`docker build --secret id=ca_bundle,src=/path/to/ca.pem -t signal-lab:local .`

## Security

Signal Lab runs arbitrary Python submitted through the browser. The runner is
isolated (separate container, non-root, read-only root filesystem, dropped
capabilities, CPU/memory/PID limits, run timeout), but treat a deployment
like a shared CI runner: keep it on a trusted network or behind
authentication. Set `SIGNAL_LAB_RUNS_ENABLED=false` for a read-only demo. The
bundled Elastic and Grafana have security disabled for local learning; use
`mode: external` with real credentials for anything shared.

## License

MIT
