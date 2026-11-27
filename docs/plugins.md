# Writing plugins

Everything course-specific in Signal Lab is a plugin: a folder under
`plugins/`. The core never names a backend, a lesson or a service.

```text
plugins/
  lessons/<pack>/        a track of lessons
  backends/<id>/         somewhere telemetry goes, and how to query it
  scenarios/<id>/        services learners interact with
```

With Docker Compose the `plugins/` folder is mounted into the lab, and lesson
files are hot-reloaded (`SIGNAL_LAB_RELOAD=true`), so edit a lesson and
refresh the page. Backend and scenario changes need `./lab up`.

---

## Lesson packs

### `pack.yaml`

```yaml
id: my-pack                 # unique; lesson ids are "<pack>/<lesson-folder>"
title: My track
description: One or two sentences shown on the course page.
order: 40                   # position on the course page
icon: radio                 # radio | gauge | search | database | boxes
requires:                   # optional: the track is shown as locked without these
  backends: [victoriametrics]
  capabilities: [metrics]
modules:
  - id: basics
    title: Basics
    description: What this module covers.
    assumes: [Python logging]          # shown so people can decide to skip it
    lessons: [first-lesson, second-lesson]   # folder names, in order
```

Design for skipping: a module should be a coherent topic, and **every lesson
must stand alone**, with complete starter code that never depends on an
earlier lesson's work.

### A lesson folder

```text
first-lesson/
  lesson.md        front matter + Markdown body
  starter.py       what the editor opens with   (.metricsql / .esql for query lessons)
  solution.py      used by "Solution" and by scripts/test_lessons.py
```

### Front matter

```yaml
---
title: Your first span
summary: One line, shown under the title and in lists.
kind: code              # code | collector | query | quiz | task | read
minutes: 5
concepts: [span, tracer]      # searchable in the command palette
assumes: [Basic Python]       # what you should know already
runtime:                      # code lessons
  service: hello-otel         # OTEL_SERVICE_NAME for the run
  auto_instrument: true       # false = plain `python main.py` (configure the SDK yourself)
  timeout: 20
  env: {MY_VAR: value}        # extra environment variables
settle_s: 6                   # max seconds to wait for telemetry after exit
tools: ["elastic:apm", "victoriametrics:explore"]   # deep links: "<backend>:<link id>"
scenario:                     # applied when the lesson opens
  chaos: {inventory: {latency_ms: 700, error_rate: 0.1}}
  load: 4                     # requests/second from the load generator
  note: This lesson slowed one service down. Find it.
hints:
  - Revealed one at a time.
checks: [...]                 # see below
---
```

Body Markdown supports GitHub-flavoured Markdown, highlighted code blocks
(`python`, `yaml`, `promql`/`metricsql`, `esql`) and callouts:

```markdown
> [!NOTE]  > [!TIP]  > [!WARNING]
```

### Checks

Checks describe *what the telemetry should look like*, never where it's
stored, so a lesson works with any backend. Every check has an optional `id`
and a `title` (backticks render as code). Failing checks explain what was
seen, so write titles as goals: *"`checkout` carries `app.user.id`"*.

#### `span`

```yaml
- type: span
  title: A client span named GET
  where:
    name: GET                     # exact, or "~regex"
    service: checkout             # resource service.name
    kind: client                  # internal | server | client | producer | consumer
    status: error                 # unset | ok | error
    parent: root                  # root | child | any | "<parent span name>" | "~regex"
    attributes:                   # "*" = present; scalar = equal; {gt|gte|lt|lte: n}; "~regex"
      http.request.method: GET
      http.response.status_code: {gte: 200, lt: 300}
    attributes_absent: [method]
    resource: {service.version: "2.3.0"}
    events: [cache.miss]          # event names that must be present
    links: {min: 3}               # number of span links
    exception: true               # an "exception" event was recorded
    min_duration_ms: 100
  count: {min: 1, max: 3}         # default {min: 1}; an int means exactly
```

