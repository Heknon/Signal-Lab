---
title: All logs for one trace
summary: Find a failed trace with ES|QL, then pull every log line written during it.
kind: query
minutes: 7
concepts: [trace.id, logs-apm, log correlation, KEEP]
assumes: [ES|QL FROM, WHERE and STATS]
query:
  backend: elastic
  language: esql
  range_s: 900
  examples:
    - {label: "Step 1: recent failed checkouts", query: "FROM traces-apm* | WHERE processor.event == \"transaction\" AND transaction.name == \"POST /api/checkout\" AND event.outcome == \"failure\" | SORT @timestamp DESC | KEEP @timestamp, trace.id, http.response.status_code | LIMIT 5"}
    - {label: Recent error logs, query: "FROM logs-apm* | WHERE TO_LOWER(log.level) == \"error\" | SORT @timestamp DESC | KEEP @timestamp, service.name, message, trace.id | LIMIT 20"}
checks:
  - id: shape
    type: query
    title: "Query `logs-apm*` filtered on one `trace.id`"
    must_include: ["logs-apm", "trace.id"]
    expect: {rows: {min: 1, max: 30}, columns: [service.name, message]}
    hint: Paste a trace id from step 1 into `WHERE trace.id == "..."`, and `KEEP` at least `service.name` and `message`.
    success: "One request's story, told by every service it passed through. Expect lines from payments, checkout and storefront."
hints:
  - "Run the first example to get a `trace.id` of a failed checkout, then copy it."
  - "`FROM logs-apm* | WHERE trace.id == \"<id>\" | SORT @timestamp | KEEP @timestamp, service.name, log.level, message`"
  - "No rows? Logs arrive a few seconds after spans. Pick a trace that's at least half a minute old."
---

In the previous lessons you counted and averaged. ES|QL is just as good at
the opposite: finding the handful of documents that belong to **one**
request.

Logs written inside a request carry the request's **`trace.id`**. They live
in `logs-apm*`, separate from the spans in `traces-apm*`, but the id is the
same, so you can go from one to the other in two queries.

**Step 1: find a failed trace.**

```esql
FROM traces-apm*
| WHERE processor.event == "transaction"
    AND transaction.name == "POST /api/checkout"
    AND event.outcome == "failure"
| SORT @timestamp DESC
| KEEP @timestamp, trace.id, http.response.status_code
| LIMIT 5
```

About 2% of checkouts fail in normal traffic (card declines), so there's
always something to find.

**Step 2: get its logs.**

```esql
FROM logs-apm*
| WHERE trace.id == "<paste the id>"
| SORT @timestamp
| KEEP @timestamp, service.name, log.level, message
```

> [!NOTE]
> `logs-apm*` also holds APM **error** documents (recorded exceptions). They
> have the same `trace.id`, so the declined card's `CardDeclined` exception
> can show up next to the log lines, with its text in `error.exception.message`.

## Try it

Run step 1 (it's the first example), then write step 2 for one of the trace
ids. Return at least `service.name` and `message`.
