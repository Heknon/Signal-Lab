---
title: Abort conditions
summary: Watch an experiment stop itself when customers start to feel it.
kind: experiment
minutes: 8
concepts: [abort conditions, saturation, connection pools]
assumes: [Your first experiment]
tools: ["victoriametrics:explore"]
experiment:
  hypothesis: Storefront p95 stays under 1 s when the inventory database pool shrinks to 1 connection under 12 requests per second.
  steady_state:
    backend: victoriametrics
    query: histogram_quantile(0.95, sum by (le) (rate(http_server_request_duration_seconds_bucket{service_name="storefront"}[30s])))
    label: storefront p95 (s)
    threshold: 1.0
    abort_at: 1.5
  baseline_s: 30
  inject: {inventory: {pool_size: 1}}
  load: 12
  duration_s: 90
  recovery_s: 40
quiz:
  questions:
    - id: outcome
      kind: outcome
      prompt: How did the experiment end?
      options:
        - {id: held, label: "Hypothesis held"}
        - {id: rejected, label: "Hypothesis rejected, but ran to the end"}
        - {id: aborted, label: "Aborted: the abort condition fired and the fault was removed"}
      explanation: The abort line is the promise you make before starting. It fired, and the lab removed the fault on its own.
    - id: signal
      prompt: Which metric shows the *cause* rather than the symptom? Check in Grafana.
      options:
        - {id: pending, label: "`db_client_connection_pending_requests` for inventory"}
        - {id: latency, label: "Storefront p95 latency"}
        - {id: errors, label: "Storefront error rate"}
      answer: pending
      explanation: Requests queued for a connection. That's saturation, the S in USE, and it rises before latency does.
    - id: errors
      prompt: Did the shop return errors during the fault?
      options:
        - {id: no, label: "Barely: requests waited instead of failing"}
        - {id: yes, label: "Yes, most requests failed"}
      answer: "no"
      explanation: Saturation shows up as latency first. Alerting on errors alone would have missed this.
---

Some experiments go wrong in ways you didn't expect. The **abort condition**
is the line you agree on *before* starting: cross it and the fault is
removed, no discussion.

This experiment shrinks the inventory service's database connection pool to
**1** while traffic rises. Requests start queueing for a connection, and
latency climbs everywhere upstream.

The steady state is storefront p95. The hypothesis limit is 1 s, and the
abort condition is 1.5 s. Watch what happens to the red line.

> [!NOTE]
> The experiment also raises traffic through the load generator. While it's
> running, open Grafana and look at
> `db_client_connection_pending_requests` and `db_client_connection_count`.
