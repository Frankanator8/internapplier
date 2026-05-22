from __future__ import annotations

import logging
from typing import Callable

from PyQt6.QtCore import QObject, QThread, Qt
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QStackedWidget, QVBoxLayout, QWidget,
)

from ..base import _label
from .answer_question_page import AnswerQuestionMixin
from .generate_resume_page import GenerateResumeMixin
from .library_page import LibraryMixin
from .research_page import ResearchMixin

logger = logging.getLogger(__name__)


class ApplierPage(
    GenerateResumeMixin,
    ResearchMixin,
    LibraryMixin,
    AnswerQuestionMixin,
    QWidget,
):
    def __init__(
        self,
        get_profile: Callable[[], dict],
        save_fn: Callable[[], None] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._get_profile = get_profile
        self._save_fn = save_fn
        self._threads: list[QThread] = []
        self._workers: list[QObject] = []
        self._research_last_result: dict = {}
        self._research_cache: dict[str, dict] = {}

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._applier_sidebar = QListWidget()
        self._applier_sidebar.setObjectName("sidebar")
        self._applier_sidebar.setFixedWidth(200)

        for label in ("📄  Generate Resume", "🔍  Research Company", "📚  Library", "❓  Answer Question"):
            item = QListWidgetItem(label)
            item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            self._applier_sidebar.addItem(item)

        self._applier_stack = QStackedWidget()
        self._applier_stack.addWidget(self._build_generate_resume_page())
        self._applier_stack.addWidget(self._build_research_page())
        self._applier_stack.addWidget(self._build_library_page())
        self._applier_stack.addWidget(self._build_answer_question_page())

        self._applier_sidebar.currentRowChanged.connect(self._applier_stack.setCurrentIndex)
        self._applier_sidebar.currentRowChanged.connect(self._on_applier_section_changed)
        self._applier_sidebar.setCurrentRow(0)

        outer.addWidget(self._applier_sidebar)
        outer.addWidget(self._applier_stack, 1)

    def _wrap_page(self, title: str, content: QWidget) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 16)
        layout.setSpacing(14)
        layout.addWidget(_label(title, "section-title"))
        layout.addWidget(content, 1)
        return page

    # ── Shared research rendering ───────────────────────────────
    def _render_research_block(self, layout: QVBoxLayout, result: dict):
        summary = (result.get("summary") or "").strip()
        values = result.get("core_values") or []
        projects = result.get("recent_projects") or []

        if not summary and not values and not projects:
            empty = QLabel("No information could be extracted from the site.")
            empty.setStyleSheet("color: #777; font-size: 13px;")
            layout.addWidget(empty)
            return

        if summary:
            layout.addWidget(self._research_section_header("SUMMARY"))
            layout.addWidget(self._research_text_row(summary))

        if values:
            layout.addWidget(self._research_section_header("CORE VALUES"))
            for v in values:
                layout.addWidget(self._research_text_row(f"• {v}"))

        if projects:
            layout.addWidget(self._research_section_header("RECENT PROJECTS / NEWS"))
            for p in projects:
                layout.addWidget(self._research_text_row(f"• {p}"))

    def _research_section_header(self, text: str) -> QLabel:
        header = QLabel(text)
        header.setObjectName("applier-section-header")
        return header

    def _research_text_row(self, text: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("result-bullet-row")
        row_layout = QVBoxLayout(frame)
        row_layout.setContentsMargins(12, 10, 12, 10)
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("font-size: 13px;")
        row_layout.addWidget(lbl)
        return frame

    # ── Research cache management ───────────────────────────────
    def get_research_data(self) -> dict:
        """Return the full cache dict: {company_name: {url, result}}."""
        return self._research_cache

    def load_research_data(self, cache: dict):
        """Load a full cache dict and populate the company list."""
        if not cache:
            return
        self._research_cache = cache
        self._refresh_company_list()

    def _refresh_company_list(self, select: str | None = None):
        self._company_list.clear()
        for name in sorted(self._research_cache.keys(), key=str.lower):
            self._company_list.addItem(name)
        if select:
            items = self._company_list.findItems(select, Qt.MatchFlag.MatchExactly)
            if items:
                self._company_list.setCurrentItem(items[0])

    def _load_cached_company(self, item: QListWidgetItem):
        name = item.text()
        entry = self._research_cache.get(name)
        if not entry:
            return
        self._research_name_input.setText(name)
        self._research_url_input.setText(entry.get("url", ""))
        result = entry.get("result") or {}
        self._research_last_result = result
        self._clear_research_results()
        if result:
            self._populate_research_results(result)

    def _delete_cached_company(self):
        item = self._company_list.currentItem()
        if not item:
            return
        name = item.text()
        self._research_cache.pop(name, None)
        self._refresh_company_list()
        self._clear_research_results()
        self._research_name_input.clear()
        self._research_url_input.clear()
        self._research_last_result = {}
        if self._save_fn:
            self._save_fn()

    def cleanup_threads(self) -> None:
        from .._thread_cleanup import shutdown_threads
        shutdown_threads(self._threads)
        self._workers.clear()

    def _on_applier_section_changed(self, idx: int):
        if idx == 0:
            self._refresh_app_picker()
        if idx == 2:
            self._refresh_library()
