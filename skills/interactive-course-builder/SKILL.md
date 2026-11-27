---
name: interactive-course-builder
description: Build a complete, auto-graded, skippable interactive course for a codebase or technology, running as a web app, verified end to end. Use when asked to create training, a course, labs, exercises, onboarding or a "crash course" for a system, library, platform or tool.
---

# Interactive course builder

Given access to a codebase or a technology, produce a **complete course** that is:

- **in depth**: from the happy path, through failure modes, to realistic incidents
- **skippable**: tracks → modules → standalone lessons, each declaring what it assumes
- **auto-graded**: every exercise is checked against real, observable behaviour
- **a web app** with a modern, clean UI
- **verified end to end**: every solution passes, every starter fails, every
  injected fault produces its evidence, all by script

The work is split into **phase 0 plus seven phases**. Each phase has a checklist and
produces one **required artifact**. The next phase starts by reading that
artifact. **Never start a phase until the previous phase's exit criteria are
met.** If you are unsure, re-read the phase file; don't improvise.

| # | Phase | Read | Produce |
|---|---|---|---|
| 0 | [Check the environment](phases/0-check-the-environment.md) | this machine | `course/environment.md` |
| 1 | [Map the subject](phases/1-map-the-subject.md) | the target system, `environment.md` | `course/concept-map.md` |
| 2 | [Design the course](phases/2-design-the-course.md) | `concept-map.md` | `course/outline.md` |
| 3 | [Define the subject adapter](phases/3-define-the-adapter.md) | `outline.md` | `course/adapter.md` |
| 4 | [Build the platform](phases/4-build-the-platform.md) | `adapter.md`, `environment.md` | a running app + `course/platform.md` |
| 5 | [Write the lessons](phases/5-write-the-lessons.md) | `outline.md`, `adapter.md`, `platform.md` | lesson folders |
| 6 | [Verify](phases/6-verify.md) | everything | `course/verification-report.md` |
| 7 | [Review the UI](phases/7-review-the-ui.md) | the running app | `course/ui-review.md` + screenshots |

All artifacts live in a `course/` folder at the root of the output project.
Templates for each are in [`templates/`](templates).

## Rules that apply in every phase

1. **Real artifacts only.** Every concept, lesson, check and incident points at
   real files, components, configs, commands, metrics or APIs of the target
   system: a path, a symbol, a config key. Generic "an example service" content is
   a defect. `tools/check_sources.py` enforces this.
2. **Grade behaviour, not text.** A check observes what the learner's work
   *did* (output, state, telemetry, responses, files), not whether their source
   contains a keyword. Keyword checks are allowed only as a secondary hint.
3. **Failures explain themselves.** Every failing check says what it saw and
   how far off it was. "Expected X, got Y; did you mean Z?" beats "wrong".
4. **Skippable by construction.** No lesson depends on work done in another
   lesson. Every lesson ships complete starter material.
5. **Prove it, don't claim it.** Nothing is "done" until a script demonstrates it.
   Write down anything you could not verify, and say why.
6. **Assume no network, while building and while running.** Everything this
   skill needs is in this folder: the UI checklist, patterns and templates are
   complete, so never search the web or fetch docs. Use only what phase 0 found
   installed or in a local package cache; never `pip install`, `npm install`
   or `docker pull` from the internet. The finished course runs with no
   network too. See [air-gapped operation](references/air-gapped.md).
7. **Stop and ask** only when the subject itself is ambiguous: two systems with
   the same name, or no access to the code. Otherwise decide, write the
   decision in the artifact, and keep going.

## References

| Reference | Use it in phase |
|---|---|
| [Lesson format](references/lesson-format.md) | 2, 5 |
| [Check patterns](references/check-patterns.md) | 3, 5 |
| [Subject adapter template](references/adapter-template.md) | 3, 4 |
| [Platform](references/platform.md) | 4 |
| [Verification](references/verification.md) | 6 |
| [UI rules and AI-slop anti-patterns](references/ui-rules.md) | 4, 7 |
| [Multi-user and team mode](references/team-mode.md) | 4 |
| [Air-gapped operation](references/air-gapped.md) | 0, 4, 6 |

## Tools

Plain Python 3.9+ scripts using only the standard library (PyYAML is used if
installed, but not required). `tools/` means this skill's `tools/` folder; run
them from the output project root, e.g. `python <skill>/tools/coverage.py ...`.
Each prints one line per problem and exits non-zero on any error.

| Command | What it checks |
|---|---|
| `tools/preflight.py --target <target>` | writes `course/environment.md`: runtimes, build tools, loaded images, browsers, local package sources; no network use |
| `tools/lint_artifacts.py course/` (or one file) | each phase artifact has every required section, filled, with no `{{placeholders}}`; plus per-artifact rules (score arithmetic, ≥ 4 incidents, reversible faults, spike output, ticked final UI pass) |
| `tools/check_sources.py --repo <target> course/concept-map.md course/outline.md <lessons-dir>` | every cited path exists in the target repo; `path#Symbol` contains the symbol; `path:N` has N lines |
| `tools/lint_lessons.py <lessons-dir> --adapter course/adapter.md` | check types are ones the adapter defines; every lesson has front matter, `assumes`, `sources`, checks or questions, hints, a starter and a solution that differ and parse; no slop phrases or emoji |
| `tools/coverage.py course/concept-map.md course/outline.md --lessons <lessons-dir>` | every concept with priority ≥ 9 is taught; every blast ≥ 3 concept has a `failure` or `capstone` lesson; the rest are taught or deliberate gaps; outline and lesson folders match (`--allow-missing` while lessons are still being written) |

| `tools/screenshots.py --base <url> --page name=/path ...` | screenshots at every width and theme, and horizontal overflow per page; uses a local Playwright or Chromium, never downloads one |

The tools need no network. `tools/` was verified by running every tool inside
a network namespace with no interfaces (`unshare -rn`).

## Worked example

[`examples/signal-lab-ops/`](examples/signal-lab-ops) holds a filled
`concept-map.md` and `outline.md` for a small course about this repository.
All four tools pass on it with `--repo` set to this repository's root. Read it before phase 1 to see the expected depth.

## Reference implementation

[Signal Lab](../../README.md), the OpenTelemetry course in this repository,
was built this way. Reuse its platform in phase 4 when it fits: lesson packs,
the check engine, the runner, the experiment and incident engine, accounts and
the UI are all subject-agnostic. Write a new subject adapter for the target
instead of rebuilding them.
