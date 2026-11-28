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
6. **Check what the data does, not what the code declares.** A goal that
   reads a declared unit or bucket list passes code that records milliseconds
   under `unit="s"`. Check the recorded values, how they spread over buckets,
   that each expected attribute value occurs, that a value changes or returns
   to zero, that a log is in the *right* span. Type-check numbers: `"3"` is not 3.
7. **Name the known mistakes.** Some wrong answers land within tolerance on
   today's data (an error ratio over successes instead of all requests differs
   by 1%). Match them explicitly and explain them, rather than loosening or
   tightening a numeric tolerance.
8. **Simulate the boundary you teach.** If a lesson is about carrying context
   between processes, make the fake network or queue start the other side from
   an empty context, or in-process context will make skipping the lesson's
   point pass.
9. **Count with ranges.** `count: {min: 1}`, `{max: 0}` (absence),
   `{min: 15, max: 70}` (for sampled or probabilistic outcomes, with margins
   that are safe for the seeded data).

## Pattern catalogue

The id in brackets is a valid `type:` name; use it in `adapter.md` when the
pattern fits, or define a subject-specific type (one word, `[a-z_.-]`).

| Pattern | Use for | Parameters |
|---|---|---|
| **entity exists** (`entity`) | a span, row, file, resource, log record, metric exists with properties | `where: {name, kind, status, attributes: {k: v}}`, `count` |
| **relationship** (`relationship`) | parent/child, foreign key, call edge, ordering | `parent: <name>`, `includes: [...]`, `depth` |
| **absence** (`absence`) | noise removed, PII gone, nothing leaked | `count: {max: 0}`, `attributes_absent: [...]` |
| **shape** (`shape`) | types, units, buckets, schema | `unit`, `instrument`, `bounds`, `columns`, `type` |
| **budget** (`budget`) | the right amount, not too much | `spans: {max}`, `series: {max}`, `logs: {max}`, `rows`, `bytes` |
| **output** (`output`) | stdout or response text | `contains`, `regex` |
| **exit** (`exit`) | the program finished cleanly | (none) |
| **query result** (`query`) | a query answers correctly | `reference` (evaluated at the same instant; compare label sets and values within `tolerance`), or `expect: {rows, columns, top, value}` |
| **external state** (`external`) | something built in another UI | `verify: dashboard | alert_rule | ...` through that tool's API |
| **outcome** (`outcome`) | experiment held, rejected or aborted | read from the experiment engine |
| **time** (`time`) | when something started | compare with the recorded fault start, ± `tolerance_s` |

## Writing good failure messages

Say what was seen and how far off it was, never what to type. "Status 404 was
read as success" is good; "Call `raise_for_status()` first" gives the lesson away.

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