#### `trace`

Passes if **any** trace in the run satisfies all conditions:

```yaml
- type: trace
  services: {min: 3}
  spans: {min: 4}
  depth: {min: 3}
  roots: 1
  includes_services: [storefront, inventory]
```

#### `metric`

```yaml
- type: metric
  name: orders.placed             # OTLP name, as recorded
  instrument: counter             # counter | updowncounter | gauge | histogram
  unit: "{order}"
  attributes: [app.payment.method]     # present on at least one series
  attributes_absent: [user.id]
  absent_hint: Shown when an absent attribute is found.
  series: {max: 6}                # number of time series (attribute combinations)
  series_hint: Shown when the series count is off.
  value: 6                        # sum of values (counters) or counts (histograms); or {gte: 6}
  bounds: [0.01, 0.05, 0.1]       # explicit histogram bucket boundaries
  exemplars: true
```

#### `log`

```yaml
- type: log
  body: order placed              # exact, or "~regex"
  body_contains: placed
  severity: ERROR
  attributes: {app.order.id: "*"}
  correlated: true                # has trace_id + span_id (false = has none)
  count: {min: 1}                 # {max: 0} to assert that nothing matches
```

#### `output` and `exit`

```yaml
- type: output
  contains: "baggage"             # or regex: "^done$"
- type: exit                      # the program exited with code 0
```

#### `query` (query lessons)

```yaml
query:
  backend: victoriametrics        # any enabled backend with a query adapter
  language: metricsql             # metricsql | esql | logsql
  range_s: 900
  examples: [{label: "Request rate", query: "sum(rate(http_server_request_duration_seconds_count[1m]))"}]
checks:
  - type: query
    title: p95 latency per service
    must_include: [histogram_quantile]          # substrings the learner's query must contain
    reference: >-                               # evaluated at the same instant; results compared
      histogram_quantile(0.95, sum by (le, service_name) (rate(http_server_request_duration_seconds_bucket[5m])))
    tolerance: 0.02                             # relative tolerance for values
    value_columns: [count]                      # non-"value" numeric columns (ES|QL)
    ignore_columns: []
    expect: {rows: {min: 1}, columns: [service.name]}
    hint: Shown when the result differs.
```

#### Collector lessons

`kind: collector` lessons have the learner edit a Collector config instead of
Python. The folder holds `starter.yaml`, `solution.yaml` and a read-only
`traffic.py`. On each run, the runner validates the config, starts a slim
Collector built from `deploy/collector/builder.yaml`, sends `traffic.py`'s
telemetry through it, waits `collector.settle_s`, then shuts it down so
buffers flush. The learner's file is merged with a base config that provides
the `otlp` receiver and the `otlphttp/lab` exporter (the inspector). Grade the
output with ordinary `span` / `metric` / `log` checks.

```yaml
kind: collector
filename: collector.yaml
collector: {settle_s: 3}
```

#### Quizzes

```yaml
kind: quiz
quiz:
  questions:
    - id: q1
      prompt: Which service is slow?      # backticks render as code
      options: [{id: a, label: "`inventory`"}, {id: b, label: "`payments`"}]
      answer: a                           # or [a, b] with multiple: true
      multiple: false
      explanation: Shown when correct.
      hint: Shown when wrong.
    - id: q2
      prompt: What's the error message?
      input: text                         # free text, compared case-insensitively
      answer: card declined
```

Answers stay on the server.

#### `backend` (hands-on tasks)

Delegated to a backend adapter's `verify()`:

```yaml
kind: task
tools: ["victoriametrics:dashboards"]
checks:
  - type: backend
    backend: victoriametrics
    verify: grafana_dashboard
    title_contains: My shop
    panel_expr_contains: [histogram_quantile, "rate("]
    variables: [service]
```

Built-in verifications: `grafana_dashboard` (victoriametrics),
`kibana_dashboard` and `kibana_rule` (elastic).

### Testing lessons

