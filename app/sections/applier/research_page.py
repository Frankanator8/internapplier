from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLayout, QVBoxLayout, QWidget

from app.context import AppContext
from app.ui.widgets import (
    BusyButton, button, clear_layout, field, hsplitter, label, line_edit,
    list_pane, scroll_area, set_status, set_titled_content, status_label, vbox_widget,
)
from app.ui.workers import WorkerPool

from .workers import ResearchWorker


def result_row(text: str) -> QFrame:
    frame = QFrame()
    frame.setObjectName("result-bullet-row")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(12, 10, 12, 10)
    layout.addWidget(label(text, "", wrap=True))
    return frame


def render_research(layout: QLayout, result: dict) -> None:
    """Append a company research result (summary, values, news) to ``layout``."""
    summary = (result.get("summary") or "").strip()
    sections = [
        ("CORE VALUES", result.get("core_values") or []),
        ("RECENT PROJECTS / NEWS", result.get("recent_projects") or []),
    ]
    if not summary and not any(items for _, items in sections):
        layout.addWidget(label("No information could be extracted from the site.", "muted"))
        return
    if summary:
        layout.addWidget(label("SUMMARY", "applier-section-header"))
        layout.addWidget(result_row(summary))
    for header, items in sections:
        if items:
            layout.addWidget(label(header, "applier-section-header"))
            for item in items:
                layout.addWidget(result_row(f"• {item}"))


class ResearchPage(QWidget):
    """Scrape and summarize a company site; browse and prune the saved results."""

    def __init__(self, ctx: AppContext, parent=None):
        super().__init__(parent)
        self._ctx = ctx
        self._pool = WorkerPool(self)

        left, left_layout, self._company_list = list_pane(
            "Saved Companies", margins=(0, 8, 8, 0), width=(160, 240),
        )
        self._company_list.itemClicked.connect(lambda item: self._show_cached(item.text()))
        delete_btn = button("Delete", "secondary", 100)
        delete_btn.clicked.connect(self._delete_selected)
        left_layout.addWidget(delete_btn)

        right, right_layout = vbox_widget((0, 8, 0, 0), spacing=10)
        form_row = QHBoxLayout()
        form_row.setSpacing(8)
        self._name_input = line_edit("e.g. Anthropic")
        self._url_input = line_edit("https://www.example.com")
        for caption, edit, stretch in (("Company Name", self._name_input, 1), ("Website URL", self._url_input, 2)):
            col = field(caption, edit)
            col.setSpacing(4)
            form_row.addLayout(col, stretch)
        right_layout.addLayout(form_row)

        self._research_btn = BusyButton("🔍  Research Company", "Researching…")
        self._research_btn.clicked.connect(self._research)
        right_layout.addWidget(self._research_btn)
        self._status = status_label()
        right_layout.addWidget(self._status)

        scroll, self._results = scroll_area(margins=(4, 0, 4, 16), spacing=10)
        right_layout.addWidget(scroll, 1)

        set_titled_content(self, "Research Company", hsplitter(left, right, sizes=[200, 600]))

        ctx.research.changed.connect(self._refresh_company_list)
        self._refresh_company_list()

    def _refresh_company_list(self) -> None:
        selected = self._company_list.currentItem()
        selected_name = selected.text() if selected else None
        self._company_list.clear()
        self._company_list.addItems(self._ctx.research.companies())
        if selected_name:
            self._select(selected_name)

    def _select(self, name: str) -> None:
        items = self._company_list.findItems(name, Qt.MatchFlag.MatchExactly)
        if items:
            self._company_list.setCurrentItem(items[0])

    def _show_cached(self, name: str) -> None:
        entry = self._ctx.research.entry(name)
        if not entry:
            return
        self._name_input.setText(name)
        self._url_input.setText(entry.get("url", ""))
        clear_layout(self._results)
        if entry.get("result"):
            render_research(self._results, entry["result"])

    def _delete_selected(self) -> None:
        item = self._company_list.currentItem()
        if not item:
            return
        self._ctx.research.remove(item.text())
        clear_layout(self._results)
        self._name_input.clear()
        self._url_input.clear()
        self._ctx.save()

    def _research(self) -> None:
        name = self._name_input.text().strip()
        url = self._url_input.text().strip()
        if not name or not url:
            set_status(self._status, "error", "Enter both a company name and a website URL.")
            return

        clear_layout(self._results)
        self._research_btn.set_busy(True)
        set_status(self._status, "neutral", "Starting…")

        def on_finished(result: dict):
            self._research_btn.set_busy(False)
            self._status.setText("")
            self._ctx.research.put(name, url, result)
            self._select(name)
            render_research(self._results, result)
            self._ctx.save()

        def on_error(msg: str):
            self._research_btn.set_busy(False)
            set_status(self._status, "error", f"Error: {msg}")

        self._pool.start(
            ResearchWorker(name, url),
            progress=lambda msg: set_status(self._status, "neutral", msg),
            finished=on_finished,
            error=on_error,
        )
