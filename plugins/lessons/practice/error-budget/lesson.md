---
title: Error budgets
summary: Compute how much of a 99% SLO's error budget the storefront has left, and how teams use that number to decide what
  to do next.
kind: query
minutes: 10
concepts: [error budget, SLO, budget remaining, increase(), release policy]
assumes: [SLIs and SLOs, increase() on counters]
tools: ['victoriametrics:explore']
query:
  backend: victoriametrics
  language: metricsql
  range_s: 3600
  examples:
  - {label: Availability SLI over 1h, query: 'sum(increase(http_server_request_duration_seconds_count{service_name="storefront",
      http_response_status_code!~"5.."}[1h])) / sum(increase(http_server_request_duration_seconds_count{service_name="storefront"}[1h]))'}
  - {label: Failed requests in the last hour, query: 'sum(increase(http_server_request_duration_seconds_count{service_name="storefront",
      http_response_status_code=~"5.."}[1h]))'}
  - {label: Allowed failures at 99%, query: 'sum(increase(http_server_request_duration_seconds_count{service_name="storefront"}[1h]))
      * 0.01'}
checks:
- id: shape
  type: query
  title: Use a 1-hour window and divide
  must_include: ['[1h]', 5.., /]
  expect: {rows: 1}
- id: answer
  type: query
  title: Share of the storefront's 1-hour error budget left, at a 99% SLO
  reference: 1 - (1 - (sum(increase(http_server_request_duration_seconds_count{service_name="storefront", http_response_status_code!~"5.."}[1h]))
    / sum(increase(http_server_request_duration_seconds_count{service_name="storefront"}[1h])))) / (1 - 0.99)
  tolerance: 0.02
  hint: Error ratio = 1 - SLI. Budget used = error ratio / 0.01. Remaining = 1 - used.
  success: 1 means untouched, 0 means spent, below 0 means overspent. With chaos experiments running on the shared shop, a
    negative number here is quite possible.
  alternatives: ['1 - (1 - (sum(rate(http_server_request_duration_seconds_count{service_name="storefront", http_response_status_code!~"5.."}[1h]))
      / sum(rate(http_server_request_duration_seconds_count{service_name="storefront"}[1h])))) / (1 - 0.99)']
hints: [The allowed error ratio for a 99% SLO is `1 - 0.99 = 0.01`., Wrap the starter in `1 - (1 - (...)) / (1 - 0.99)`.]
---

An SLO of 99% says 1% of requests may fail. That 1% is the **error
budget**: an amount of unreliability you have agreed to accept and can
spend.

```text
allowed error ratio = 1 - SLO                       # 0.01 for 99%
budget used         = observed error ratio / allowed error ratio
budget remaining    = 1 - budget used               # 1 = untouched, 0 = spent, < 0 = overspent
```

Over 30 days at 99%, the budget is 1% of the month's requests, or 7.2
hours of total outage. A day with 5% errors spends five days' worth.

## How budgets drive decisions

The point of the budget is that it replaces an argument with a number.

- **Budget left:** ship features, run experiments, take planned risks such
  as migrations or chaos tests. Unused budget is reliability nobody asked for.
- **Budget running low:** slow down risky changes, prioritise the
  reliability work the last incidents pointed at.
- **Budget spent:** a release freeze for anything but fixes, as agreed in
  advance with product, until the window recovers.

Agreeing on that policy *before* the budget runs out is what makes it work.

> [!NOTE]
> Real SLOs use a 28- or 30-day window, either rolling or calendar-aligned.
> The lab's metrics only go back a few hours, so this lesson uses one hour.
> The arithmetic is the same: replace `[1h]` with `[30d]`.

## Try it

The starter is the storefront's availability SLI over the last hour. Turn
it into the **share of the error budget remaining** for a 99% SLO.
