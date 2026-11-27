---
title: Log volume over time
summary: Bucket logs by time with stats by (_time:1m) to graph how many lines each service writes.
kind: query
minutes: 6
concepts: [time buckets, log volume, stats by _time]
assumes: [LogsQL stats by]
query:
  backend: victorialogs
  language: logsql
  range_s: 900
  examples:
    - {label: All logs per minute, query: "_time:15m | stats by (_time:1m) count() logs"}
    - {label: Per service, every 30s, query: "_time:15m | stats by (_time:30s, service.name) count() logs"}
checks:
  - id: shape
    type: query
    title: "Bucket with `stats by (_time:1m, ...)`"
    must_include: ["_time:1m", "stats"]
    expect: {rows: {min: 2}, columns: [_time, logs]}
    success: One row per minute; the lab draws it as a graph.
  - id: answer
    type: query
    title: "Lines that aren't httpx chatter, per minute and service"
    reference: '_time:15m -scope.name:=httpx | stats by (_time:1m, service.name) count() logs'
    value_columns: [logs]
    tolerance: 0.05
    hint: "Exclude the httpx logger with `-scope.name:=httpx`, then `| stats by (_time:1m, service.name) count() logs`."
    success: "checkout's line is the order rate: one `order ... placed` per successful checkout. The others only log when something goes wrong."
hints:
  - "`_time:1m` inside `by (...)` groups entries into one-minute buckets. Any duration works: `30s`, `5m`, `1h`."
  - "`scope.name` is the name of the Python logger that wrote the line. The HTTP client lines all come from `httpx`."
  - "Answer: `_time:15m -scope.name:=httpx | stats by (_time:1m, service.name) count() logs`"
---

A count per service tells you who logs the most. A count per **minute**
tells you when that changed, which is usually the first thing you want to
know during an incident.

```logsql
_time:15m | stats by (_time:1m) count() logs
```

Putting `_time:1m` in the `by` list groups entries into one-minute buckets.
Each row's `_time` is the start of its bucket. Add more fields to get one
line per value:

```logsql
_time:15m | stats by (_time:1m, service.name) count() logs
```

The lab charts any result that has a `_time` column and numbers, one line
per combination of the other fields. Switch to **Table** to see the rows.

> [!NOTE]
> The newest bucket is still filling up, so it's usually lower than the
> others. Ignore it, or end the range at the last full minute.

## Try it

Most of the shop's lines are `HTTP Request: ...` from the **httpx** logger.
Leave those out and count the rest per **minute** and **service** over the
last 15 minutes, in a column named `logs`.
