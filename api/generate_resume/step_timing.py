"""TEMPORARY instrumentation. Delete this file (and its uses in
generator.py) to remove all step-timing logging."""
from __future__ import annotations

import datetime
import functools
import pathlib
import threading
import time
from contextlib import contextmanager

_TIMING_FILE = pathlib.Path.cwd() / "step_timings.txt"

# Track the currently-active step (per thread) so token-usage events that
# come from deep inside the provider can be attributed to the right step.
_current = threading.local()


def _stack() -> list[tuple[str, int | None]]:
    s = getattr(_current, "stack", None)
    if s is None:
        s = []
        _current.stack = s
    return s


def _write_line(line: str) -> None:
    with _TIMING_FILE.open("a") as f:
        f.write(line)


@contextmanager
def time_step(step: str, attempt: int | None = None):
    t0 = time.perf_counter()
    _stack().append((step, attempt))
    try:
        yield
    finally:
        _stack().pop()
        elapsed = time.perf_counter() - t0
        ts = datetime.datetime.now().isoformat(timespec="seconds")
        attempt_str = f"attempt={attempt}  " if attempt is not None else ""
        _write_line(
            f"{ts}  {attempt_str}step={step:<18s}  elapsed={elapsed:.3f}s\n"
        )


def time_call(step: str):
    """Decorator: time a function/method call as ``step``."""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            with time_step(step):
                return fn(*args, **kwargs)
        return wrapper
    return deco


# ---------- token-usage hook ----------
#
# Monkey-patch api.token_usage.record_usage so every LLM call also writes
# a token-count line attributed to the currently-active step. Keeping this
# here (instead of editing provider.py) means deleting this module removes
# all instrumentation in one shot.

def _install_token_hook() -> None:
    try:
        from .. import token_usage as _tu
    except Exception:
        return
    if getattr(_tu, "_step_timing_hooked", False):
        return
    original = _tu.record_usage

    @functools.wraps(original)
    def patched(tier: str, input_tokens: int, output_tokens: int) -> None:
        try:
            stack = _stack()
            step, attempt = stack[-1] if stack else ("(no-step)", None)
            ts = datetime.datetime.now().isoformat(timespec="seconds")
            attempt_str = f"attempt={attempt}  " if attempt is not None else ""
            _write_line(
                f"{ts}  {attempt_str}step={step:<18s}  "
                f"tokens tier={tier} in={int(input_tokens or 0)} "
                f"out={int(output_tokens or 0)}\n"
            )
        except Exception:
            pass
        return original(tier, input_tokens, output_tokens)

    _tu.record_usage = patched
    _tu._step_timing_hooked = True

    # Rebind any modules that already did `from ..token_usage import record_usage`.
    try:
        from ..ai_provider import provider as _prov
        if getattr(_prov, "record_usage", None) is original:
            _prov.record_usage = patched
    except Exception:
        pass


_install_token_hook()
