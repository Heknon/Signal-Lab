# Lesson format

A lesson is a folder. The platform discovers it through its track's
`pack.yaml`. Everything a lesson needs is in its folder.

```text
<track>/
  pack.yaml
  <lesson-slug>/
    lesson.md        front matter + Markdown prose
    starter.<ext>    what the learner starts from (runs, but fails a check)
    solution.<ext>   the reference answer (passes every check; never sent to the browser)
    traffic.<ext>    optional: fixed input the learner's work processes (read-only)
```

## Track manifest: `pack.yaml`

```yaml
id: operating            # lesson ids are "<id>/<lesson-slug>"
title: Operating it in production
description: One or two plain sentences.
order: 20
requires:                # optional: the track is shown as locked without these
  components: [postgres]
modules:
  - id: pools
    title: Connection pools
    assumes: [SQL basics]              # shown, so people can decide to skip
    lessons: [pool-sizing, pool-exhaustion]
```

## Lesson front matter

```yaml
---
title: Pool exhaustion                     # sentence case, names the idea
summary: Find why requests queue when every connection is busy.
kind: code          # code | config | query | quiz | task | experiment | incident
minutes: 8
concepts: [connection-pool, saturation]    # ids from concept-map.md
assumes: [Connection pool sizing]          # what you should know already
sources:                                   # REQUIRED: real artifacts in the target system
  - src/db/pool.py#Pool.acquire
  - config/defaults.yaml#database.pool_size
runtime:                                   # code/config lessons; how the runner executes it
  timeout: 20                              #   seconds before the run is killed
  args: ["deploy", "--dry-run"]            #   command-line arguments for the learner's program
  env: {POOL_SIZE: "2"}                    #   extra environment variables for this lesson
hints:                                     # 2-3, from "where to look" to nearly the answer
  - Look at how long requests wait before they get a connection.
  - "`pool_wait_seconds` is a histogram per pool."
checks: [...]                              # see check-patterns.md
---
```

Kind-specific blocks:

| Kind | Extra front matter |
|---|---|
| `query` | `query: {backend, language, range_s, examples: [{label, query}]}` |
| `quiz` | `quiz: {questions: [...]}` (see Questions below) |
| `task` | `tools: [<links to the UI>]`, checks of type `backend` verified through an API |
| `config` | `filename`, plus `traffic.*` that runs through the learner's config (Signal Lab calls this kind `collector`) |
| `experiment` | `experiment: {hypothesis, steady_state: {query, threshold, abort_at, direction}, baseline_s, inject, duration_s, recovery_s}`, plus `quiz: {questions: [...]}` |
| `incident` | `incident: {duration_s, timeline: [{at, set, load, fault: true}]}`, plus `quiz: {questions: [...]}` |

## Prose rules

- Open with why it matters, in one or two sentences. No "In this lesson we will…".
- Show the idea with a minimal snippet **taken from the target system**: same
  names, same config keys. Never `foo`/`bar` or a made-up service.
- A `## Try it` section says exactly what to change and what to look at after running.
- At most one callout (`> [!NOTE]`, `> [!TIP]`, `> [!WARNING]`), only when it adds something.
- Short paragraphs, concrete numbers, sentence-case headings, no emoji.
- Tables are good for comparisons (option, meaning, when to use).

## Starter and solution rules

- The starter runs without crashing and fails at least one check with a useful message.
- The starter marks the work with `TODO` comments, not blanks that break parsing.
- The solution is idiomatic, minimal, and passes every check.
- Both are complete: nothing depends on another lesson.
- Use a private seeded RNG (`random.Random(7)`) for simulated data. Global RNG
  state is shared with libraries (e.g. id generators) and makes outcomes flaky.

## Questions

Questions always live under `quiz: {questions: [...]}`, for quiz, incident and
experiment lessons alike.

```yaml
quiz:
  questions:
    - id: start
      kind: time                 # omit kind for multiple choice
      prompt: When did the problem start?
      tolerance_s: 120
      hint: Where does the line first leave its usual band?
    - id: cause
      prompt: Which service is the root cause?
      options: [{id: a, label: storefront}, {id: b, label: checkout}]
      answer: b
      multiple: false
      explanation: Checkout retries every failed payment, tripling payments traffic.
    - id: evidence
      kind: query
      prompt: Write a query that shows it.
      language: metricsql
      must_include: [rate]
      expect: {top: {service_name: payments}}
```

Set `kind:` only for `time`, `outcome` and `query`. Without `kind`, a question
with `options` is multiple choice, and one with `input: text` (and no
options) takes a typed answer.

| Question | Graded against |
|---|---|
| `options` (single or `multiple: true`) | the answer key |
| `input: text` | the answer key, case-insensitive |
| `time` | the real start of the fault, within `tolerance_s` |
| `outcome` | what the experiment actually did: `held`, `rejected` or `aborted` |
| `query` | live data: `must_include`, and `expect: {top: {label: value}}` or `expect: {value: {gt: n}}` |

Explanations teach the *why*. Wrong-answer hints point somewhere to look; they
never reveal the answer.
