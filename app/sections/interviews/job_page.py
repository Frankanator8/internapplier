from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import (
    QHBoxLayout, QListWidget, QListWidgetItem, QSplitter, QVBoxLayout, QWidget,
)

from ..base import _label
from .questions_page import InterviewQuestionsPage


class JobInterviewPage(QWidget):
    """Per-job interview prep: Template + jobs sidebar, shared card editor."""

    def __init__(
        self,
        get_profile: Callable[[], dict],
        get_applications: Callable[[], list[dict]],
        get_research_cache: Callable[[], dict],
        set_application_interviews: Callable[[int, list[dict]], None],
        parent=None,
    ):
        super().__init__(parent)
        self._get_profile = get_profile
        self._get_applications = get_applications
        self._get_research_cache = get_research_cache
        self._set_application_interviews = set_application_interviews

        self._template: list[dict] = []
        self._current_kind: str = "template"   # "template" or "job"
        self._current_job_index: int | None = None
        self._suppress_selection = False

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        outer.addWidget(splitter, 1)

        left = QWidget()
        left.setMinimumWidth(180)
        left.setMaximumWidth(280)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(16, 16, 8, 0)
        left_layout.setSpacing(6)
        left_layout.addWidget(_label("Templates & Jobs"))

        self._sidebar = QListWidget()
        self._sidebar.setObjectName("company-cache-list")
        left_layout.addWidget(self._sidebar, 1)
        splitter.addWidget(left)

        self._editor = InterviewQuestionsPage(
            get_profile=get_profile,
            get_job_context=self._current_job_context,
        )
        splitter.addWidget(self._editor)
        splitter.setSizes([220, 700])

        self._sidebar.currentRowChanged.connect(self._on_row_changed)

    # ── public API ────────────────────────────────────────────────
    def load_template(self, value: list[dict] | None):
        self._template = list(value or [])
        # Initial display: rebuild sidebar and show Template at row 0.
        self._rebuild_sidebar(initial=True)

    def get_template_data(self) -> list[dict]:
        # Make sure any in-flight edits to Template are flushed first.
        self.commit_current()
        return list(self._template)

    def commit_current(self) -> None:
        """Flush the editor's current contents back to its source."""
        data = self._editor.get_data()
        if self._current_kind == "template":
            self._template = data
        elif self._current_kind == "job" and self._current_job_index is not None:
            self._set_application_interviews(self._current_job_index, data)

    def showEvent(self, event):  # noqa: N802 (Qt API)
        super().showEvent(event)
        # Applications may have changed elsewhere; refresh the sidebar.
        self._rebuild_sidebar(initial=False)

    # ── internals ─────────────────────────────────────────────────
    def _current_job_context(self) -> dict | None:
        if self._current_kind != "job" or self._current_job_index is None:
            return None
        apps = self._get_applications()
        if not (0 <= self._current_job_index < len(apps)):
            return None
        entry = apps[self._current_job_index]
        from ..applier import _research_from_cache
        research = _research_from_cache(self._get_research_cache() or {}, entry.get("company", ""))
        return {
            "company_name": entry.get("company") or None,
            "company_research": research,
            "job_description": entry.get("description") or None,
        }

    def _rebuild_sidebar(self, initial: bool) -> None:
        # Remember selection (kind + job index) so we restore it after rebuild.
        prev_kind = self._current_kind
        prev_index = self._current_job_index

        self._suppress_selection = True
        try:
            self._sidebar.clear()

            # Row 0: Template (always present).
            tmpl_item = QListWidgetItem("📌  Template")
            tmpl_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            self._sidebar.addItem(tmpl_item)

            apps = self._get_applications()
            if apps:
                # Row 1: visual divider (non-selectable, non-interactive).
                divider = QListWidgetItem("")
                divider.setFlags(Qt.ItemFlag.NoItemFlags)
                divider.setSizeHint(QSize(0, 8))
                self._sidebar.addItem(divider)

                for entry in apps:
                    company = (entry.get("company") or "").strip()
                    role = (entry.get("role") or "").strip()
                    if company and role:
                        label = f"{company} — {role}"
                    elif company or role:
                        label = company or role
                    else:
                        label = "(untitled job)"
                    item = QListWidgetItem(label)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                    self._sidebar.addItem(item)

            # Restore selection.
            target_row = 0
            if not initial and prev_kind == "job" and prev_index is not None and prev_index < len(apps):
                target_row = 2 + prev_index  # 0 = template, 1 = divider
            self._sidebar.setCurrentRow(target_row)
        finally:
            self._suppress_selection = False

        # Manually trigger a load for the current row, since signals were suppressed.
        self._load_for_row(self._sidebar.currentRow())

    def _on_row_changed(self, row: int) -> None:
        if self._suppress_selection or row < 0:
            return
        # Skip divider — bump to next selectable.
        item = self._sidebar.item(row)
        if item is not None and not (item.flags() & Qt.ItemFlag.ItemIsSelectable):
            self._sidebar.setCurrentRow(row + 1 if row + 1 < self._sidebar.count() else 0)
            return
        # Commit edits on the page we are leaving before swapping content.
        self.commit_current()
        self._load_for_row(row)

    def _load_for_row(self, row: int) -> None:
        if row <= 0:
            self._current_kind = "template"
            self._current_job_index = None
            self._editor.load(self._template)
            return
        # Row 1 is the divider, rows 2..N are jobs (when divider present).
        job_index = row - 2 if self._sidebar.count() > 1 else None
        apps = self._get_applications()
        if job_index is None or not (0 <= job_index < len(apps)):
            self._current_kind = "template"
            self._current_job_index = None
            self._editor.load(self._template)
            return
        self._current_kind = "job"
        self._current_job_index = job_index
        existing = apps[job_index].get("interview_questions") or []
        self._editor.load(existing if existing else list(self._template))
