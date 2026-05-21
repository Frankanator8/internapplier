from __future__ import annotations

from PyQt6.QtCore import QThread


def shutdown_threads(threads: list[QThread], timeout_ms: int = 1500) -> None:
    """Quit and wait on each QThread; terminate as a last resort.

    Called on app close to prevent crashes from QThreads still running while the
    Qt event loop is torn down.
    """
    live = [t for t in threads if t is not None and t.isRunning()]
    for t in live:
        t.quit()
    for t in live:
        if not t.wait(timeout_ms):
            t.terminate()
            t.wait(500)
    threads.clear()
