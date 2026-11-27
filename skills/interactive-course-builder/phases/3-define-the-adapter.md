# Phase 3: Define the subject adapter

**Goal:** decide exactly how learners interact with the target system, what the
checks can observe, and which faults can be injected. This is the bridge
between a generic course platform and this particular subject.

**Read:** `course/outline.md`, [subject adapter template](../references/adapter-template.md),
[check patterns](../references/check-patterns.md).

**Produce:** `course/adapter.md`, from [`templates/adapter.md`](../templates/adapter.md).

## Checklist

1. [ ] **Learner outputs.** For each lesson kind in the outline, define what the
   learner submits: code (which language, which entry point), config (which
   file, merged with what base), queries (which language, against what data),
   actions in a UI (which UI, verified through which API), or answers. For
   answer-only kinds (quiz), "none: graded from the answer key" is a valid
   execution path.
2. [ ] **Execution.** For code and config: how is it run, with what
   environment, in what sandbox, with what timeout and limits? It must be the
   way the system really runs it, the same CLI or entry point.
3. [ ] **Observable state.** List every source the checks read, with how to
   read it: captured output, HTTP responses, database rows, files, telemetry
   captured by a tap, metrics or query APIs. For each: latency (how long until
   it's visible) and how to attribute it to one learner run (a run id in a
   header, label, resource attribute, namespace, schema or temp dir).
4. [ ] **Check types.** From [check patterns](../references/check-patterns.md),
   pick the types the course needs and define any new ones: name, parameters,
   pass condition, and the failure message. This table is the complete list of
   `type:` values lessons may use; `lint_lessons.py --adapter` enforces it.
5. [ ] **Scenario.** The live system that query lessons, experiments and
   incidents run against: which components, what background traffic, how it's
   reset. Prefer the subject's own example app or a small, realistic one.
6. [ ] **Fault catalogue.** For every incident and failure-mode lesson, the fault
   that causes it: name, parameters, how it's injected (API, flag, env var,
   config reload, restart), how it's removed, and the evidence it produces.
   Faults must be **reversible** and **time-boxed**. Use the same fault ids the
   outline's capstone incidents name; add any that are missing.
7. [ ] **Isolation.** What stops one learner's run from affecting another's,
   and what is deliberately shared (for example one scenario for a team game day)?
8. [ ] **Spike it.** Before phase 4, prove the riskiest assumption with a
   throwaway script: run one learner submission, read one observable, inject one
   fault and see its evidence. Paste the output into the artifact. One fault
   is enough here; phase 6's incident suite proves the rest.

## Exit criteria

- `python <skill>/tools/lint_artifacts.py course/adapter.md` passes.
- Every lesson kind in the outline has an output, an execution path and at least one check type.
- Every incident in the outline maps to a fault in the catalogue (checked by
  `lint_artifacts.py` when `outline.md` sits next to `adapter.md`).
- The spike output is in the artifact.

## Common mistakes

- Checks that read the learner's source text instead of what it did.
- Faults that can't be undone without restarting everything.
- No run attribution, so two runs (or two learners) see each other's results.
