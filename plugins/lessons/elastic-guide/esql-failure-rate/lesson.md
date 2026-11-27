---
title: Failure rate with ES|QL
summary: Turn event.outcome into a failure rate per service with EVAL and CASE.
kind: query
minutes: 7
concepts: [event.outcome, EVAL, CASE, ratio]
assumes: [ES|QL FROM, WHERE and STATS]
query:
  backend: elastic
  language: esql
  range_s: 900
  examples:
    - {label: Outcomes per service, query: "FROM traces-apm* | WHERE processor.event == \"transaction\" AND @timestamp > NOW() - 15 minutes | STATS n = COUNT(*) BY service.name, event.outcome"}
    - {label: Failed transactions by status code, query: "FROM traces-apm* | WHERE processor.event == \"transaction\" AND event.outcome == \"failure\" | STATS n = COUNT(*) BY service.name, http.response.status_code"}
checks:
  - id: shape
    type: query
    title: "Compute a `failure_rate` column from `event.outcome`, per service"
    must_include: ["event.outcome", "failure", "STATS", "service.name"]
    expect: {rows: {min: 2}, columns: [failure_rate, service.name]}
    success: A failure rate per service.
  - id: answer
    type: query
    title: Failure rate (0 to 1) per service, last 15 minutes
    reference: 'FROM traces-apm* | WHERE processor.event == "transaction" AND @timestamp > NOW() - 15 minutes | EVAL failed = CASE(event.outcome == "failure", 1, 0) | STATS failure_rate = AVG(failed) BY service.name'
    value_columns: [failure_rate]
    tolerance: 0.1
    hint: "Turn each transaction into 1 (failed) or 0 (not) with `EVAL failed = CASE(event.outcome == \"failure\", 1, 0)`; the average of that column is the failure rate. Keep only the `failure_rate` and `service.name` columns."
    success: "checkout and storefront fail a little (their 502s after card declines); payments shows 0: a 402 decline isn't a server failure."
hints:
  - "`CASE(condition, value_if_true, value_otherwise)` works inside `EVAL`."
  - "Answer: `FROM traces-apm* | WHERE processor.event == \"transaction\" AND @timestamp > NOW() - 15 minutes | EVAL failed = CASE(event.outcome == \"failure\", 1, 0) | STATS failure_rate = AVG(failed) BY service.name`"
---

APM Server sets **`event.outcome`** on every transaction and span:

| Value | Meaning for a transaction |
| --- | --- |
| `success` | Handled fine, including 4xx responses |
| `failure` | HTTP 5xx, or span status `ERROR` |
| `unknown` | Not enough information to tell |

A failure *rate* needs two numbers per service: failed and total. One way is
to turn the outcome into a number and average it:

```esql
FROM traces-apm*
| WHERE processor.event == "transaction" AND @timestamp > NOW() - 15 minutes
| EVAL failed = CASE(event.outcome == "failure", 1, 0)
| STATS failure_rate = AVG(failed) BY service.name
```

The average of a column of 0s and 1s is the share of 1s.

> [!TIP]
> Want counts as well? `STATS total = COUNT(*), failed = SUM(failed) BY
> service.name | EVAL failure_rate = failed / TO_DOUBLE(total)` gives the
> same rate with the numbers behind it. Integer division would round
> everything down to 0, hence `TO_DOUBLE`.

## Try it

Return a `failure_rate` between 0 and 1 for **each service**, over the
**last 15 minutes** of transactions. Return only `failure_rate` and
`service.name`.
