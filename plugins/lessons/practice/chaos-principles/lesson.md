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
        - {id: metric, label: "A user-facing measure, like checkout success rate or p95 latency, within its normal range"}
        - {id: cpu, label: "CPU, memory and connection counts on every host within their normal range"}
        - {id: errors, label: "Zero error logs from every service for the duration of the experiment"}
        - {id: quiet, label: "A period with no deploys, so any change you see comes from the fault"}
      answer: metric
      explanation: Steady state is defined by what users experience, so you can tell whether the fault actually hurt them. Host metrics and error logs move for reasons users never notice, and some log errors even when everything is fine.
    - id: hypothesis
      prompt: Which is a usable hypothesis?
      options:
        - {id: good, label: "Checkout success stays above 99% while payments has 300 ms of extra latency"}
        - {id: direction, label: "Checkout gets slower when payments gets slower"}
        - {id: survives, label: "The shop survives losing payments"}
        - {id: watch, label: "Add 300 ms to payments and watch the dashboards"}
      answer: good
      explanation: It names the fault, the steady-state metric and the threshold, so the result is a clear yes or no. "Gets slower" is always true and says nothing about users; "survives" has no measure; watching dashboards has no hypothesis at all.
    - id: abort
      prompt: Why does every experiment need an abort condition?
      options:
        - {id: harm, label: "So the fault is removed automatically if customers feel it beyond an agreed limit"}
        - {id: confirmed, label: "So the experiment stops as soon as the hypothesis is confirmed, saving time"}
        - {id: oncall, label: "So on-call knows an experiment is running and doesn't page anyone"}
        - {id: data, label: "So the experiment collects enough data before it's allowed to stop"}
      answer: harm
      explanation: Experiments run on real systems. A pre-agreed limit turns "this is getting bad" into an automatic rollback. Stopping early on success would hide a slow degradation, and an abort limit doesn't replace telling on-call.
    - id: radius
      prompt: You're running your first latency experiment on a payments dependency. What's the right blast radius?
      options:
        - {id: small, label: "One instance or a small share of traffic, for a short time, then widen"}
        - {id: all, label: "All traffic for a short time, so the signal is strong enough to read"}
        - {id: staging, label: "Only staging, until the system has passed in production once"}
        - {id: offpeak, label: "All traffic, but only off-peak, when fewer customers are affected"}
      answer: small
      explanation: Start where a wrong guess costs little, in the environment you actually care about. Widen once the hypothesis has held at the smaller scope. Off-peak still hits everyone who is using the shop.
    - id: value
      prompt: An experiment's hypothesis is rejected. What was it worth?
      options:
        - {id: "found", label: "A weakness found on your schedule instead of during an outage"}
        - {id: "nothing", label: "Little: the goal is to show the system is resilient, so it has to be rerun"}
        - {id: "rollback", label: "It's a failed change: roll back whatever the experiment touched and move on"}
      answer: "found"
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
