# Phase 5: Write the lessons

**Goal:** every lesson in `outline.md` exists as a content folder: prose,
starter, solution and checks, all built on real artifacts of the target system.

**Read:** `course/outline.md`, `course/adapter.md`, `course/platform.md`,
[lesson format](../references/lesson-format.md), [check patterns](../references/check-patterns.md).

**Produce:** one folder per lesson ([`templates/lesson/`](../templates/lesson)).

## For each lesson, in outline order

1. [ ] **Open the cited sources** listed for the lesson in the outline. Read
   them. The lesson's code, config and names come from there.
2. [ ] **Write the solution first.** Run it against the platform. Note what it
   produces.
3. [ ] **Write the checks** from what the solution produces, using the
   patterns. Each check:
   - observes behaviour, not source text
   - has a title phrased as a goal ("`checkout` carries `app.user.id`")
   - fails with a message that says what was seen, without giving away the fix
   - is tolerant of equivalent correct answers (different variable names,
     ordering, a different but equivalent query)
4. [ ] **Write the starter** by breaking the solution in the way the lesson
   teaches: leave a `TODO` where the learner works. The starter must run
   without crashing, and must fail at least one check with a useful message.
5. [ ] **Write the prose.** Short and concrete:
   - why this matters, in one or two sentences
   - the idea, with a minimal snippet taken from the real system
   - a "Try it" section saying exactly what to change
   - at most one callout, only where it adds something
   No filler, no "In this lesson we will", no emoji, no marketing tone.
6. [ ] **Fill the front matter:** title, summary, kind, minutes, concepts,
   `assumes`, `sources` (real paths), `hints` (2–3, progressively more specific),
   and `checks`.
7. [ ] **Run it.** Starter fails, solution passes, through the real platform.
   Fix the lesson, not the check, unless the check is wrong.

## Incident lessons, additionally

- [ ] The brief (the lesson's prose) states only the symptom, never the cause.
      Don't quote the faulty code or name the mechanism; sources are listed in
      front matter, and hints lead there.
- [ ] The fault timeline starts healthy, so "when did it start" is answerable.
- [ ] Questions: start time (graded against the real fault start, with a
      tolerance), root cause, mechanism, and an evidence query or command
      graded against live data.
- [ ] Progressive hints, from "where to look" to "what to compare".

## Exit criteria

- `python <skill>/tools/lint_lessons.py <lessons-dir> --adapter course/adapter.md`, `python <skill>/tools/check_sources.py --repo <target> <lessons-dir>` and
  `python <skill>/tools/coverage.py course/concept-map.md course/outline.md --lessons <lessons-dir>` pass.
- Every lesson in the outline exists; nothing extra exists that isn't in the outline (update the outline first).
- Each lesson has been run at least once with its solution and its starter.

## Common mistakes

- Copying a generic example from a tutorial instead of the target's own code.
- Starter code that crashes. The learner should see a clear failing check, not a stack trace.
- Checks that only accept the reference solution's exact wording.
