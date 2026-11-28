---
title: Filtering on fields
summary: Every OpenTelemetry attribute is a field. Filter on service.name and severity instead of searching the message.
kind: query
minutes: 6
concepts: [field filter, exact match, service.name, severity_text, resource attributes]
assumes: [LogsQL word filters and _time]
query:
  backend: victorialogs
  language: logsql
  range_s: 900
  examples:
  - {label: One service, query: '_time:5m service.name:=payments'}
  - {label: WARN and above, query: '_time:15m severity_number:>=13'}
  - {label: Field names in use, query: '_time:5m | field_names'}
checks:
- id: shape
  type: query
  title: Filter on the `service.name` and severity fields
  must_include: [service.name, severity]
  expect:
    rows: {min: 1}
    columns: [service.name, severity_text]
  success: Field filters, not text search.
  must_match:
  - {pattern: 'severity_text\s*:=?\s*ERROR|severity_number\s*:\s*>=?\s*1[7-9]', message: 'Errors only: `severity_text:=ERROR`
      (WARN is severity 13, ERROR 17).'}
  - {pattern: '_time:\s*(15m|900s)\b', message: 'The question asks about the last 15 minutes: start with `_time:15m`.'}
- {id: answer, type: query, title: checkout's `ERROR` lines from the last 15 minutes, reference: '_time:15m service.name:=checkout
    severity_text:=ERROR', hint: 'Combine `_time:15m`, `service.name:=checkout` and `severity_text:=ERROR`, with spaces between
    them.', success: 'Each one is an order that failed after its payment was declined. The order id is in the message, not
    in a field, so searching for one means a word filter: `"dc8d4704db"`.'}
hints: ['`field:value` matches a word inside the field; `field:=value` matches the whole value exactly.', 'Severity is in
    `severity_text` (`INFO`, `WARN`, `ERROR`) and `severity_number` (9, 13, 17).', 'Answer: `_time:15m service.name:=checkout
    severity_text:=ERROR`']
---

VictoriaLogs stores each OTLP log record as a set of **fields**: the
message in `_msg`, the timestamp in `_time`, and every resource and log
attribute under its OpenTelemetry name.

| Field | Where it comes from |
| --- | --- |
| `_msg` | the log body |
| `service.name`, `service.version`, `deployment.environment.name` | resource attributes |
| `severity_text`, `severity_number` | the record's severity |
| `trace_id`, `span_id` | the active span, when the line was logged inside one |
| `scope.name` | the logger name, e.g. `shop.checkout` or `httpx` |
| `app.chaos.error_rate`, ... | attributes passed with `extra={...}` |

## Field filters

Put the field name and a colon in front of any filter from the last lesson
to apply it to that field instead of `_msg`:

| Filter | Matches |
| --- | --- |
| `service.name:checkout` | the word `checkout` in `service.name` |
| `service.name:=checkout` | `service.name` is exactly `checkout` |
| `service.name:in(checkout, payments)` | one of several values |
| `service.name:~"^(check\|pay)"` | regular expression |
| `severity_number:>=13` | numeric comparison: WARN and above |
| `-service.name:=loadgen` | every service but loadgen |

Field names containing dots need no quoting.

> [!TIP]
> Filtering on a field is faster and safer than searching for a word.
> `ERROR` as a word filter also matches a message that merely mentions
> "error"; `severity_text:=ERROR` only matches what was logged at that level.

## Try it

Return every **ERROR** log line from the **checkout** service in the
**last 15 minutes**.
