"""PDF viewing and live LaTeX compile previews.

Imports QtWebEngine at module level: it must be loaded before the
QApplication is constructed, so importing this module early is the point.
"""
from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path
from typing import Callable

from PyQt6.QtCore import Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtWebEngineCore import QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QLabel, QPlainTextEdit, QStackedWidget

from .widgets import label, mono_font
from .workers import Worker, WorkerPool

logger = logging.getLogger(__name__)

COMPILE_DEBOUNCE_MS = 800

# A compile function takes LaTeX and returns {"pdf": path, "fill": float}
# and/or {"note": str}. It runs on a worker thread.
CompileFn = Callable[[str], dict]


def compile_with_fill(latex: str) -> dict:
    """Compile LaTeX to a fresh temp PDF and measure its page fill."""
    from api.generate_resume.compile import pdf_page_metrics
    from api.generate_resume.preview import compile_latex_preview

    pdf = compile_latex_preview(latex)
    return {"pdf": str(pdf), "fill": float(pdf_page_metrics(pdf)["fill"])}


def compile_template(template: str) -> dict:
    """Compile a resume template filled with sample data."""
    from api.generate_resume.preview import compile_template_preview

    pdf, note = compile_template_preview(template)
    return {"pdf": str(pdf), "note": note or ""}


def page_fill_status(fill: float) -> tuple[str, str]:
    """``(status state, text)`` describing ``fill`` against the page cap."""
    from api.ai_provider import get_resume_page_cap

    cap = get_resume_page_cap()
    overflow = fill > cap + 1e-6
    text = f"{fill:.2f} / {cap} page{'s' if cap != 1 else ''}"
    return ("error", text + " — over the page cap") if overflow else ("ok", text)


class PdfView(QWebEngineView):
    """WebEngine view with the built-in PDF viewer enabled."""

    def __init__(self, parent=None):
        super().__init__(parent)
        settings = self.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.PdfViewerEnabled, True)
        self._copies: tempfile.TemporaryDirectory | None = None
        self._copy_n = 0

    def show_pdf(self, path: str, *, bust_cache: bool = False) -> None:
        """Load ``path``. WebEngine caches by URL, so a file rewritten in place
        needs ``bust_cache`` to be shown from a fresh temp copy."""
        if bust_cache and Path(path).is_file():
            path = self._fresh_copy(path) or path
        self.setUrl(QUrl.fromLocalFile(path))

    def clear(self) -> None:
        self.setUrl(QUrl("about:blank"))

    def _fresh_copy(self, path: str) -> str | None:
        if self._copies is None:
            self._copies = tempfile.TemporaryDirectory(prefix="pdf_view_")
        root = Path(self._copies.name)
        prev = root / f"view_{self._copy_n}.pdf"
        self._copy_n += 1
        dest = root / f"view_{self._copy_n}.pdf"
        try:
            shutil.copyfile(path, dest)
        except OSError:
            logger.exception("PdfView — copy failed")
            return None
        prev.unlink(missing_ok=True)
        return str(dest)


class _CompileWorker(Worker):
    def __init__(self, compile_fn: CompileFn, latex: str):
        super().__init__()
        self._compile_fn = compile_fn
        self._latex = latex

    def work(self) -> dict:
        return {**self._compile_fn(self._latex), "latex": self._latex}

    def error_message(self, exc: Exception) -> str:
        log_excerpt = getattr(exc, "log_excerpt", "")
        return f"{exc}\n\n{log_excerpt}" if log_excerpt else str(exc)


class LatexPreviewPane(QStackedWidget):
    """Placeholder / compiled PDF / compiler log, driven by off-thread compiles.

    ``source`` produces the LaTeX at compile time. Compiles requested while
    one is running are coalesced into a single follow-up, so the preview
    always converges on the latest source. Results are reported through
    ``compiled(result)`` (result has ``pdf``, ``latex`` and ``fill`` or
    ``note``) and ``failed(log)``; ``busy_changed`` brackets each compile.
    """

    busy_changed = pyqtSignal(bool)
    compiled = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, source: Callable[[], str], compile_fn: CompileFn, placeholder: str, parent=None):
        super().__init__(parent)
        self._source = source
        self._compile_fn = compile_fn
        self._pool = WorkerPool(self)
        # Our own flag, not pool.busy: the thread is still winding down when
        # the result callbacks run, and a queued follow-up must start then.
        self._busy = False
        self._pending = False
        self.pdf_path: str | None = None

        self._placeholder: QLabel = label(placeholder, "muted", wrap=True)
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.view = PdfView()
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setFont(mono_font())
        for w in (self._placeholder, self.view, self._log):
            self.addWidget(w)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(COMPILE_DEBOUNCE_MS)
        self._timer.timeout.connect(self.compile_now)

    @property
    def busy(self) -> bool:
        return self._busy

    def schedule(self) -> None:
        """Compile after a short quiet period (for as-you-type edits)."""
        self._timer.start()

    def compile_now(self) -> None:
        self._timer.stop()
        if self._busy:
            self._pending = True
            return
        self._busy = True
        self.busy_changed.emit(True)
        self._pool.start(
            _CompileWorker(self._compile_fn, self._source()),
            finished=self._on_compiled,
            error=self._on_failed,
        )

    def cancel_pending(self) -> None:
        """Drop any scheduled or queued compile (the running one still reports)."""
        self._timer.stop()
        self._pending = False

    def reset(self, placeholder: str | None = None) -> None:
        self.cancel_pending()
        self.pdf_path = None
        if placeholder is not None:
            self._placeholder.setText(placeholder)
        self.setCurrentWidget(self._placeholder)

    def _on_compiled(self, result: dict) -> None:
        self._busy = False
        self.busy_changed.emit(False)
        self.pdf_path = result["pdf"]
        self.view.show_pdf(result["pdf"])
        self.setCurrentWidget(self.view)
        self.compiled.emit(result)
        self._run_pending()

    def _on_failed(self, log: str) -> None:
        self._busy = False
        self.busy_changed.emit(False)
        self.pdf_path = None
        self._log.setPlainText(log)
        self.setCurrentWidget(self._log)
        self.failed.emit(log)
        self._run_pending()

    def _run_pending(self) -> None:
        if self._pending:
            self._pending = False
            self.compile_now()
