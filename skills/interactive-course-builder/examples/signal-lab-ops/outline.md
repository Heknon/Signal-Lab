# Course outline: operating the Signal Lab shop

A worked example of a phase 2 artifact, built from the concept map next to it.

## Tracks

| Track id | Title | For whom | Requires |
|---|---|---|---|
| ops | Running the lab | people hosting Signal Lab for a team | none |
| shop | The shop under stress | lesson authors and incident designers | victoriametrics |

## Lessons

### Module: ops/content: Lessons and checks

- **Assumes:** Python, YAML
- **Skip if:** you have written a lesson pack before

| id | Title | Kind | Stage | Min | Concepts | Assumes | Sources | Learner produces | Checks observe |
|---|---|---|---|---|---|---|---|---|---|
| ops/first-pack | Add a lesson pack | task | happy | 8 | lesson-packs | nothing | `plugins/lessons/otel-core/pack.yaml` | a pack folder | the lesson appears in `/api/lessons` |
| ops/tolerant-checks | Write a check that accepts equivalent answers | code | failure | 10 | check-engine | Add a lesson pack | `server/signal_lab/checks.py#check_span` | check YAML | the starter fails and the solution passes |
| ops/run-attribution | Why a run sees no spans | quiz | failure | 5 | run-attribution | nothing | `server/signal_lab/otlp.py#attrs` | answers | answer key |
| ops/collector-fragments | Fix a merged Collector config that drops spans | config | failure | 10 | collector-config | nothing | `deploy/collector/base.yaml` | Collector YAML | spans pass through the new processor |

### Module: shop/stress: Faults and their signals

- **Assumes:** PromQL basics
- **Skip if:** you have run the shop's chaos API before

| id | Title | Kind | Stage | Min | Concepts | Assumes | Sources | Learner produces | Checks observe |
|---|---|---|---|---|---|---|---|---|---|
| shop/topology | Map the shop from its traces | query | happy | 6 | shop-topology | nothing | `plugins/scenarios/shop/plugin.yaml` | a query | call edges match the topology |
| shop/inject-and-reset | Inject a fault and clear it | task | failure | 5 | chaos-reset | Map the shop from its traces | `plugins/scenarios/shop/app.py#chaos_active` | chaos API calls | `/_stats` shows the fault, then none |
| shop/abort-limits | Set an abort limit that protects the shop | experiment | failure | 10 | drills-abort | Inject a fault and clear it | `server/signal_lab/drills.py#_experiment` | an experiment spec | the outcome is graded from the real run |
| shop/incident-retry-storm | Checkout fails, payments looks guilty | incident | capstone | 15 | retries | PromQL basics | `plugins/scenarios/shop/app.py:311` | answers and a query | live data |
| shop/incident-saturation | Inventory is slow and its CPU is idle | incident | capstone | 15 | pool-size | PromQL basics | `plugins/scenarios/shop/app.py#pool_state` | answers and a query | live data |
| shop/incident-memory-leak | Errors every few minutes | incident | capstone | 12 | memory-leak | PromQL basics | `plugins/scenarios/shop/app.py#leak_mb_per_min` | answers and a query | live data |
| shop/incident-cardinality | Dashboards are slow, nothing errors | incident | capstone | 12 | label-cardinality | PromQL basics | `plugins/scenarios/shop/app.py#label_user_id` | answers and a query | live data |

## Capstone incidents

| id | Symptom brief | Hidden fault | Fault | Misleading symptom | Signals | When / where / what | Evidence |
|---|---|---|---|---|---|---|---|
| shop/incident-retry-storm | "Checkout fails a lot, payments must be down" | `retries: 4` with a small `error_rate` on payments | `retries`, `error_rate` | payments latency rises | `metric:http.client.request.duration` | fault start; checkout; retries amplify load | `sum by (service_name) (rate(http_client_request_duration_seconds_count[1m]))` |
| shop/incident-saturation | "Inventory is slow but its CPU is idle" | `pool_size: 1` under load | `pool_size` | storefront latency | `metric:db.client.connection.count` | fault start; inventory; pool exhausted | `max by (state) (db_client_connection_count)` |
| shop/incident-memory-leak | "Random errors every few minutes" | `leak_mb_per_min: 40` | `leak_mb_per_min` | error spikes look like bad deploys | `metric:process.memory.usage` | first restart; inventory; leak then restart | `max by (service_name) (process_memory_usage_bytes)` |
| shop/incident-cardinality | "Dashboards time out, nothing errors" | `label_user_id: true` | `label_user_id` | query latency, not app latency | series count | fault start; checkout metrics; user-id attribute | `count by (__name__) ({__name__=~"app_.*"})` |

## Decisions

- The ops track has no incidents of its own: its failure modes are authoring mistakes, and the shop track's incidents exercise them.
- `backend-plugins` and `helm-values` are deliberate gaps (see the concept map).
