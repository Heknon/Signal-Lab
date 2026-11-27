---
title: "{{Sentence-case title naming the idea}}"
summary: "{{One sentence: what the learner will be able to do.}}"
kind: code
minutes: 8
concepts: ["{{concept-id}}"]
assumes: ["{{Lesson title or plain-words skill}}"]
sources:
  - "{{src/real/file.py#Symbol}}"
hints:
  - "{{Where to look.}}"
  - "{{What to compare or which API to use.}}"
  - "{{Nearly the answer.}}"
checks:
  - id: "{{short-id}}"
    type: "{{span | trace | metric | log | output | exit | budget | query | backend}}"
    title: "{{Goal phrased as a fact, e.g. `checkout` carries `app.user.id`}}"
    where: {name: "{{entity}}"}
---

{{Why this matters, in one or two sentences, grounded in the target system.}}

```python
# {{a minimal snippet copied or adapted from the cited source}}
```

{{The idea: what to know, with real names and concrete numbers.}}

## Try it

1. {{Exactly what to change in the starter.}}
2. Run it.
3. {{What to look at in the result panel, and what you should see.}}
