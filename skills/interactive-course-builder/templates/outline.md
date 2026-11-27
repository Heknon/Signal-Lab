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

| id | Title | Kind | Min | Concepts | Assumes | Sources | Learner produces | Checks observe |
|---|---|---|---|---|---|---|---|---|
| {{track-id/lesson-slug}} | {{title}} | {{code / config / query / quiz / task / experiment / incident}} | {{3-15}} | {{concept-id, concept-id}} | {{lesson title or "nothing"}} | `{{src/x.py#func}}` | {{code / config / query / answer}} | {{what the checks read}} |

## Progression

For each track, which lessons are: happy path → shape and options → failure
modes → judgment → capstone.

| Track | Happy path | Options | Failure modes | Judgment | Capstone |
|---|---|---|---|---|---|
| {{track-id}} | {{lesson ids}} | {{lesson ids}} | {{lesson ids}} | {{lesson ids}} | {{lesson ids}} |

## Capstone incidents

| id | Symptom brief | Hidden fault | Misleading symptom | Signals | When / where / what | Evidence query |
|---|---|---|---|---|---|---|
| {{track-id/incident-slug}} | {{"checkout spins, but not for everyone"}} | {{fault from adapter.md}} | {{where it hurts but isn't}} | `{{metric:name}}` | {{answers}} | `{{query}}` |

## Decisions

- {{anything decided without asking, and why}}
