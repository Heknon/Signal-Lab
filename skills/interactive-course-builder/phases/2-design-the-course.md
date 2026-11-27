# Phase 2: Design the course

**Goal:** turn the concept map into a course structure where any lesson can be
skipped and the whole thing builds to realistic incidents.

**Read:** `course/concept-map.md`, plus [lesson format](../references/lesson-format.md).

**Produce:** `course/outline.md`, from [`templates/outline.md`](../templates/outline.md).

## Checklist

1. [ ] **Group concepts into tracks.** A track is something a person would sign
   up for: "Foundations", "Operating it in production", "Querying it",
   "Investigating incidents". 3–7 tracks. A track may require an optional
   component (for example one backend), and must say so.
2. [ ] **Split tracks into modules.** A module is one topic, taught in 2–7 lessons,
   that an experienced person could skip as a whole. Each module lists what it
   **assumes**, in plain words ("Python logging", "SQL joins").
3. [ ] **Write lessons as standalone units.** For every lesson record:
   - id (`track-id/lesson-slug`), title, one-line summary, minutes (3–15)
   - kind: `code`, `config`, `query`, `quiz`, `task`, `experiment` or `incident`
   - concepts taught (ids from the concept map)
   - **assumes**: concepts the learner should already know, so they can decide to skip
   - **sources**: the real artifacts this lesson is built on
   - what the learner produces, and what the checks will observe
4. [ ] **Order each track by progression,** and record each lesson's stage in
   the outline's `Stage` column (`happy`, `options`, `failure`, `judgment`, `capstone`):
   1. **Happy path:** use it correctly, see it work.
   2. **Shape and options:** the settings and variations people actually use.
   3. **Failure modes:** each high-blast-radius concept gets a lesson where
      something breaks and the learner fixes or diagnoses it.
   4. **Judgment:** when to use it, when *not* to, and what it costs.
   5. **Capstone incidents:** realistic incidents investigated with the system's
      own signals (see below).
5. [ ] **Design the capstone incidents.** 4–8 per course. Each has:
   - a **symptom brief** written the way people really report problems ("checkout spins, but not for everyone")
   - a **hidden fault** from the concept map's failure modes
   - the **fault** ids that cause it (`Fault` column); phase 3 defines each one
   - the **signals** that reveal it, which must be the target system's own
     (for a library: its API surface, observed through the scenario)
   - graded answers: **when** it started, **where** the cause is, **what** the
     mechanism is, and **evidence**: a query, command or check against the
     scenario, in whatever form the adapter can observe
   - one deliberately misleading symptom (the cause is not where it hurts)
6. [ ] **Check coverage.** Every concept with priority ≥ 9 is taught in at least
   one lesson. Every concept with blast ≥ 3 is taught by a `failure` or `capstone` lesson. Everything else is taught or listed in the concept map's
   deliberate gaps. Run `python <skill>/tools/coverage.py course/concept-map.md course/outline.md`.
7. [ ] **Check skippability.** For each lesson ask: could someone open it
   directly, with nothing done before? If not, fold the dependency into its starter.

## Exit criteria

- `python <skill>/tools/lint_artifacts.py course/outline.md` and `python <skill>/tools/coverage.py course/concept-map.md course/outline.md` pass.
- Every lesson has kind, stage, assumes, sources and a "checks observe" line.
- Every track has a `happy` lesson and a `failure` or `capstone` lesson; at
  least 4 incidents, each naming its fault ids. (The tools check all of this.)

## Common mistakes

- Lessons that only explain. Every lesson makes the learner *do* something that can be graded.
- A capstone that is a quiz about the docs. Incidents need a live system and real signals.
- One giant "advanced" module. If it can't be skipped as a unit, split it.
