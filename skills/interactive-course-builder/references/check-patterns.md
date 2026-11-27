# Check patterns

A check reads **observable behaviour** and returns `pass`, `fail` or
`pending` (still collecting), with a **detail** that explains what it saw.

## Principles

1. **Observe, don't parse.** Read what the work *did*: output, state,
   telemetry, responses. Reading the learner's source is allowed only as a
   secondary hint (`must_include`), never as the only check.
2. **Attribute to the run.** Every observation is tied to one run, by an id the
   platform injects (env var, header, label, schema, temp dir). Otherwise
   learners see each other's results.
3. **Explain failures.** Say what was found, compare it with what was
   expected, and suggest the nearest match:
   - `No span named "say-hello". Did you mean "say_hello"? Spans seen: my-span.`
   - `api.requests has 854 time series, expected at most 6. Every unique attribute combination is a separate series.`
4. **Accept equivalent answers.** Match on meaning (structure, values,
   relationships), not exact text. Allow regexes (`~^GET `), numeric ranges
   (`{gte: 1}`), and any one of several valid forms.
5. **Pending, then final.** While results are still arriving, report
   `pending`. After a settle time, missing data becomes `fail` with "nothing
   arrived; did the program run?"
6. **Count with ranges.** `count: {min: 1}`, `{max: 0}` (absence),
   `{min: 15, max: 70}` (for sampled or probabilistic outcomes, with margins
   that are safe for the seeded data).

## Pattern catalogue

| Pattern | Use for | Parameters |
|---|---|---|
| **entity exists** | a span, row, file, resource, log record, metric exists with properties | `where: {name, kind, status, attributes: {k: v}}`, `count` |
| **relationship** | parent/child, foreign key, call edge, ordering | `parent: <name>`, `includes: [...]`, `depth` |
| **absence** | noise removed, PII gone, nothing leaked | `count: {max: 0}`, `attributes_absent: [...]` |
| **shape** | types, units, buckets, schema | `unit`, `instrument`, `bounds`, `columns`, `type` |
| **budget** | the right amount, not too much | `spans: {max}`, `series: {max}`, `logs: {max}`, `rows`, `bytes` |
| **output** | stdout or response text | `contains`, `regex` |
| **exit** | the program finished cleanly | (none) |
| **query result** | a query answers correctly | `reference` (evaluated at the same instant; compare label sets and values within `tolerance`), or `expect: {rows, columns, top, value}` |
| **external state** | something built in another UI | `verify: dashboard | alert_rule | ...` through that tool's API |
| **outcome** | experiment held, rejected or aborted | read from the experiment engine |
| **time** | when something started | compare with the recorded fault start, ± `tolerance_s` |

## Writing good failure messages

| Situation | Message |
|---|---|
| nothing observed | "No spans were exported. Did the program record anything?" |
| close miss on a name | "No metric `orders.placed`. Did you mean `orders_placed`?" |
| right entity, wrong property | "Span `charge-card` is close, but its status is `unset`, expected `error`." |
| missing attribute | "`checkout` has no `app.user.id`. It has `user`, `cart`." |
| too many | "854 series, expected at most 6." Then explain why it matters. |
| relationship broken | "4 traces were produced. Context may not be propagating." |
| query differs | "Your query returns 15 rows; the expected answer has 4. Aggregate with `sum by (le, service)`." |

## Anti-patterns

- A check that the starter already passes: the exercise has nothing to do.
- A check that only the reference solution passes (exact strings, exact float values).
- A single check hiding several requirements: split it, so the goals list shows progress.
- Timing-sensitive checks without margins: use percentiles and ranges, and seed randomness.
- Checks that call the same API the learner's code calls and trust its answer.
