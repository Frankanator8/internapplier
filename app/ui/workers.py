"""Off-thread job plumbing shared by every page.

A ``Worker`` is a ``QObject`` whose ``work()`` runs on a ``QThread``; a
``WorkerPool`` owns the threads for one widget, wires the signals, and joins
them on shutdown so no QThread outlives the Qt event loop.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Iterable

from PyQt6.QtCore import QObject, QThread, pyqtSignal

logger = logging.getLogger(__name__)


class Worker(QObject):
    """Base class: implement ``work()``; its return value is emitted on ``finished``.

    Exceptions are logged and emitted on ``error`` as a user-facing message.
    """

    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def work(self) -> Any:
        raise NotImplementedError

    def error_message(self, exc: Exception) -> str:
        from api.ai_provider.errors import friendly_error_message
        return friendly_error_message(exc)

    def run(self) -> None:
        name = type(self).__name__
        logger.info("%s.run — start", name)
        try:
            result = self.work()
        except Exception as exc:
            logger.exception("%s.run — failed", name)
            self.error.emit(self.error_message(exc))
            return
        logger.info("%s.run — done", name)
        self.finished.emit(result)


def _provider_call(method: str, args: tuple, kwargs: dict) -> Callable[[], Any]:
    def call():
        from api.ai_provider import get_provider
        return getattr(get_provider(), method)(*args, **kwargs)
    return call


class CallWorker(Worker):
    """Run one blocking callable off-thread."""

    def __init__(self, fn: Callable[..., Any], *args, **kwargs):
        super().__init__()
        self._fn, self._args, self._kwargs = fn, args, kwargs

    @classmethod
    def provider(cls, method: str, *args, **kwargs) -> "CallWorker":
        """Call ``get_provider().<method>(*args, **kwargs)`` on the worker thread."""
        return cls(_provider_call(method, args, kwargs))

    def work(self) -> Any:
        return self._fn(*self._args, **self._kwargs)


class StreamWorker(Worker):
    """Drain a text generator off-thread, emitting each delta on ``chunk``.

    ``finished`` carries the full joined text.
    """

    chunk = pyqtSignal(str)

    def __init__(self, fn: Callable[..., Iterable[str]], *args, **kwargs):
        super().__init__()
        self._fn, self._args, self._kwargs = fn, args, kwargs

    @classmethod
    def provider(cls, method: str, *args, **kwargs) -> "StreamWorker":
        """Stream ``get_provider().<method>(*args, **kwargs)`` on the worker thread."""
        return cls(_provider_call(method, args, kwargs))

    def work(self) -> str:
        buf: list[str] = []
        for delta in self._fn(*self._args, **self._kwargs):
            buf.append(delta)
            self.chunk.emit(delta)
        return "".join(buf)


class WorkerPool(QObject):
    """Owns the worker threads started on behalf of one widget.

    Created as a child of that widget, so ``MainWindow`` can find every pool
    with ``findChildren(WorkerPool)`` and join them all on close.
    """

    def __init__(self, parent: QObject):
        super().__init__(parent)
        self._jobs: dict[QThread, QObject] = {}

    @property
    def busy(self) -> bool:
        return bool(self._jobs)

    def start(
        self,
        worker: Worker,
        *,
        finished: Callable | None = None,
        error: Callable | None = None,
        **signal_slots: Callable,
    ) -> QThread:
        """Run ``worker`` on a new thread.

        ``finished``/``error`` connect to the worker's terminal signals; any
        other keyword connects the worker signal of that name (``progress=``,
        ``chunk=``…). The thread quits itself on either terminal signal — the
        quit is queued ahead of the callbacks, so a callback that opens a
        nested event loop (a modal dialog) doesn't run over a live thread.
        """
        thread = QThread(self)
        worker.moveToThread(thread)
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        if finished is not None:
            worker.finished.connect(finished)
        if error is not None:
            worker.error.connect(error)
        for name, slot in signal_slots.items():
            getattr(worker, name).connect(slot)
        thread.started.connect(worker.run)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: self._jobs.pop(thread, None))
        self._jobs[thread] = worker
        thread.start()
        return thread

    def shutdown(self, timeout_ms: int = 1500) -> None:
        """Quit and wait on every live thread; terminate as a last resort."""
        live = []
        for t in list(self._jobs):
            try:
                if t.isRunning():
                    live.append(t)
            except RuntimeError:
                # Already deleted on the C++ side — nothing to wait on.
                continue
        for t in live:
            t.quit()
        for t in live:
            if not t.wait(timeout_ms):
                t.terminate()
                t.wait(500)
        self._jobs.clear()
