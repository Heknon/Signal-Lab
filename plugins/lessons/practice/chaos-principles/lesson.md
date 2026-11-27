---
title: What chaos engineering is
summary: Experiments with a hypothesis, a steady state and a way to stop, not breaking things at random.
kind: quiz
minutes: 5
concepts: [steady state, hypothesis, blast radius, abort conditions]
assumes: [SLIs]
quiz:
  questions:
    - id: steady
      prompt: What is a *steady state* in a chaos experiment?
      options:
        - {id: metric, label: "A measurable output that shows the system works for users, like checkout success rate or p95 latency"}
        - {id: cpu, label: "Low CPU and memory on every host"}
        - {id: quiet, label: "A period when nobody is deploying"}
      answer: metric
      explanation: Steady state is defined by what users experience, so you can tell whether the fault actually hurt them.
    - id: hypothesis
      prompt: Which is a usable hypothesis?
      options:
        - {id: good, label: "Storefront checkout success stays above 99% when payments loses one of three instances"}
        - {id: vague, label: "The system is resilient"}
        - {id: break, label: "Let's see what happens if we kill the database"}
      answer: good
      explanation: It names the fault, the steady-state metric and the threshold, so the result is a clear yes or no.
    - id: abort
      prompt: Why does every experiment need an abort condition?
      options:
        - {id: harm, label: "So the fault is removed automatically if customers start to feel it beyond an agreed limit"}
        - {id: time, label: "To keep experiments short"}
        - {id: legal, label: "It's only needed in production"}
      answer: harm
      explanation: Experiments run on real systems. A pre-agreed limit turns "this is getting bad" into an automatic rollback.
    - id: radius
      prompt: You're running your first latency experiment on a payments dependency. What's the right blast radius?
      options:
        - {id: small, label: "Small: one instance or a small share of traffic, for a short time, then widen"}
        - {id: all, label: "All traffic, to make the result unambiguous"}
        - {id: none, label: "Blast radius only matters for error injection"}
      answer: small
      explanation: Start where a wrong guess costs little. Widen once the hypothesis has held at the smaller scope.
    - id: value
      prompt: An experiment's hypothesis is rejected. Was it a waste?
      options:
        - {id: no, label: "No: you found a weakness on your schedule instead of during an outage"}
        - {id: yes, label: "Yes: the goal is to confirm the system is resilient"}
      answer: "no"
      explanation: A rejected hypothesis is the most valuable result. Fix the weakness, then rerun the experiment to prove the fix.
---

Chaos engineering is **experimenting on a system to build confidence that it
copes with turbulent conditions**. It is not breaking things to see what
happens. Every experiment has the same shape:

1. **Steady state**: a metric that says the system is working *for users*.
2. **Hypothesis**: "steady state holds when *this* fault happens".
3. **Inject** a realistic fault: latency, errors, a dependency or instance lost.
4. **Observe** the steady state against the hypothesis.
5. **Abort** automatically if it degrades beyond an agreed limit.
6. **Learn**: fix what broke, then run it again.

Two ideas keep experiments safe: a small **blast radius** (limited traffic,
instances or time) and **abort conditions** that remove the fault on their
own.

In this module you'll run real experiments on the Signal Shop. The lab
injects the fault, charts your steady-state metric live against the
hypothesis, and aborts if the abort line is crossed.

> [!NOTE]
> The shop is shared by everyone using this lab, so only one experiment runs
> at a time. Others can watch it while it runs.
