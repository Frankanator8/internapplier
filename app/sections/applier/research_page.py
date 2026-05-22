from __future__ import annotations

from PyQt6.QtCore import Qt, QThread
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QScrollArea,
    QSplitter, QVBoxLayout, QWidget,
)

from ..base import _label, _primary_btn, _secondary_btn, _set_status
from .workers import _ResearchWorker


class ResearchMixin:
    def _build_research_page(self) -> QWidget:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # ── Left: saved companies list ────────────────────────────
        left = QWidget()
        left.setMinimumWidth(160)
        left.setMaximumWidth(240)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 8, 8, 0)
        left_layout.setSpacing(6)

        left_layout.addWidget(_label("Saved Companies"))

        self._company_list = QListWidget()
        self._company_list.setObjectName("company-cache-list")
        self._company_list.itemClicked.connect(self._load_cached_company)
        left_layout.addWidget(self._company_list, 1)

        self._delete_company_btn = _secondary_btn("Delete", 100)
        self._delete_company_btn.clicked.connect(self._delete_cached_company)
        left_layout.addWidget(self._delete_company_btn)

        splitter.addWidget(left)

        # ── Right: research form + results ────────────────────────
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 8, 0, 0)
        right_layout.setSpacing(10)

        form_row = QHBoxLayout()
        form_row.setSpacing(8)

        name_col = QVBoxLayout()
        name_col.setSpacing(4)
        name_col.addWidget(_label("Company Name"))
        self._research_name_input = QLineEdit()
        self._research_name_input.setPlaceholderText("e.g. Anthropic")
        name_col.addWidget(self._research_name_input)
        form_row.addLayout(name_col, 1)

        url_col = QVBoxLayout()
        url_col.setSpacing(4)
        url_col.addWidget(_label("Website URL"))
        self._research_url_input = QLineEdit()
        self._research_url_input.setPlaceholderText("https://www.example.com")
        url_col.addWidget(self._research_url_input)
        form_row.addLayout(url_col, 2)

        right_layout.addLayout(form_row)

        self._research_btn = _primary_btn("🔍  Research Company")
        self._research_btn.clicked.connect(self._research)
        right_layout.addWidget(self._research_btn)

        self._research_status = QLabel("")
        self._research_status.setWordWrap(True)
        self._research_status.setObjectName("status-neutral")
        right_layout.addWidget(self._research_status)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._research_results_content = QWidget()
        self._research_results_content.setStyleSheet("background: transparent;")
        self._research_results_layout = QVBoxLayout(self._research_results_content)
        self._research_results_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._research_results_layout.setSpacing(10)
        self._research_results_layout.setContentsMargins(4, 0, 4, 16)
        scroll.setWidget(self._research_results_content)
        right_layout.addWidget(scroll, 1)

        splitter.addWidget(right)
        splitter.setSizes([200, 600])

        return self._wrap_page("Research Company", splitter)

    def _research(self):
        name = self._research_name_input.text().strip()
        url = self._research_url_input.text().strip()
        if not name or not url:
            self._research_status.setText("Enter both a company name and a website URL.")
            _set_status(self._research_status, "error")
            return

        self._clear_research_results()
        self._research_btn.setEnabled(False)
        self._research_btn.setText("Researching…")
        _set_status(self._research_status, "neutral")
        self._research_status.setText("Starting…")

        worker = _ResearchWorker(name, url)
        thread = QThread(self)
        worker.moveToThread(thread)

        def on_finished(result: dict):
            self._research_btn.setEnabled(True)
            self._research_btn.setText("🔍  Research Company")
            self._research_status.setText("")
            self._research_last_result = result
            self._research_cache[name] = {"url": url, "result": result}
            self._refresh_company_list(select=name)
            self._populate_research_results(result)
            if self._save_fn:
                self._save_fn()
            thread.quit()

        def on_error(msg: str):
            self._research_btn.setEnabled(True)
            self._research_btn.setText("🔍  Research Company")
            _set_status(self._research_status, "error")
            self._research_status.setText(f"Error: {msg}")
            thread.quit()

        def on_research_progress(msg: str):
            _set_status(self._research_status, "neutral")
            self._research_status.setText(msg)

        worker.finished.connect(on_finished)
        worker.error.connect(on_error)
        worker.progress.connect(on_research_progress)
        thread.started.connect(worker.run)
        thread.finished.connect(thread.deleteLater)
        self._threads.append(thread)
        self._workers.append(worker)
        thread.finished.connect(lambda: self._workers.remove(worker) if worker in self._workers else None)
        thread.start()

    def _populate_research_results(self, result: dict):
        self._render_research_block(self._research_results_layout, result)

    def _clear_research_results(self):
        while self._research_results_layout.count():
            item = self._research_results_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
