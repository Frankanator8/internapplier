from __future__ import annotations

import logging

from PyQt6.QtCore import Qt, QThread
from PyQt6.QtGui import QGuiApplication, QTextCursor
from PyQt6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QLineEdit, QSplitter, QTextEdit, QVBoxLayout, QWidget,
)

from api import data_store
from api.research_cache import lookup as _research_from_cache

from ..base import _label, _primary_btn, _secondary_btn, _set_status
from .workers import _QuestionWorker

logger = logging.getLogger(__name__)


class AnswerQuestionMixin:
    def _build_answer_question_page(self) -> QWidget:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        left = QWidget()
        left.setMinimumWidth(320)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 8, 0, 0)
        left_layout.setSpacing(10)

        left_layout.addWidget(_label("Fill from Application"))
        self._answer_app_picker = QComboBox()
        self._answer_app_picker.currentIndexChanged.connect(self._on_fill_answer_from_application)
        left_layout.addWidget(self._answer_app_picker)
        self._refresh_answer_app_picker()

        left_layout.addWidget(_label("Company (optional)"))
        self._answer_company_input = QLineEdit()
        self._answer_company_input.setPlaceholderText(
            "Match a researched company to tailor the answer"
        )
        left_layout.addWidget(self._answer_company_input)

        left_layout.addWidget(_label("Question"))
        self._answer_question_input = QTextEdit()
        self._answer_question_input.setPlaceholderText(
            "e.g. Why are you interested in this role?"
        )
        left_layout.addWidget(self._answer_question_input, 1)

        left_layout.addWidget(_label("Job Description (optional)"))
        self._answer_jd_input = QTextEdit()
        self._answer_jd_input.setPlaceholderText(
            "Paste the job description to tailor the answer to the role…"
        )
        left_layout.addWidget(self._answer_jd_input, 2)

        self._answer_btn = _primary_btn("❓  Answer Question")
        self._answer_btn.clicked.connect(self._answer_question)
        left_layout.addWidget(self._answer_btn)

        self._answer_status = QLabel("")
        self._answer_status.setWordWrap(True)
        self._answer_status.setObjectName("status-neutral")
        left_layout.addWidget(self._answer_status)

        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 8, 0, 0)
        right_layout.setSpacing(8)

        self._answer_output = QTextEdit()
        self._answer_output.setReadOnly(True)
        self._answer_output.setPlaceholderText(
            "The generated answer will stream here."
        )
        right_layout.addWidget(self._answer_output, 1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self._answer_copy_btn = _secondary_btn("Copy Answer", 120)
        self._answer_copy_btn.clicked.connect(
            lambda: QGuiApplication.clipboard().setText(
                self._answer_output.toPlainText()
            )
        )
        btn_row.addWidget(self._answer_copy_btn)
        btn_row.addStretch()
        right_layout.addLayout(btn_row)

        splitter.addWidget(right)
        splitter.setSizes([360, 600])

        return self._wrap_page("Answer Question", splitter)

    def _answer_question(self):
        question = self._answer_question_input.toPlainText().strip()
        if not question:
            _set_status(self._answer_status, "error")
            self._answer_status.setText("Type a question first.")
            return

        company = self._answer_company_input.text().strip()
        jd = self._answer_jd_input.toPlainText().strip()
        profile = self._get_profile()

        self._answer_output.clear()
        self._answer_btn.setEnabled(False)
        self._answer_btn.setText("Answering…")
        _set_status(self._answer_status, "neutral")
        if company and _research_from_cache(self._research_cache, company):
            self._answer_status.setText(f"Using cached research for {company!r}…")
        elif company:
            self._answer_status.setText(
                f"No cached research for {company!r} — answering from profile only."
            )
        else:
            self._answer_status.setText("Answering from profile…")

        worker = _QuestionWorker(question, profile, company, jd, self._research_cache)
        thread = QThread(self)
        worker.moveToThread(thread)

        def on_finished():
            self._answer_btn.setEnabled(True)
            self._answer_btn.setText("❓  Answer Question")
            self._answer_status.setText("")
            thread.quit()

        def on_error(msg: str):
            self._answer_btn.setEnabled(True)
            self._answer_btn.setText("❓  Answer Question")
            _set_status(self._answer_status, "error")
            self._answer_status.setText(f"Error: {msg}")
            thread.quit()

        worker.finished.connect(on_finished)
        worker.error.connect(on_error)
        worker.stream.connect(self._on_answer_chunk)
        thread.started.connect(worker.run)
        thread.finished.connect(thread.deleteLater)
        self._threads.append(thread)
        self._workers.append(worker)
        thread.finished.connect(lambda: self._workers.remove(worker) if worker in self._workers else None)
        thread.start()

    def _on_answer_chunk(self, chunk: str):
        self._answer_output.moveCursor(QTextCursor.MoveOperation.End)
        self._answer_output.insertPlainText(chunk)
        sb = self._answer_output.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _refresh_answer_app_picker(self):
        if not hasattr(self, "_answer_app_picker"):
            return
        picker = self._answer_app_picker
        picker.blockSignals(True)
        picker.clear()
        picker.addItem("— Select an application —", None)
        try:
            entries = data_store.load().get("applications") or []
        except Exception:
            logger.exception("_refresh_answer_app_picker — failed to load applications")
            entries = []
        for entry in entries:
            company = (entry.get("company") or "").strip()
            role = (entry.get("role") or "").strip()
            if company and role:
                label = f"{company} — {role}"
            else:
                label = company or role or "(untitled)"
            picker.addItem(label, entry)
        picker.setCurrentIndex(0)
        picker.blockSignals(False)

    def _on_fill_answer_from_application(self, idx: int):
        if idx <= 0:
            return
        entry = self._answer_app_picker.itemData(idx)
        if not isinstance(entry, dict):
            return
        self._answer_company_input.setText(entry.get("company", "") or "")
        self._answer_jd_input.setPlainText(entry.get("description", "") or "")
        self._answer_app_picker.blockSignals(True)
        self._answer_app_picker.setCurrentIndex(0)
        self._answer_app_picker.blockSignals(False)
