# Writing a subject adapter

A subject adapter connects a generic course platform to one target system. It
answers four questions:

1. **Input:** what does the learner produce?
2. **Execution:** how is it run, the way the real system runs it?
3. **Observation:** what can checks read, and how is it tied to one run?
4. **Faults:** what can be broken on purpose, reversibly?

Fill [`templates/adapter.md`](../templates/adapter.md) first, then implement
the pieces below.

## Components

| Component | Responsibility | Interface (suggested) |
|---|---|---|
| **Executor** | run learner work in the sandbox; stream output; enforce limits | `execute(submission, env, timeout) -> stream of {output, exit}` |
| **Collector / tap** | receive what the work emits and attribute it to a run | e.g. an HTTP endpoint the work sends to; a DB query filtered by run id; a temp dir |
| **Backend adapter** | talk to an external store or UI: health, "did it arrive?", queries, deep links, task verification | `health()`, `find(run)`, `query(lang, q, at, range)`, `link(kind, params)`, `verify(check)` |
| **Check types** | evaluate observations | `check(spec, observations, ctx) -> {status, detail}` |
| **Scenario** | a live system for queries, experiments and incidents | each service exposes `GET /_stats` and `POST /_chaos`, plus `POST /_load` on the traffic generator |
| **Fault catalogue** | named, parameterised, reversible faults | `{reset: true}` clears everything |

## Subjects that are not services

A library, CLI or compiler runs once per submission; there is no long-lived
system to break. Map the concepts like this:

| Concept | For a service | For a one-shot process (library, CLI) |
|---|---|---|
| Scenario | running services plus a traffic generator | a fixture the run uses: a local test server, sample files, env vars, a temp repo |
| Fault | a chaos API call | a fixture setting: a slow or failing test server, a bad env var, a corrupt input file |
| Time limit | a TTL on the fault | one run; the fixture is rebuilt for the next |
| Reset | `{"reset": true}` | delete and recreate the fixture |
| Incident timeline | faults applied at offsets during live traffic | a sequence of runs ("deploys") with the fault switched on from run N; "when" is the run or commit that introduced it |
| Evidence | a query against a backend | a command against the fixture's record (server log, output files, exit codes) |

## Plugin folder layout (Signal Lab conventions)

```text
plugins/backends/<id>/
  plugin.yaml       id, title, capabilities, query_languages, components, settings (env + defaults), links
  adapter.py        class Adapter(BackendAdapter): health, find_*, query, suggest, link, verify
  compose.yaml      services to run it locally, plus env for the lab
  collector.yaml    how telemetry or data reaches it (if relevant)
plugins/scenarios/<id>/
  plugin.yaml       services (id, url, calls, role), runner_env injected into learner code
  app.py            the services, with /_stats and /_chaos
```

## Checklist for a new subject

- [ ] The executor runs learner work with the subject's **real** CLI, SDK or entry point.
- [ ] Every run gets an id, and every observation carries it.
- [ ] Observations appear within a few seconds. Long ingestion delays are
      handled with `pending` and a settle time.
- [ ] Each fault is reversible, has a time limit, and is cleared by `reset`.
- [ ] Faults survive a restart only if that is the point (for example a deploy or a crash loop).
- [ ] Health checks exist for every component, so the UI can show what's down.
- [ ] Deep links take the learner from a result to the same thing in the
      subject's own UI.
- [ ] One spike script proves input → execution → observation → fault before anything else is built.

## Examples of adapters

| Subject | Input | Execution | Observation | Faults |
|---|---|---|---|---|
| OpenTelemetry (Signal Lab) | Python, Collector YAML, MetricsQL/LogsQL/ES\|QL | `opentelemetry-instrument python`, `otelcol --config` | OTLP tap by `run_id`; backend APIs | latency, errors, retries, pool size, deploys, leaks, cardinality |
| A web framework | handlers, middleware, config | the framework's dev server in a sandbox | HTTP responses from a test client; DB state | slow DB, failing dependency, bad config value |
| A database | SQL, schema migrations, config | `psql` against a per-run schema | query results, `EXPLAIN`, system views | missing index, lock contention, bloat, low memory |
| Kubernetes | manifests, `kubectl` commands | a per-run namespace on a disposable cluster | API objects, events, pod status | crashlooping image, bad probe, quota, node pressure |
| A message broker | producer and consumer code, topology config | client libraries against a broker | consumed messages, lag, broker metrics | slow consumer, partition skew, broker restart |
