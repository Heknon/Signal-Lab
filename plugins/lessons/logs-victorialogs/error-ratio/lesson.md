---
title: Error ratio per service
summary: Count errors and totals in one stats pipe with count() if, then divide them with math.
kind: query
minutes: 7
concepts: [conditional stats, count() if, math pipe, ratio]
assumes: [LogsQL stats by]
query:
  backend: victorialogs
  language: logsql
  range_s: 900
  examples:
  - {label: Errors and totals per service, query: '_time:15m | stats by (service.name) count() if (severity_text:=ERROR) errors,
      count() total'}
  - {label: checkout's order failure ratio, query: '_time:15m scope.name:=shop.checkout | stats count() if (severity_text:=ERROR)
      failed, count() if (placed) placed | math failed / (failed + placed) as failure_ratio'}
checks:
- id: shape
  type: query
  title: Compute an `error_ratio` per service with `math`
  must_include: [count(), if, math, service.name]
  expect:
    rows: {min: 2}
    columns: [service.name, error_ratio]
  success: A ratio per service, between 0 and 1.
  mistakes:
  - {pattern: count\(\)\s*if\s*\(\s*-, message: 'Divide the errors by all log lines (`count()`), not only by the non-error
      ones.'}
- id: answer
  type: query
  title: Share of each service's log lines at ERROR, last 15 minutes
  reference: _time:15m | stats by (service.name) count() if (severity_text:=ERROR) errors, count() total | math errors / total
    as error_ratio | fields service.name, error_ratio
  value_columns: [error_ratio]
  ignore_columns: [errors, total]
  expect:
    columns: [service.name, error_ratio]
  tolerance: 0.05
  hint: 'Count ERROR lines and all lines in the same `stats by (service.name)`, divide with `| math errors / total as error_ratio`,
    and end with `| fields service.name, error_ratio`. Don''t filter the lines before `stats`: the total needs all of them.'
  success: 'About 1% for checkout and storefront, 0 for the rest. The total includes every httpx line, so this is a share
    of log volume, not of requests: compare it over time, not with your SLO.'
hints: ['`count() if (<filter>) name` only counts the entries in the group that match the filter.', '`math a / b as c` adds
    a field `c` to each row.', 'Answer: `_time:15m | stats by (service.name) count() if (severity_text:=ERROR) errors, count()
    total | math errors / total as error_ratio | fields service.name, error_ratio`']
---

An error count on its own says little: 20 errors is bad for a service that
logged 25 lines and noise for one that logged 20,000. Divide by the total
and you can compare services, and the same service at different times.

## Two counts in one pass

`stats` can compute several results per group, and `if (...)` restricts a
result to the entries that match a filter:

```logsql
_time:15m
| stats by (service.name)
    count() if (severity_text:=ERROR) errors,
    count() total
```

## Dividing

The `math` pipe computes new fields from existing ones, row by row:

```logsql
| math errors / total as error_ratio
```

It supports `+ - * / %`, `round(x, 0.01)`, `abs`, `min`, `max` and more. Then
`fields service.name, error_ratio` keeps just the answer.

> [!TIP]
> A ratio is only as good as its denominator. checkout's own logger writes
> exactly one line per order, `placed` or `payment failed`, so filtering to
> `scope.name:=shop.checkout` gives a real order failure ratio (second
> example). Over all lines, the httpx chatter dilutes it.

## Try it

For **each service**, return the share of its log lines from the last
**15 minutes** that are at **ERROR**, as `error_ratio` between 0 and 1.
Return only `service.name` and `error_ratio`.
