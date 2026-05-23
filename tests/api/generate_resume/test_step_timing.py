"""Light tests for step_timing — the monkey-patch hook is module-level
so we mostly verify the time_step + decorator scaffolding works."""
from __future__ import annotations

from api.generate_resume import step_timing


def test_time_step_writes_a_line(tmp_path, monkeypatch):
    log = tmp_path / "timings.txt"
    monkeypatch.setattr(step_timing, "_TIMING_FILE", log)
    with step_timing.time_step("my-step", attempt=1):
        pass
    content = log.read_text()
    assert "step=my-step" in content
    assert "attempt=1" in content
    assert "elapsed=" in content


def test_time_call_decorator(tmp_path, monkeypatch):
    log = tmp_path / "timings.txt"
    monkeypatch.setattr(step_timing, "_TIMING_FILE", log)

    @step_timing.time_call("decorated")
    def fn(x):
        return x * 2

    assert fn(3) == 6
    content = log.read_text()
    assert "step=decorated" in content


def test_stack_isolated_per_thread():
    # Sanity — _stack returns the same list within a thread
    s1 = step_timing._stack()
    s2 = step_timing._stack()
    assert s1 is s2
