"""Structured per-question trace: each step's name, path, time, cost and model, for the console."""
import contextvars
import time
from contextlib import contextmanager

_current: contextvars.ContextVar = contextvars.ContextVar("downshift_trace", default=None)


@contextmanager
def collect():
    steps: list[dict] = []
    token = _current.set({"t0": time.perf_counter(), "steps": steps})
    try:
        yield steps
    finally:
        _current.reset(token)


def step(name: str, kind: str, ms: float = 0, cost: float = 0.0, model: str | None = None,
         ok: bool = True, detail: str | None = None):
    cur = _current.get()
    if cur is None:
        return
    end = (time.perf_counter() - cur["t0"]) * 1000
    cur["steps"].append({"name": name, "kind": kind, "startMs": round(max(0.0, end - ms)), "ms": round(ms),
                         "cost": round(cost, 6), "model": model, "ok": ok, "detail": detail})


@contextmanager
def timed():
    box = {"ms": 0.0}
    t0 = time.perf_counter()
    try:
        yield box
    finally:
        box["ms"] = (time.perf_counter() - t0) * 1000
