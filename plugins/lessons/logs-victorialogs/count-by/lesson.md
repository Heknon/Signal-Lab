---
title: Counting with stats
summary: Pipe matching logs into stats to count them per service, per severity, or per any other field.
kind: query
minutes: 6
concepts: [pipes, stats, count, by, sort]
assumes: [LogsQL field filters]
query:
  backend: victorialogs
  language: logsql
  range_s: 900
  examples:
  - {label: All lines in 15 minutes, query: '_time:15m | stats count() logs'}
  - {label: By severity, query: '_time:15m | stats by (severity_text) count() logs'}
  - {label: Busiest loggers, query: '_time:15m | stats by (service.name, scope.name) count() logs | sort by (logs desc)'}
checks:
- id: shape
  type: query
  title: Use `stats by (service.name)` with a column named `logs`
  must_include: [stats, service.name]
  expect:
    rows: {min: 2}
    columns: [service.name, logs]
  success: One row per service.
  mistakes:
  - {pattern: count_uniq, message: 'Count log lines with `count()`. `count_uniq(trace_id)` counts requests, which only matches
      while each one logs once.'}
  must_match:
  - {pattern: '_time:\s*(15m|900s)\b', message: 'The question asks about the last 15 minutes: start with `_time:15m`.'}
- id: answer
  type: query
  title: WARN and ERROR lines per service, last 15 minutes
  reference: _time:15m severity_text:in(WARN, ERROR) | stats by (service.name) count() logs
  value_columns: [logs]
  tolerance: 0.05
  hint: Filter first (`severity_text:in(WARN, ERROR)` or `severity_number:>=13`), then `| stats by (service.name) count()
    logs`. Group by `service.name` only.
  success: payments only warns (card declines); checkout and storefront log the errors that follow. inventory hardly logs
    at all in normal traffic.
hints: [Everything before the first `|` is the filter; each `|` then transforms the results., '`count() logs` names the result
    column `logs`. Without a name it''s called `count(*)`.', 'Answer: `_time:15m severity_text:in(WARN, ERROR) | stats by
    (service.name) count() logs`']
---

Filters pick log entries. **Pipes**, written after `|`, turn them into
something else. The one you'll use most is `stats`:

```logsql
_time:15m | stats by (severity_text) count() logs
```

| Part | Meaning |
| --- | --- |
| `stats by (severity_text)` | one result row per distinct `severity_text` |
| `count()` | number of entries in each group |
| `logs` | the name of the result column |

Group by several fields with `by (service.name, severity_text)`, and compute
several results at once: `count() logs, count_uniq(trace_id) traces`.
Other functions include `sum`, `avg`, `min`, `max`, `quantile(0.95, field)`
and `count_uniq`.

## More pipes

| Pipe | Does |
| --- | --- |
| `sort by (logs desc)` | order the rows |
| `limit 10` | keep the first 10 |
| `fields _time, _msg` | keep only these fields |
| `field_names` | list the fields that occur, with counts |

> [!NOTE]
> Without a `by` clause, `stats` returns a single row for everything that
> matched.

## Try it

Count the log lines at **WARN or ERROR** per **service** over the last
**15 minutes**. Name the count `logs`.
