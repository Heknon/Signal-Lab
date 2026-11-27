---
title: All logs for a trace
summary: Use trace_id to pull every line one request wrote across services, then do it for every failed checkout at once with a subquery.
kind: query
minutes: 8
concepts: [trace_id, log correlation, in() subquery, fields]
assumes: [LogsQL field filters, Correlating logs with traces]
query:
  backend: victorialogs
  language: logsql
  range_s: 900
  examples:
    - {label: "Step 1: recent checkout errors", query: "_time:15m service.name:=checkout severity_text:=ERROR | sort by (_time desc) | limit 5 | fields _time, trace_id, _msg"}
    - {label: "Step 2: one trace (paste an id)", query: "_time:15m trace_id:=\"paste-a-trace-id\" | sort by (_time) | fields _time, service.name, severity_text, _msg"}
checks:
  - id: shape
    type: query
    title: "Filter on `trace_id` with an `in(...)` subquery"
    must_include: ["trace_id", "in("]
    expect: {rows: {min: 1}, columns: [_time, service.name, _msg]}
    success: The subquery finds the traces, the outer query their logs.
  - id: answer
    type: query
    title: "Every line from the traces in which checkout logged an ERROR"
    reference: '_time:15m trace_id:in(_time:15m service.name:=checkout severity_text:=ERROR | fields trace_id)'
    hint: "Inside `in(...)`, write the query that finds checkout's ERROR lines and end it with `| fields trace_id`. Put `_time:15m` on both the inner and the outer query, and return whole log entries."
    success: "Every failed checkout tells the same story: checkout reserves stock, payments declines the card, checkout gets a 402 and logs `payment failed`, storefront gets a 502 and logs `checkout failed`. Six lines, three services, one trace_id."
hints:
  - "Run the first example, copy a `trace_id`, and use it in the second example to see what one failed request logged."
  - "`field:in(<query> | fields other_field)` keeps entries whose `field` equals any value the subquery returns."
  - "Answer: `_time:15m trace_id:in(_time:15m service.name:=checkout severity_text:=ERROR | fields trace_id)`"
---

Lines logged inside a span carry its **`trace_id`** and **`span_id`**. One
request touches several services, and every line it causes, in any service,
has the same `trace_id`.

**Step 1: find a failed request.** About 2% of checkouts fail because the
card is declined, and checkout logs `order <id>: payment failed` at ERROR:

```logsql
_time:15m service.name:=checkout severity_text:=ERROR
| sort by (_time desc) | limit 5
| fields _time, trace_id, _msg
```

**Step 2: everything that request logged.**

```logsql
_time:15m trace_id:="<paste the id>"
| sort by (_time)
| fields _time, service.name, severity_text, _msg
```

## Both steps in one query

`in()` accepts a whole query as long as it ends in `fields` with one field.
Its values become the list to match:

```logsql
_time:15m trace_id:in(
  _time:15m service.name:=checkout severity_text:=ERROR | fields trace_id
)
```

That's "every log line from every trace where checkout logged an error".
The same pattern finds every line for one user, one order or one host.

> [!TIP]
> The trace itself is in your trace backend. In Jaeger, search by the trace
> id to see the spans these lines were written in.

## Try it

Return **every log entry** (all fields, no `fields` pipe on the outer query)
from the last 15 minutes that belongs to a trace in which **checkout**
logged an **ERROR**.
