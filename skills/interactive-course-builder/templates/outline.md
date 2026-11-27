# Course outline: {{subject}}

Replace every `{{...}}` placeholder. One `### Module` section per module, one
table row per lesson. `tools/coverage.py` reads the **Concepts** column.

## Tracks

| Track id | Title | For whom | Requires |
|---|---|---|---|
| {{track-id}} | {{Sentence-case title}} | {{who should take it}} | {{optional component, or "none"}} |

## Lessons

### Module: {{track-id}}/{{module-id}}: {{Module title}}

- **Assumes:** {{plain words, e.g. "SQL joins"}}
- **Skip if:** {{what an experienced person already does}}

Stage is one of `happy` (use it correctly), `options` (the settings people
use), `failure` (something breaks; fix or diagnose it), `judgment` (when to use
it, when not, what it costs) and `capstone` (incidents). Order lessons by stage.

| id | Title | Kind | Stage | Min | Concepts | Assumes | Sources | Learner produces | Checks observe |
|---|---|---|---|---|---|---|---|---|---|
| {{track-id/lesson-slug}} | {{title}} | {{code / config / query / quiz / task / experiment / incident}} | {{happy / options / failure / judgment / capstone}} | {{3-15}} | {{concept-id, concept-id}} | {{lesson title or "nothing"}} | `{{src/x.py#func}}` | {{code / config / query / answer}} | {{what the checks read}} |

## Capstone incidents

`Fault` names fault ids from the adapter's fault catalogue (phase 3 adds any
that are missing). `Evidence` is a query, command or check against the
scenario: whatever the adapter can observe.

| id | Symptom brief | Hidden fault | Fault | Misleading symptom | Signals | When / where / what | Evidence |
|---|---|---|---|---|---|---|---|
| {{track-id/incident-slug}} | {{"checkout spins, but not for everyone"}} | {{the mechanism}} | `{{fault-id}}` | {{where it hurts but isn't}} | `{{metric:name}}` | {{answers}} | `{{query}}` |

## Decisions

- {{anything decided without asking, and why}}
