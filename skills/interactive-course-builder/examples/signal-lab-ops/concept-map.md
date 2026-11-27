# Concept map: operating the Signal Lab shop

A worked example of a phase 1 artifact. It targets this repository, so the
tools can check it: `python tools/check_sources.py --repo ../.. examples/signal-lab-ops/concept-map.md`.

## Subject

- **Target:** Signal Lab, this repository at its current commit; the shop scenario and the lab server.
- **Audience:** engineers who will run Signal Lab for a team and write lessons for it. They know Python and Docker.
- **Evidence used:** `git log` over `plugins/` and `server/` (most-changed files), the incident test script, and the bugs fixed while building it (pool never saturating, retries tied, spanmetrics not flushing).

## Inventory

| Component | Kind | Artifacts |
|---|---|---|
| Shop scenario | services | `plugins/scenarios/shop/app.py`, `plugins/scenarios/shop/plugin.yaml` |
| Check engine | library | `server/signal_lab/checks.py#evaluate` |
| OTLP tap | HTTP endpoint | `server/signal_lab/otlp.py#decode_traces` |
| Experiments and incidents | engine | `server/signal_lab/drills.py#Drills` |
| Collector config | config | `deploy/collector/base.yaml` |
| Lesson packs | content | `plugins/lessons/otel-core/pack.yaml` |

## Concepts

| id | Concept | Freq | Blast | Confusion | Priority | Artifacts | Confusion evidence |
|---|---|---|---|---|---|---|---|
| shop-topology | Which shop service calls which | 5 | 2 | 2 | 9 | `plugins/scenarios/shop/plugin.yaml` | |
| chaos-reset | Faults are cleared by reset and expire by TTL | 4 | 3 | 2 | 9 | `plugins/scenarios/shop/app.py#chaos_active` | |
| retries | Checkout retries payments with no backoff | 3 | 5 | 4 | 12 | `plugins/scenarios/shop/app.py:311` | Retry storms look like a payments outage |
| pool-size | Inventory's DB pool queues requests when exhausted | 3 | 5 | 4 | 12 | `plugins/scenarios/shop/app.py#pool_state` | Pool never saturated until DB latency was raised |
| memory-leak | Leak until an OOM-style restart | 2 | 4 | 3 | 9 | `plugins/scenarios/shop/app.py#leak_mb_per_min` | Restarts hide the trend |
| label-cardinality | A user-id label multiplies series | 3 | 4 | 3 | 10 | `plugins/scenarios/shop/app.py#label_user_id` | Series count grows without any error |
| check-engine | How checks match spans, metrics and logs | 4 | 3 | 3 | 10 | `server/signal_lab/checks.py#check_span` | Exact-match checks rejected valid answers |
| run-attribution | Telemetry is tied to a run by a resource attribute | 4 | 3 | 3 | 10 | `server/signal_lab/otlp.py#attrs` | Shop spans arrive without the run id |
| collector-config | Base config merged with backend fragments | 4 | 3 | 4 | 11 | `deploy/collector/base.yaml` | spanmetrics emitted nothing within a run |
| drills-abort | Experiments abort at a steady-state limit | 2 | 4 | 3 | 9 | `server/signal_lab/drills.py#_experiment` | `abort_at` direction is easy to invert |
| lesson-packs | Tracks, modules and lessons from folders | 5 | 2 | 2 | 9 | `plugins/lessons/otel-core/pack.yaml` | |
| backend-plugins | Adding a backend plugin | 3 | 2 | 2 | 7 | `plugins/backends/victoriametrics/plugin.yaml` | |
| helm-values | Chart values for bundled or external backends | 2 | 2 | 2 | 6 | `charts/signal-lab/values.yaml` | |

## Failure modes

| Concept | What breaks | Symptom | Signal that shows it |
|---|---|---|---|
| chaos-reset | A fault is left on after a lesson | The shop is slow for everyone | `metric:http.server.request.duration` on storefront |
| retries | Each failed payment is retried immediately | Payments looks overloaded; checkout errors rise | `metric:http.client.request.duration` count per checkout |
| pool-size | Pool too small for the load | Inventory latency climbs, CPU stays flat | `metric:db.client.connection.count` at its maximum |
| memory-leak | Memory grows until restart | Periodic error spikes | `metric:process.memory.usage` sawtooth |
| label-cardinality | `app.user.id` added as a metric attribute | Queries slow down, storage grows | series count per metric |
| check-engine | A check only accepts one form | Correct answers fail | the check's failure detail |
| run-attribution | Spans lack `signal_lab.run_id` | Results appear in nobody's run | the inspector stays empty |
| collector-config | A processor is missing from a pipeline | Telemetry never reaches a backend | Collector `otelcol_exporter_sent_spans` |
| drills-abort | Limit direction inverted | The experiment aborts immediately or never | the activity panel's abort reason |

## Observable surface

| Source | How to read it | Latency | Attribution |
|---|---|---|---|
| Learner stdout | runner stream | 0 s | one stream per run |
| Telemetry | OTLP tap at `/tap/v1/*` | 1–3 s | `signal_lab.run_id` resource attribute; shop spans adopted by trace id |
| Shop state | `GET /_stats` on each service | 0 s | shared on purpose |
| Backends | MetricsQL, LogsQL, ES\|QL APIs | 5–15 s | time range of the run |

## Deliberate gaps

| Concept | Reason |
|---|---|
| backend-plugins | Covered by `docs/plugins.md`; the audience runs Signal Lab rather than extends its backends |
| helm-values | Operations of the chart are documented by helm-docs; there is no realistic exercise without a cluster |
