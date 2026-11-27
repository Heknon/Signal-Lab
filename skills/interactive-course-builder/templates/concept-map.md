# Concept map: {{subject}}

Replace every `{{...}}` placeholder. `tools/lint_artifacts.py` fails while any remain.

## Subject

- **Target:** {{name, version or commit, where the code lives}}
- **Audience:** {{who takes this course and what they already know}}
- **Evidence used:** {{git history range, docs, issues, tests that informed the scores}}

## Inventory

| Component | Kind | Artifacts |
|---|---|---|
| {{component}} | {{service / library / CLI / config}} | `{{path/to/file.py}}`, `{{path/to/config.yaml#key}}` |

## Concepts

Scores are 1–5. Priority = frequency + blast + confusion. Cite artifacts as
backticked repo paths (`path`, `path#symbol`, `path:line`). For citations that
are not files, use a prefix: `metric:`, `cmd:`, `key:`, `api:`, `doc:`.

| id | Concept | Freq | Blast | Confusion | Priority | Artifacts | Confusion evidence |
|---|---|---|---|---|---|---|---|
| {{concept-id}} | {{one idea a learner can use or misuse}} | {{1-5}} | {{1-5}} | {{1-5}} | {{3-15}} | `{{src/x.py#func}}` | {{issue, doc warning or common bug}} |

## Failure modes

For every concept with blast ≥ 3. A signal is whatever the system exposes: a
metric, log line, trace, exception class, return value, HTTP status, exit code
or file. Libraries without telemetry are observed through their API surface.

| Concept | What breaks | Symptom | Signal that shows it |
|---|---|---|---|
| {{concept-id}} | {{mechanism}} | {{what a user or on-call sees}} | `{{metric:name}}` / `{{log message}}` |

## Observable surface

| Source | How to read it | Latency | Attribution |
|---|---|---|---|
| {{stdout / HTTP / DB / telemetry / files}} | {{API, query, tap}} | {{seconds}} | {{run id in header, label, schema...}} |

## Deliberate gaps

Concepts seen and deliberately not taught. Write "None" with a reason if empty.

| Concept | Reason |
|---|---|
| {{concept-id (an id from the Concepts table, not a name)}} | {{out of scope / deprecated / too rare / needs hardware}} |
