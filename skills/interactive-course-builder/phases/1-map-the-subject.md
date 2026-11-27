# Phase 1: Map the subject

**Goal:** know the target system well enough to decide what is worth teaching,
grounded in its real code and configuration.

**Read:** `course/environment.md`, then the target codebase or technology:
source, configs, docs, examples, tests, changelog, and the way it's deployed.
Use only what is on disk; there is no issue tracker or web search.

**Produce:** `course/concept-map.md`, from [`templates/concept-map.md`](../templates/concept-map.md).

## Checklist

1. [ ] **Inventory the system.** List the top-level components, entry points,
   config files, public APIs, CLI commands, and the signals it emits (logs,
   metrics, traces, events, files, exit codes). Record real paths.
2. [ ] **Find where engineers spend time.** Use evidence in this order:
   - files that change most often (`git log --format= --name-only | sort | uniq -c | sort -rn | head -50`)
   - the most-used config keys and flags in examples, tests and docs
   - bugs and confusion, offline: commit subjects with "fix", "regression",
     "revert" or "clarify" (`git log --format=%s | grep -iE 'fix|regress|revert|clarif'`);
     changelog entries; regression tests; `FIXME`, `XXX` and "note:" comments;
     warnings and "common mistakes" in the docs folder; FAQ or troubleshooting pages
   - the "getting started" path in the official docs
3. [ ] **List candidate concepts.** One concept is one idea a learner can use or
   misuse: "context propagation", "connection pool sizing", "retry policy".
   Size by core source (all of the main package, excluding tests, docs and
   vendored code; `environment.md` shows the line count): under 10k lines,
   15–30 concepts; 10k–100k lines, 30–60; larger, 50–80.
4. [ ] **Score each concept** from 1 to 5 on:
   - **Frequency:** how often an engineer touches it in normal work.
   - **Blast radius:** how bad it is when someone gets it wrong.
   - **Confusion:** how often newcomers misunderstand it. Cite local evidence:
     a commit, changelog entry, regression test, doc warning or code comment.
     No evidence means confusion ≤ 2.

   Priority = frequency + blast radius + confusion (3–15).
5. [ ] **Cite artifacts for every concept.** At least one real path, symbol,
   config key, command or metric name per concept. If you can't find one, the
   concept is either not part of this system or you haven't looked enough.
6. [ ] **Record failure modes** for each concept with blast radius ≥ 3: what
   breaks, what the symptom looks like, and which signal shows it. These become
   incidents in phase 2. **Confirm each one** by reading the code path or
   running a few lines against the installed target; memory of how a library
   behaves is often wrong.
7. [ ] **Write the deliberate gaps.** Concepts you saw and chose not to teach,
   each with a reason (out of scope, deprecated, too rare, needs hardware...).
   Nothing may be missed *by accident*. Use the concept's **id** from the
   Concepts table. Every concept with priority below 9 that you don't expect to
   teach goes here now; phase 2's coverage check fails on any that is neither
   taught nor listed.
8. [ ] **Note the observable surface.** What can a checker read without
   trusting the learner? Process output, HTTP responses, database state, files,
   telemetry, metrics endpoints, logs, CLI exit codes. Phase 3 builds on this.
   A library with no telemetry is observed through its API surface: return
   values, exceptions, the requests it sends to a local test server, files it
   writes. Use those as the "signal" for its failure modes.

## Exit criteria

- `python <skill>/tools/lint_artifacts.py course/concept-map.md` passes.
- Every concept row has a score, a priority and at least one artifact citation.
- `python <skill>/tools/check_sources.py --repo <target> course/concept-map.md` finds every cited path.
- The deliberate-gaps section is present (it may say "none", with a reason).

## Common mistakes

- Listing chapter titles from the official docs instead of concepts. Docs are
  organised for reference, not for learning.
- Scoring everything 4–5. Force a spread: at most a quarter of the concepts get priority ≥ 12.
- Citing a directory when the concept lives in one file or one config key.
