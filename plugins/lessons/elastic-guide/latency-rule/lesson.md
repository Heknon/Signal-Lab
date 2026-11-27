---
title: Alert on checkout latency
summary: Create an APM latency threshold rule that fires when checkout's p95 gets too slow.
kind: task
minutes: 8
concepts: [alerting rule, latency threshold, rule type]
assumes: [Kibana APM, Percentiles]
tools: ["elastic:apm"]
checks:
  - id: rule
    type: backend
    backend: elastic
    verify: kibana_rule
    title: "An APM **Latency threshold** rule named “Checkout latency”"
    name_contains: Checkout latency
    rule_type: apm.transaction_duration
hints:
  - "APM → open **checkout** → **Alerts and rules → Create threshold rule → Latency**. The service is pre-filled for you."
  - "Or: Observability → **Alerts → Manage rules → Create rule → Latency threshold**."
  - "The check looks for rule type *Latency threshold* (`apm.transaction_duration`); an Elasticsearch query rule won't count."
---

A dashboard only helps when someone looks at it. An **alerting rule** looks
for you: Kibana runs it on a schedule and creates an alert when its condition
is met.

For APM data, Kibana has ready-made rule types that understand services
and transaction types:

| Rule type | Fires when |
| --- | --- |
| **Latency threshold** | a percentile (or the average) of transaction latency exceeds a value |
| **Failed transaction rate threshold** | the share of failed transactions exceeds a value |
| **Error count threshold** | more than N errors are recorded |
| **Anomaly** | machine learning flags unusual latency or throughput (needs a license) |

## Create the rule

1. Open **Kibana APM → checkout**, then **Alerts and rules → Create
   threshold rule → Latency**.
2. Set:

   | Field | Value |
   | --- | --- |
   | Service | `checkout` |
   | Transaction type | `request` |
   | Environment | All |
   | When | 95th percentile |
   | Is above | 300 ms |
   | For the last | 5 minutes |

3. Name it **Checkout latency** and save. You can skip actions (notifications)
   for now: the alert still shows up under **Observability → Alerts**.

Then press **Check** here.

> [!TIP]
> To see it fire, add 500 ms of latency to `inventory` in the **Scenario**
> drawer. checkout waits for inventory, so its p95 crosses 300 ms within a
> few minutes. Clear the fault afterwards and watch the alert recover.

> [!NOTE]
> Normal checkout p95 is around 90 ms. A threshold a few times above normal
> avoids alerts on ordinary noise; a threshold right at normal fires all
> day and soon gets ignored.
