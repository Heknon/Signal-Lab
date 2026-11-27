---
title: Counting with ES|QL
summary: "Write your first ES|QL pipeline: count transactions per service in the last 15 minutes."
kind: query
minutes: 6
concepts: [ES|QL, FROM, WHERE, STATS ... BY, SORT, processor.event]
assumes: [Kibana APM transactions]
query:
  backend: elastic
  language: esql
  range_s: 900
  examples:
    - {label: Ten raw transaction documents, query: "FROM traces-apm* | WHERE processor.event == \"transaction\" | KEEP @timestamp, service.name, transaction.name, transaction.duration.us | LIMIT 10"}
    - {label: Spans vs transactions, query: "FROM traces-apm* | STATS docs = COUNT(*) BY processor.event"}
    - {label: Transactions per minute, query: "FROM traces-apm* | WHERE processor.event == \"transaction\" AND @timestamp > NOW() - 15 minutes | STATS transactions = COUNT(*) BY minute = BUCKET(@timestamp, 1 minute) | SORT minute"}
checks:
  - id: shape
    type: query
    title: "Filter to transactions and use `STATS ... BY service.name`"
    must_include: ["traces-apm", "processor.event", "STATS", "service.name"]
    expect: {rows: {min: 2}, columns: [transactions, service.name]}
    success: One row per service, with a `transactions` column.
  - id: answer
    type: query
    title: Transactions per service in the last 15 minutes
    reference: 'FROM traces-apm* | WHERE processor.event == "transaction" AND @timestamp > NOW() - 15 minutes | STATS transactions = COUNT(*) BY service.name'
    value_columns: [transactions]
    tolerance: 0.05
    hint: "Keep only `processor.event == \"transaction\"` and the last 15 minutes (`@timestamp > NOW() - 15 minutes`), then `STATS transactions = COUNT(*) BY service.name`."
    success: storefront and inventory handle about twice as many requests as checkout and payments.
hints:
  - "ES|QL is a pipeline: `FROM ... | WHERE ... | STATS ... | SORT ...`. Each `|` takes the previous table and transforms it."
  - "Name a computed column with `=`: `STATS transactions = COUNT(*) BY service.name`."
  - "Answer: `FROM traces-apm* | WHERE processor.event == \"transaction\" AND @timestamp > NOW() - 15 minutes | STATS transactions = COUNT(*) BY service.name | SORT transactions DESC`"
---

**ES|QL** is Elasticsearch's piped query language. A query is a chain of
commands; each one takes a table and returns a new one:

```esql
FROM traces-apm*
| WHERE processor.event == "transaction" AND @timestamp > NOW() - 15 minutes
| STATS transactions = COUNT(*) BY service.name
| SORT transactions DESC
```

- `FROM traces-apm*` reads the APM trace data streams.
- `WHERE` filters rows. Note `==` for equality and double quotes for strings.
- `STATS ... BY` aggregates, like SQL's `GROUP BY`.
- `SORT`, `LIMIT` and `KEEP` (pick columns) shape the output.

## Transactions and spans live together

APM Server writes transactions *and* spans into `traces-apm*`. The
`processor.event` field tells them apart (`"transaction"` or `"span"`).
Forget the filter and you count every span too: database calls, outgoing
HTTP calls, the ASGI `http send` spans and so on.

> [!NOTE]
> The lab runs your query exactly as written, without a time picker, so put
> the time range in the query: `@timestamp > NOW() - 15 minutes`. (In Kibana's
> ES|QL editor the time picker filters for you.)

## Try it

Count **transactions** per `service.name` over the **last 15 minutes**, in a
column called `transactions`.
