from __future__ import annotations

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import QHBoxLayout, QListWidgetItem, QWidget

from api.applications import app_label, job_context
from app.context import AppContext
from app.ui.widgets import hsplitter, list_pane

from .questions_page import InterviewQuestionsPage

_FIRST_JOB_ROW = 2  # row 0 = Template, row 1 = divider


class JobInterviewPage(QWidget):
    """Per-job interview prep: a Template plus one question set per application.

    A job without its own questions starts from a copy of the template. The
    shared editor's contents are committed back whenever the selection moves.
    """

    def __init__(self, ctx: AppContext, parent=None):
        super().__init__(parent)
        self._ctx = ctx
        self._template: list[dict] = []
        self._job_index: int | None = None  # None → the Template is selected
        self._suppress_selection = False

        left, _layout, self._sidebar = list_pane("Templates & Jobs", width=(180, 280))
        self._editor = InterviewQuestionsPage(ctx.get_profile, get_job_context=self._current_job_context)
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(hsplitter(left, self._editor, sizes=[220, 700]), 1)
        self._sidebar.currentRowChanged.connect(self._on_row_changed)

    # ── Public API ──────────────────────────────────────────────
    def load_template(self, value: list[dict] | None) -> None:
        self._template = list(value or [])
        self._job_index = None
        self._rebuild_sidebar()

    def get_template_data(self) -> list[dict]:
        self.commit_current()
        return list(self._template)

    def commit_current(self) -> None:
        """Flush the editor's contents back to the template or the selected job."""
        data = self._editor.get_data()
        if self._job_index is None:
            self._template = data
        else:
            self._ctx.set_application_interviews(self._job_index, data)

    def hideEvent(self, event):  # noqa: N802 (Qt API)
        # Commit while the job index still points at the right application —
        # rows may be added or deleted elsewhere before we're shown again.
        self.commit_current()
        super().hideEvent(event)

    def showEvent(self, event):  # noqa: N802 (Qt API)
        super().showEvent(event)
        # Applications may have changed elsewhere; refresh the sidebar.
        self._rebuild_sidebar()

    # ── Internals ───────────────────────────────────────────────
    def _current_job_context(self) -> dict | None:
        apps = self._ctx.get_applications()
        if self._job_index is None or not (0 <= self._job_index < len(apps)):
            return None
        entry = apps[self._job_index]
        return job_context(entry, self._ctx.research.lookup(entry.get("company", "")))

    def _add_row(self, text: str) -> QListWidgetItem:
        item = QListWidgetItem(text)
        item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._sidebar.addItem(item)
        return item

    def _rebuild_sidebar(self) -> None:
        apps = self._ctx.get_applications()
        self._suppress_selection = True
        try:
            self._sidebar.clear()
            self._add_row("📌  Template")
            if apps:
                divider = self._add_row("")
                divider.setFlags(Qt.ItemFlag.NoItemFlags)
                divider.setSizeHint(QSize(0, 8))
                for entry in apps:
                    self._add_row(app_label(entry, "(untitled job)"))
            keep_job = self._job_index is not None and self._job_index < len(apps)
            self._sidebar.setCurrentRow(_FIRST_JOB_ROW + self._job_index if keep_job else 0)
        finally:
            self._suppress_selection = False
        # Signals were suppressed, so load the selected row by hand.
        self._load_row(self._sidebar.currentRow())

    def _on_row_changed(self, row: int) -> None:
        if self._suppress_selection or row < 0:
            return
        item = self._sidebar.item(row)
        if item is not None and not (item.flags() & Qt.ItemFlag.ItemIsSelectable):
            # The divider: skip to the next selectable row.
            self._sidebar.setCurrentRow(row + 1 if row + 1 < self._sidebar.count() else 0)
            return
        self.commit_current()
        self._load_row(row)

    def _load_row(self, row: int) -> None:
        apps = self._ctx.get_applications()
        job_index = row - _FIRST_JOB_ROW
        if row < _FIRST_JOB_ROW or job_index >= len(apps):
            self._job_index = None
            self._editor.load(self._template)
            return
        self._job_index = job_index
        existing = apps[job_index].get("interview_questions") or []
        self._editor.load(existing or list(self._template))
