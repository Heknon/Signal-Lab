# Platform

The platform is subject-agnostic. Everything subject-specific is a plugin
(see [adapter template](adapter-template.md)).

## Required capabilities

| Capability | Minimum |
|---|---|
| Content loading | tracks, modules and lessons from folders; hot reload in development; broken content reported, not fatal |
| Runner | separate process or container; non-root; read-only FS plus scratch; CPU, memory, PID and time limits; restricted network; live output |
| Check engine | pattern checks with explanatory details; pending → final; answers never sent to the browser |
| Inspector | shows what was observed (not just pass/fail), with links into the subject's own tools |
| Query workbench | editor with highlighting and completion; table and chart results; time range |
| Experiments and incidents | timeline engine, steady-state sampling, abort limit, guaranteed cleanup, one shared activity at a time |
| Progress | done / known / todo per lesson; "continue" jumps to the next unfinished lesson; nothing is locked by progress |
| Accounts | open mode (no login) and accounts mode ([team mode](team-mode.md)) |
| Packaging | one-command start; optional components opt-in; pinned versions; a deployment chart |
| Offline | no runtime network fetches ([air-gapped](air-gapped.md)) |

## Reusing Signal Lab

This repository's platform implements all of the above. To reuse it for a new subject:

1. Keep `server/`, `web/`, `charts/` and `deploy/`.
2. Replace `plugins/scenarios/shop` with a scenario for your subject (same
   `/_stats`, `/_chaos` and `/_load` contract), or keep it if it fits.
3. Add backend plugins for the subject's stores and UIs (`plugins/backends/<id>`).
4. If learners write something other than Python or Collector YAML, add an
   execution mode to `server/signal_lab/runner.py` (see how `collector_config`
   runs a second process next to the learner's program).
5. Add check types in `server/signal_lab/checks.py` (`CHECKS` registry) or in
   a backend adapter's `verify()`.
6. Write lesson packs in `plugins/lessons/<track>/`.
7. Run `scripts/test_lessons.py` and `scripts/test_incidents.py`.

Lesson kinds already supported: `code`, `collector` (config + traffic),
`query`, `quiz`, `task`, `experiment` and `incident`. Check types: `span`,
`trace`, `map` (service-map arrows), `metric`, `log`, `budget`, `output`, `exit`, `query`, `backend`, plus
the question kinds `time`, `outcome` and `query`.

## Building from scratch

When reuse doesn't fit, build the same shape:

```text
browser ──▶ app (lessons, checks, progress, faults)
              │ submit
              ▼
           runner (sandbox) ──▶ target system ──▶ observable state
              ▲                                       │
              └──────── check engine reads ◀──────────┘
```

Build the smallest vertical slice first: one lesson of each kind, from
submission to graded result. Then add content.
