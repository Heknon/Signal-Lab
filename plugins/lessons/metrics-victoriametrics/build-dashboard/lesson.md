---
title: Build a dashboard
summary: Build a Grafana dashboard with a service variable, a request-rate panel and a p95 latency panel.
kind: task
minutes: 12
concepts: [Grafana dashboard, panel, template variable, $__rate_interval]
assumes: [rate() on counters, sum by, histogram_quantile]
tools: ["victoriametrics:grafana", "victoriametrics:dashboards"]
checks:
  - id: dashboard
    type: backend
    backend: victoriametrics
    verify: grafana_dashboard
    title: A saved dashboard whose title contains “My shop”, with at least 2 panels
    title_contains: My shop
    min_panels: 2
  - id: latency
    type: backend
    backend: victoriametrics
    verify: grafana_dashboard
    title: A latency panel using `histogram_quantile` over `rate(`
    title_contains: My shop
    panel_expr_contains: ["histogram_quantile", "rate("]
  - id: variable
    type: backend
    backend: victoriametrics
    verify: grafana_dashboard
    title: A `service` variable that the panels use as `$service`
    title_contains: My shop
    variables: [service]
    panel_expr_contains: ["$service"]
hints:
  - "Variables live under **Dashboard settings → Variables**. Use type *Query* and `label_values(http_server_request_duration_seconds_count, service_name)`."
  - "Reference the variable in a query as `service_name=~\"$service\"`. `=~` keeps it working when you enable *Multi-value* or *Include All*."
  - "Nothing is checked until you **Save dashboard**."
  - "Stuck? The provisioned **Signal Shop · overview** dashboard has the same panels. Open a panel's menu → *Edit* to see its queries."
---

Explore is for questions you have now; a **dashboard** is for questions you
will have again. You'll build a small one for the shop, with a drop-down to
pick the service.

## 1. Create it

In Grafana, go to **Dashboards → New → New dashboard**, then open
**Settings** (the gear) and name it **My shop**. Save.

## 2. Add a `service` variable

Under **Settings → Variables → Add variable**:

| Field | Value |
| --- | --- |
| Type | Query |
| Name | `service` |
| Data source | VictoriaMetrics |
| Query | `label_values(http_server_request_duration_seconds_count, service_name)` |
| Multi-value, Include All option | on |

A drop-down appears at the top of the dashboard.

## 3. Request rate panel

**Add → Visualization**, switch the query editor to **Code**, and enter:

```promql
sum by (service_name) (rate(http_server_request_duration_seconds_count{service_name=~"$service"}[$__rate_interval]))
```

Set the legend to `{{service_name}}` and the unit to *requests/sec*.

## 4. p95 latency panel

Add a second panel:

```promql
histogram_quantile(0.95, sum by (le, service_name) (rate(http_server_request_duration_seconds_bucket{service_name=~"$service"}[$__rate_interval])))
```

Unit: *seconds (s)*. Then **Save dashboard** and press **Check** here.

> [!NOTE]
> `$__rate_interval` is a Grafana variable: a window that's always wide
> enough for `rate()` at the current zoom level. Prefer it to a fixed `[5m]`
> in panels.

> [!TIP]
> Want more? Add the error ratio from the earlier lesson as a third panel,
> or a **Stat** panel showing checkouts per minute:
> `sum(rate(shop_checkouts_total{outcome="ok"}[$__rate_interval])) * 60`.
