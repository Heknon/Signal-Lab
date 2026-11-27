---
title: Words, phrases and time ranges
summary: Find log lines by the words in their message, and limit the search to a time range.
kind: query
minutes: 6
concepts: [LogsQL, word filter, phrase filter, _time, _msg]
assumes: [What a log record is]
query:
  backend: victorialogs
  language: logsql
  range_s: 900
  examples:
    - {label: Everything from the last minute, query: "_time:1m"}
    - {label: One word, query: "_time:5m declined"}
    - {label: Not the HTTP client chatter, query: "_time:5m -\"HTTP Request\""}
checks:
  - id: shape
    type: query
    title: "Filter on `_time` and the words `payment declined`"
    must_include: ["_time:", "declined"]
    expect: {rows: {min: 1}, columns: [_time, _msg]}
    success: Each row is a whole log entry, newest first.
  - id: answer
    type: query
    title: "Every `payment declined` line from the last 10 minutes"
    reference: '_time:10m "payment declined"'
    hint: "Put the phrase in double quotes and add `_time:10m`. Return whole log entries: no pipes."
    success: "About 2% of payments are declined, so there are a handful. Each line has the order id in its message."
hints:
  - "Filters separated by a space must all match: `_time:5m error` means \"in the last 5 minutes AND contains the word error\"."
  - "A phrase in double quotes matches those words next to each other, in that order."
  - "Answer: `_time:10m \"payment declined\"`"
---

A LogsQL query is a list of **filters**. A log entry is returned when it
matches all of them.

```logsql
_time:5m "payment declined"
```

- `_time:5m` keeps entries from the last 5 minutes.
- `"payment declined"` keeps entries whose message (`_msg`) contains that
  phrase.

## Words, not substrings

A bare word or quoted phrase matches whole **words** in `_msg`, ignoring
punctuation. `declined` matches `payment declined for order 6fc4a4d980`;
`declin` matches nothing.

| Filter | Matches |
| --- | --- |
| `declined` | the word `declined` |
| `"payment declined"` | those two words, adjacent, in order |
| `payment declined` | both words, anywhere (two filters) |
| `declin*` | any word starting with `declin` |
| `i("Payment")` | case-insensitive |
| `-"HTTP Request"` | entries that do **not** contain the phrase |
| `(placed or declined)` | either word (`or` binds looser than the implicit `and`, so add parentheses) |

## Time ranges

| Filter | Range |
| --- | --- |
| `_time:5m` | the last 5 minutes (also `30s`, `1h`, `2d`) |
| `_time:[2026-01-02T10:00:00Z, 2026-01-02T11:00:00Z)` | an absolute range, end excluded |
| `_time:>1h` | older than an hour |

Always put a `_time` filter in a query. Without one, VictoriaLogs scans
everything it has.

> [!NOTE]
> The lab runs your query over the last 15 minutes and counts relative
> ranges like `_time:5m` back from the end of that window, so every run of the
> same query sees the same logs.

> [!TIP]
> Most lines from storefront, checkout and loadgen are `HTTP Request: ...`
> lines from the httpx instrumentation. `-"HTTP Request"` hides them.

## Try it

Return every log entry from the **last 10 minutes** that contains the phrase
**payment declined**.
