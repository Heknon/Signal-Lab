# Phase 6: Verify

**Goal:** prove, by script, that the course works: every solution passes,
every starter fails, every incident's fault produces its evidence, and the
platform itself is tested.

**Read:** everything so far, and [verification](../references/verification.md).

**Produce:** `course/verification-report.md`, from
[`templates/verification-report.md`](../templates/verification-report.md),
plus the scripts that generated it, committed with the course.

## Checklist

1. [ ] **Static checks:** `lint_artifacts.py`, `lint_lessons.py`,
   `check_sources.py --repo <target>`, `coverage.py`. All pass.
2. [ ] **Lesson suite.** A script that, for every gradable lesson, submits the
   solution (all checks must pass) and the starter (at least one check must
   fail), through the real platform API. Lessons whose solution needs a live
   value (a trace id, a timestamp) are listed and checked by hand, with notes.
3. [ ] **Quiz answers.** Every quiz answer is checked against the real system,
   not just against the answer key: if a question says "checkout calls
   inventory and payments", query the system and confirm it.
4. [ ] **Incident suite.** For each incident: apply its faults, wait, and grade
   a known-good evidence query (must pass); grade the same query on a healthy
   system (must fail). Also check the start-time answer against the real fault
   start.
5. [ ] **Experiment runs.** Run each experiment once to the end. Record whether
   it held, failed or aborted, and confirm the question that asks this is
   graded from the actual outcome.
6. [ ] **Platform tests.** Unit tests for the check engine, the fault/timeline
   engine (including abort and cleanup), accounts and progress (also against
   the real database), and any adapters.
7. [ ] **Packaging.** Build the images from clean; start with the default
   components; start with the optional components; lint and render the
   deployment chart.
8. [ ] **Air-gap test.** Start the stack with outbound network blocked and
   repeat a few lessons ([air-gapped operation](../references/air-gapped.md)).
9. [ ] **Report.** Fill the report: commands run, results, failures fixed (with
   what was wrong), and an explicit **not verified** list with the reason for each.
10. [ ] **Automate.** Put steps 1, 2, 4, 6 and 7 into CI.

## Exit criteria

- Every row in the report is PASS, or appears in "not verified" with a reason.
- Zero failing lessons and zero failing incidents.
- The CI configuration runs the same scripts.

## Common mistakes

- Marking something verified because the code "looks right".
- Fixing a failing lesson by loosening its check until anything passes.
- Testing incidents only during the fault, so a query that is always true passes.
