---
title: A Kibana dashboard for the shop
summary: Build a "Shop health" dashboard from ES|QL panels in Kibana.
kind: task
minutes: 12
concepts: [Kibana dashboard, ES|QL visualization, Lens]
assumes: [ES|QL STATS and EVAL]
tools: ["elastic:esql", "elastic:discover"]
checks:
  - id: dashboard
    type: backend
    backend: elastic
    verify: kibana_dashboard
    title: A saved Kibana dashboard titled “Shop health”
    title_contains: Shop health
hints:
  - "Kibana → **Dashboards → Create dashboard → Add panel → ES|QL** lets you paste a query and pick a chart type."
  - "A panel only shows up after you **Save** the dashboard itself (top right), not just the panel."
  - "Name it exactly `Shop health` (more words after it are fine, like `Shop health (mine)`)."
---

Dashboards in Kibana are built from **panels**. Each panel is a
visualization over a query. You'll make three, all from ES|QL, so you can
reuse what you've learned.

## 1. Create the dashboard

Kibana → **Dashboards → Create dashboard**. Set the time picker to the last
15 minutes and turn on auto-refresh (every 10 seconds is plenty).

## 2. Add panels

For each, choose **Add panel → ES|QL**, paste the query, pick a chart type
in the editor that opens, and **Apply**. Kibana's time picker filters ES|QL
panels for you, so the queries need no time condition.

**Transactions per minute, by service** (line or bar chart):

```esql
FROM traces-apm*
| WHERE processor.event == "transaction"
| STATS transactions = COUNT(*) BY minute = BUCKET(@timestamp, 1 minute), service.name
```

**p95 latency per service, in ms** (bar chart):

```esql
FROM traces-apm*
| WHERE processor.event == "transaction"
| STATS p95_us = PERCENTILE(transaction.duration.us, 95) BY service.name
| EVAL p95_ms = ROUND(p95_us / 1000.0, 1)
| KEEP service.name, p95_ms
```

**Failure rate per service** (bar chart, or a table):

```esql
FROM traces-apm*
| WHERE processor.event == "transaction"
| EVAL failed = CASE(event.outcome == "failure", 1, 0)
| STATS failure_rate = AVG(failed) BY service.name
```

## 3. Save

**Save** the dashboard as **Shop health**, then press **Check** here.

> [!TIP]
> Prefer clicking to typing? **Create visualization** opens Lens, where you
> drag fields from a data view (Kibana creates an *APM* data view the first
> time you open the APM app). Lens and ES|QL panels mix happily on one
> dashboard.

> [!NOTE]
> For per-service views, the APM app already has curated dashboards.
> Your own dashboard earns its place when it mixes signals the APM app shows
> separately: business numbers, logs, and several services side by side.
