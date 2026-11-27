# Platform: {{subject}}

Replace every `{{...}}` placeholder.

## Decision

{{Reused Signal Lab / another platform / built from scratch, and why.}}

## Start

```bash
{{one command that starts everything with the default components}}
```

Optional components: {{how to enable each one}}

## Content

| Folder | Holds |
|---|---|
| `{{plugins/lessons/<track>/}}` | {{lesson packs}} |

## Lesson kinds

| Kind | Workbench | Graded by |
|---|---|---|
| {{code}} | {{editor + console + inspector}} | {{check types}} |

## Check types

| Type | Reads | Defined in |
|---|---|---|
| {{span}} | {{captured telemetry}} | `{{server/checks.py}}` |

## Runner isolation

| Control | Setting |
|---|---|
| User | {{non-root uid}} |
| Filesystem | {{read-only + scratch}} |
| Limits | {{CPU, memory, PIDs, timeout}} |
| Network | {{what is reachable}} |

## Smoke lesson

{{lesson id; starter result; solution result}}
