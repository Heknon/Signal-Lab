# Verification report: {{subject}}

Replace every `{{...}}` placeholder.

## Run

- **Date:** {{YYYY-MM-DD}}
- **Commit:** {{git sha}}
- **Components enabled:** {{list}}
- **Machine:** {{CPU / memory / OS}}

## Summary

| Suite | Command | Result |
|---|---|---|
| Static | `{{python tools/lint_artifacts.py && ...}}` | {{PASS / FAIL}} |
| Lessons | `{{scripts/test_lessons.py}}` | {{N/N solutions pass, N/N starters fail}} |
| Quiz facts | `{{command}}` | {{N/N confirmed}} |
| Incidents | `{{scripts/test_incidents.py}}` | {{N/N evidence during fault, N/N fail when healthy}} |
| Experiments | `{{command}}` | {{N/N ran to the end}} |
| Platform tests | `{{pytest}}` | {{N passed}} |
| Packaging | `{{docker compose build && helm lint}}` | {{PASS / FAIL}} |
| Air gap | `{{procedure}}` | {{PASS / FAIL}} |

## Lessons

| Lesson | Solution | Starter | Notes |
|---|---|---|---|
| {{track/lesson}} | {{PASS}} | {{FAILS as expected: which check}} | {{}} |

## Incidents

| Incident | Fault applied | Evidence during fault | Evidence when healthy | Start-time answer |
|---|---|---|---|---|
| {{track/incident}} | {{faults}} | {{PASS}} | {{FAILS as expected}} | {{within N s}} |

## Failures found and fixed

| What failed | Cause | Fix |
|---|---|---|
| {{lesson or component}} | {{root cause}} | {{what changed; whether a check was loosened and why}} |

## Not verified

Write "Nothing" if empty.

| Item | Why not | How to verify |
|---|---|---|
| {{item}} | {{reason}} | {{steps}} |
