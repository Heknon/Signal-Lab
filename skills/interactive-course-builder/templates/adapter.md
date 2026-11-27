# Subject adapter: {{subject}}

Replace every `{{...}}` placeholder. See `references/adapter-template.md`.

## Learner outputs

| Lesson kind | Learner submits | Language / format | Entry point | Merged with |
|---|---|---|---|---|
| {{code}} | {{a program}} | {{Python 3.13}} | `{{main.py}}` | {{nothing / base config}} |

## Execution

| Kind | Command | Environment | Sandbox and limits | Timeout |
|---|---|---|---|---|
| {{code}} | `{{the real CLI}}` | {{env vars injected, incl. run id}} | {{container, non-root, read-only, mem/cpu/pids}} | {{seconds}} |

## Observable state

| Source | Read by | Latency | Attribution |
|---|---|---|---|
| {{stdout}} | {{runner stream}} | {{0 s}} | {{one stream per run}} |

## Check types

These names are the only valid `type:` values in lesson checks
(`lint_lessons.py --adapter` enforces it). Reuse names from
`references/check-patterns.md` where they fit. Quiz-style lessons may use
"none: graded from the answer key" as their execution path.

| Type | Parameters | Passes when | Failure message example |
|---|---|---|---|
| {{span}} | {{where, count}} | {{a matching entity exists}} | {{"No span named X. Did you mean Y?"}} |

## Scenario

- **Components:** {{services, with real names from the target}}
- **Background traffic:** {{generator and rate}}
- **Reset:** {{how it returns to healthy}}

## Fault catalogue

Every `Fault` id used by the outline's capstone incidents must appear here.
The spike proves one fault; phase 6 proves the rest.

| Fault | Parameters | Injected by | Removed by | Time limit | Evidence |
|---|---|---|---|---|---|
| `{{fault-id}}` | {{latency_ms}} | `{{POST /_chaos}}` | `{{{"reset": true}}}` | {{TTL}} | `{{metric or log}}` |

## Isolation

- **Per run:** {{what keeps runs apart}}
- **Shared on purpose:** {{the scenario, game days}}

## Spike

Command:

```text
{{exact command}}
```

Output:

```text
{{pasted output proving submit → observe → fault → evidence}}
```
