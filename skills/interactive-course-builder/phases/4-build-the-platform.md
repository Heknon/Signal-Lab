# Phase 4: Build the platform

**Goal:** a running web app that serves lessons, runs learner work in a
sandbox, grades it with the check engine, and injects faults: everything
`adapter.md` describes.

**Read:** `course/adapter.md`, [platform](../references/platform.md),
[UI rules](../references/ui-rules.md), [team mode](../references/team-mode.md),
[air-gapped operation](../references/air-gapped.md).

**Produce:** the platform code, a one-command start (`docker compose up` or
equivalent), and `course/platform.md` from [`templates/platform.md`](../templates/platform.md)
(how to run it, where content lives, which check types and lesson kinds exist).

## Checklist

1. [ ] **Reuse first.** If an existing platform fits (Signal Lab in this
   repository is one, see [platform](../references/platform.md)), use it and
   write only the subject adapter: backend or runner plugins, check types,
   scenario services. Record the decision in `platform.md`.
2. [ ] **Content as folders.** Lessons, subject adapters and scenarios live in
   plugin folders that are loaded at start-up and hot-reloaded in development.
   Adding a lesson never requires changing platform code.
3. [ ] **Runner / sandbox.** Executes learner work exactly as the adapter
   describes. It runs in a separate process or container: non-root, read-only
   filesystem except a scratch dir, dropped capabilities, CPU, memory, process and
   time limits, and network restricted to what lessons need. It streams output
   live.
4. [ ] **Observation.** Implement each observable from `adapter.md`, with run
   attribution. Show what was observed to the learner (an inspector panel), not
   just pass/fail.
5. [ ] **Check engine.** Evaluates a lesson's checks against observations,
   repeatedly while results arrive (pending → pass/fail), with explanatory
   failure messages. Answers and reference solutions never reach the browser.
6. [ ] **Faults, experiments and incidents.** A timeline engine applies faults
   at offsets, samples a steady-state signal, aborts at a limit, always cleans
   up (also on crash and on expiry), and allows one shared activity at a time.
7. [ ] **UI.** Course map with progress, lesson page (prose and goals on one
   side, a workbench on the other), workbench per lesson kind, a search and
   command palette, and a page showing the running stack and loaded plugins.
   Follow [UI rules](../references/ui-rules.md) from the first screen, not as a
   later fix.
8. [ ] **Progress and accounts.** Local single-user mode with no login, and an
   accounts mode for teams ([team mode](../references/team-mode.md)).
9. [ ] **Packaging.** One command starts everything with the default
   components. Optional heavy components are opt-in. Provide a Helm chart or
   equivalent if the audience deploys to Kubernetes. Pin every version.
10. [ ] **Air-gapped build.** Nothing fetched at runtime: fonts, scripts, editor
    language packs, plugins and images are all local ([air-gapped operation](../references/air-gapped.md)).
11. [ ] **Smoke test.** Write one trivial lesson end to end (starter fails,
    solution passes) before writing the rest.

## Exit criteria

- One command starts the app; the smoke lesson fails with its starter and passes with its solution.
- `python <skill>/tools/lint_artifacts.py course/platform.md` passes: `course/platform.md` lists the start command, content folders, lesson kinds and check types.
- The runner's isolation settings are written down in `platform.md`.

## Common mistakes

- Executing learner code inside the API process.
- A UI that hides observations, so learners see only a red cross.
- Fetching fonts or libraries from a CDN.