```bash
python3 scripts/test_lessons.py my-pack           # or a single lesson id
```

For each code lesson the solution must pass every check, and the starter
must fail at least one. Query lessons run their solution.

---

## Backend plugins

```text
plugins/backends/<id>/
  plugin.yaml       manifest (required)
  collector.yaml    Collector fragment: exporters + pipelines
  compose.yaml      services to run it locally (+ env for the lab service)
  adapter.py        optional Python adapter
```

### `plugin.yaml`

```yaml
id: tempo
title: Grafana Tempo
vendor: Grafana Labs
description: Shown on the course and stack pages.
color: "#F46800"
capabilities: [traces]             # traces | metrics | logs
query_languages: [traceql]
components:                        # health is reported per component
  - {id: tempo, title: Tempo, role: Trace storage}
settings:                          # resolved from env vars, with defaults
  tempo_url:        {env: TEMPO_URL, default: "http://tempo:3200"}
  tempo_public_url: {env: TEMPO_PUBLIC_URL, default: "http://localhost:3200"}
  api_token:        {env: TEMPO_TOKEN, default: "", secret: true}   # never sent to the browser
links:                             # deep links; {placeholders} come from settings and runtime values
  - {id: ui, label: Tempo, url: "{tempo_public_url}"}
  - {id: trace, label: Open in Tempo, url: "{tempo_public_url}/trace/{trace_id}"}
proxy:                             # optional read-only passthrough at /api/proxy/<id>/...
  target: tempo_url
  allow: ["api/search"]
```

A link with id `trace` is used by the inspector's "Open in …" buttons.

### `collector.yaml`

Use names that can't collide with other plugins: `otlp/<id>`,
`traces/<id>`. The Collector merges every `--config` file it's given, so a
fragment only adds its own exporters and pipelines. Read endpoints from
environment variables with defaults, so the Helm chart can override them:

```yaml
exporters:
  otlp/tempo:
    endpoint: ${env:TEMPO_OTLP_ENDPOINT:-tempo:4317}
    tls: {insecure: true}
service:
  pipelines:
    traces/tempo:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [otlp/tempo]
```

### `adapter.py`

Subclass `signal_lab.backends.BackendAdapter` as `Adapter`. Every method is
optional:

| Method | Used for |
|---|---|
| `health()` | status dots: `{component_id: {"ok": bool, "detail": str}}` |
| `find_trace(trace_id)`, `find_metric(name, service)`, `find_logs(run_id)` | "arrived in &lt;backend&gt;" confirmations after a run |
| `query(language, query, at_ms=, range_s=)` | query lessons, returns `QueryResult(columns, rows, series)` |
| `suggest(language, kind, prefix)` | autocomplete values |
| `link(kind, params)` | deep links that need more than a URL template |
| `verify(check, context)` | `type: backend` checks, returns `Verdict(passed, detail)` |

`self.client` is a shared `httpx.AsyncClient`; `self.settings` holds the
resolved settings.

### Enabling it

```bash
./lab use tempo victoriametrics && ./lab up
```

For Kubernetes, add the fragment to `charts/signal-lab/files/collector/` with
`scripts/sync-chart.sh` and add values for the new backend.

---

## Scenarios

`plugins/scenarios/<id>/plugin.yaml` describes services the lab can show and
control:

```yaml
id: shop
title: Signal Shop
settings:
  storefront: {env: SHOP_STOREFRONT_URL, default: "http://storefront:8080"}
services:
  - {id: storefront, url: "{storefront}", calls: [checkout, inventory], description: Public API}
  - {id: loadgen, url: "{loadgen}", role: loadgen}
runner_env:                       # injected into learner code
  SHOP_URL: "{storefront}"
```

Each service exposes `GET /_stats` (`{chaos, requests, errors, p50_ms, p95_ms}`)
and `POST /_chaos` (`{latency_ms, error_rate}`). The load generator also
exposes `POST /_load` (`{rps}`). That's the whole contract: write a scenario in
any language.
