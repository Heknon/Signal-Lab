# Verification

"Verified" means a script ran it and it passed. Anything else is "not
verified", and the report says why.

## Suites

| Suite | Passes when | How |
|---|---|---|
| Static | artifacts complete, lessons well-formed, sources real, coverage complete | `tools/lint_artifacts.py`, `tools/lint_lessons.py`, `tools/check_sources.py --repo <target>`, `tools/coverage.py` |
| Lessons | every solution passes all checks; every starter fails at least one | submit both through the real platform API and read the graded result (Signal Lab: `scripts/test_lessons.py`) |
| Quizzes | every answer is true of the real system | for each factual question, a query or command that confirms the answer; record it in the report |
| Incidents | the evidence query passes during the fault and fails on a healthy system | apply faults, wait, grade; reset; grade again (Signal Lab: `scripts/test_incidents.py`) |
| Experiments | each runs to the end; the outcome question is graded from the real result | start through the API, poll until done, answer the outcome question |
| Platform | check engine, timeline engine (including abort and cleanup), accounts, adapters | unit tests; accounts tests also against the real database |
| Packaging | clean image build; start with defaults; start with optional components; chart lint and render | CI jobs |
| Air gap | tools, suites and the stack work with the network blocked | `unshare -rn` for scripts, an internal Compose network for the stack; see [air-gapped](air-gapped.md) |
| UI | no horizontal overflow at 390/768/1024/1280/1440; deslop checklist clean | screenshot script ([phase 7](../phases/7-review-the-ui.md)) |

## Rules

- **Run against the real thing.** Mocks are for unit tests of the platform,
  not for lessons.
- **Test both directions.** A check that passes on the solution proves nothing
  if it also passes on the starter, or on a healthy system for incidents.
- **Seed and margin.** Probabilistic lessons (sampling, load) use seeded data
  and ranges wide enough to pass every time. Run the suite three times before
  trusting it.
- **Manual items are explicit.** A lesson whose solution needs a live value
  (for example a trace id) is marked `manual_solution: true`, skipped by the
  suite, checked by hand, and listed in the report with the evidence.
- **Fix the cause.** When a lesson fails verification, fix the lesson or the
  platform. Loosen a check only when it was wrong, and say so in the report.
- **Re-verify after changes to shared parts.** A change to the scenario (for
  example a service gets slower) can silently change quiz answers. Re-run the
  quiz-fact checks too.

## Report

Use [`templates/verification-report.md`](../templates/verification-report.md).
It must contain the exact commands, the date, the platform version (commit),
totals, every failure found and how it was fixed, and the not-verified list.
