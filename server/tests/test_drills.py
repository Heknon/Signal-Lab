import asyncio

from signal_lab.drills import Drills


def make(values):
    applied, resets = [], []
    it = iter(values)

    async def apply(f):
        applied.append(f)

    async def load(rps):
        pass

    async def reset():
        resets.append(1)

    async def query(b, l, q):
        return next(it, values[-1])

    return Drills(apply, load, reset, query), applied, resets


SPEC = {"steady_state": {"query": "x", "threshold": 1.0, "abort_at": 3.0, "interval_s": 0.01}, "baseline_s": 0.05, "duration_s": 0.1, "recovery_s": 0.05, "inject": {"inventory": {"latency_ms": 300}}}


def run(drills, spec):
    async def go():
        act = drills.start("experiment", "p/x", "x", "ada", spec)
        await drills._task
        return act
    return asyncio.run(go())


def test_hypothesis_holds():
    d, applied, resets = make([0.2] * 200)
    act = run(d, SPEC)
    assert act.status == "done" and act.hypothesis_held is True
    assert applied == [{"inventory": {"latency_ms": 300}}] and resets  # fault applied once, then cleared


def test_abort_removes_fault():
    d, applied, resets = make([0.2] * 6 + [5.0] * 200)
    act = run(d, SPEC)
    assert act.status == "aborted" and act.hypothesis_held is False and "Abort" in act.reason
    assert len(resets) >= 2  # reset at start and again on abort


def test_below_direction():
    spec = SPEC | {"steady_state": SPEC["steady_state"] | {"direction": "below", "threshold": 0.9, "abort_at": 0.1}}
    d, _, _ = make([0.99] * 6 + [0.7] * 200)
    act = run(d, spec)
    assert act.status == "done" and act.hypothesis_held is False


def test_one_at_a_time():
    d, _, _ = make([0.2] * 200)

    async def go():
        d.start("experiment", "p/x", "x", "ada", SPEC | {"duration_s": 5})
        try:
            d.start("experiment", "p/y", "y", "bob", SPEC)
            return False
        except RuntimeError:
            return True
        finally:
            await d.stop()

    assert asyncio.run(go())
