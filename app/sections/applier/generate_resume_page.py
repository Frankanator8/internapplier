from __future__ import annotations

import logging

from PyQt6.QtCore import Qt, QThread, QUrl
from PyQt6.QtGui import QDesktopServices, QFont, QGuiApplication, QTextCursor
from PyQt6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
    QScrollArea, QSizePolicy, QSplitter, QTextEdit, QVBoxLayout, QWidget,
)

from api import data_store

from ..base import _label, _primary_btn, _secondary_btn, _set_status
from .workers import _GenerateResumeWorker

logger = logging.getLogger(__name__)


class GenerateResumeMixin:
    def _build_generate_resume_page(self) -> QWidget:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # ── Left: inputs ─────────────────────────────────────────
        left = QWidget()
        left.setMinimumWidth(320)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 8, 0, 0)
        left_layout.setSpacing(10)

        left_layout.addWidget(_label("Fill from Application"))
        self._gen_app_picker = QComboBox()
        self._gen_app_picker.currentIndexChanged.connect(self._on_fill_from_application)
        left_layout.addWidget(self._gen_app_picker)
        self._refresh_app_picker()

        form_row = QHBoxLayout()
        form_row.setSpacing(8)

        name_col = QVBoxLayout()
        name_col.setSpacing(4)
        name_col.addWidget(_label("Company Name *"))
        self._gen_name_input = QLineEdit()
        self._gen_name_input.setPlaceholderText("e.g. Anthropic")
        name_col.addWidget(self._gen_name_input)
        form_row.addLayout(name_col, 1)

        url_col = QVBoxLayout()
        url_col.setSpacing(4)
        url_col.addWidget(_label("Website (optional)"))
        self._gen_url_input = QLineEdit()
        self._gen_url_input.setPlaceholderText("https://www.example.com")
        url_col.addWidget(self._gen_url_input)
        form_row.addLayout(url_col, 2)

        left_layout.addLayout(form_row)

        left_layout.addWidget(_label("Job Description"))
        self._gen_jd_input = QTextEdit()
        self._gen_jd_input.setPlaceholderText("Paste the job description here…")
        left_layout.addWidget(self._gen_jd_input, 1)

        self._gen_btn = _primary_btn("📄  Generate Resume")
        self._gen_btn.clicked.connect(self._generate_resume)
        left_layout.addWidget(self._gen_btn)

        self._gen_status = QLabel("")
        self._gen_status.setWordWrap(True)
        self._gen_status.setObjectName("status-neutral")
        left_layout.addWidget(self._gen_status)

        splitter.addWidget(left)

        # ── Right: live stream view + results ────────────────────
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self._gen_stream_view = QPlainTextEdit()
        self._gen_stream_view.setReadOnly(True)
        self._gen_stream_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        mono = QFont("Menlo")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        mono.setPointSize(11)
        self._gen_stream_view.setFont(mono)
        self._gen_stream_view.setStyleSheet(
            "QPlainTextEdit { background: #1d1d1d; color: #e6e6e6;"
            " border: 1px solid #333; padding: 8px; }"
        )
        self._gen_stream_view.setVisible(False)
        self._gen_stream_last_stage: str | None = None
        right_layout.addWidget(self._gen_stream_view, 1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._gen_results_content = QWidget()
        self._gen_results_content.setStyleSheet("background: transparent;")
        self._gen_results_layout = QVBoxLayout(self._gen_results_content)
        self._gen_results_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._gen_results_layout.setSpacing(10)
        self._gen_results_layout.setContentsMargins(12, 0, 4, 16)
        scroll.setWidget(self._gen_results_content)
        self._gen_results_scroll = scroll
        right_layout.addWidget(scroll, 1)

        splitter.addWidget(right)
        splitter.setSizes([400, 560])

        return self._wrap_page("Generate Resume", splitter)

    def _on_gen_stream(self, stage: str, chunk: str) -> None:
        if stage != self._gen_stream_last_stage:
            if self._gen_stream_last_stage is not None:
                sep = f"\n\n\n══════ {stage} ══════\n\n"
            else:
                sep = f"══════ {stage} ══════\n\n"
            self._gen_stream_view.moveCursor(QTextCursor.MoveOperation.End)
            self._gen_stream_view.insertPlainText(sep)
            self._gen_stream_last_stage = stage
        self._gen_stream_view.moveCursor(QTextCursor.MoveOperation.End)
        self._gen_stream_view.insertPlainText(chunk)
        sb = self._gen_stream_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _generate_resume(self):
        jd = self._gen_jd_input.toPlainText().strip()
        if not jd:
            _set_status(self._gen_status, "error")
            self._gen_status.setText("Paste a job description first.")
            return

        name = self._gen_name_input.text().strip()
        url = self._gen_url_input.text().strip()
        profile = self._get_profile()

        self._clear_generate_results()
        self._gen_stream_view.clear()
        self._gen_stream_last_stage = None
        self._gen_stream_view.setVisible(True)
        self._gen_results_scroll.setVisible(False)
        self._gen_btn.setEnabled(False)
        self._gen_btn.setText("Generating…")
        _set_status(self._gen_status, "neutral")
        self._gen_status.setText("Starting…")

        worker = _GenerateResumeWorker(profile, jd, name, url, self._research_cache)
        thread = QThread(self)
        worker.moveToThread(thread)

        def on_finished(payload: dict):
            self._gen_btn.setEnabled(True)
            self._gen_btn.setText("📄  Generate Resume")
            self._gen_status.setText("")
            self._gen_stream_view.setVisible(False)
            self._gen_results_scroll.setVisible(True)
            self._populate_generate_results(payload)
            if payload.get("new_research") and name:
                self._research_cache[name] = {"url": url, "result": payload["research"]}
                self._refresh_company_list()
                if self._save_fn:
                    self._save_fn()
            self._refresh_library()
            thread.quit()

        def on_error(msg: str):
            self._gen_btn.setEnabled(True)
            self._gen_btn.setText("📄  Generate Resume")
            _set_status(self._gen_status, "error")
            self._gen_status.setText(f"Error: {msg}")
            thread.quit()

        def on_progress(msg: str):
            _set_status(self._gen_status, "neutral")
            self._gen_status.setText(msg)

        worker.finished.connect(on_finished)
        worker.error.connect(on_error)
        worker.progress.connect(on_progress)
        worker.stream.connect(self._on_gen_stream)
        thread.started.connect(worker.run)
        thread.finished.connect(thread.deleteLater)
        self._threads.append(thread)
        self._workers.append(worker)
        thread.finished.connect(lambda: self._workers.remove(worker) if worker in self._workers else None)
        thread.start()

    def _populate_generate_results(self, payload: dict):
        layout = self._gen_results_layout

        research = payload.get("research") or {}
        layout.addWidget(self._research_section_header("COMPANY RESEARCH"))
        self._render_research_block(layout, research)

        fill = payload.get("fill")
        grade = payload.get("grade") or {}
        latex = payload.get("latex") or ""
        pdf = payload.get("pdf") or ""
        if latex or fill is not None or grade or pdf:
            layout.addWidget(self._research_section_header("GENERATED RESUME"))
            if fill is None:
                layout.addWidget(self._research_text_row("Pages: (failed to compile)"))
            else:
                layout.addWidget(self._research_text_row(f"Pages: {fill:.2f}"))
            if grade:
                layout.addWidget(self._research_text_row(f"Grade: {grade.get('score', 0):.2f}/10"))
                fb = grade.get("feedback") or ""
                if fb:
                    layout.addWidget(self._research_text_row("Feedback: " + fb))
                drops = grade.get("drops") or []
                if drops:
                    layout.addWidget(self._research_text_row(
                        "Dropped for page-fit: " + "; ".join(drops)
                    ))

            btn_row_frame = QFrame()
            btn_row = QHBoxLayout(btn_row_frame)
            btn_row.setContentsMargins(0, 4, 0, 0)
            btn_row.setSpacing(8)
            if pdf:
                open_btn = _primary_btn("Open PDF")
                open_btn.clicked.connect(
                    lambda checked, p=pdf: QDesktopServices.openUrl(QUrl.fromLocalFile(p))
                )
                btn_row.addWidget(open_btn)
            if latex:
                copy_btn = _secondary_btn("Copy LaTeX", 120)
                copy_btn.clicked.connect(
                    lambda checked, t=latex: QGuiApplication.clipboard().setText(t)
                )
                btn_row.addWidget(copy_btn)
            btn_row.addStretch()
            layout.addWidget(btn_row_frame)

            attempts = payload.get("attempts") or []
            chosen = payload.get("chosen_attempt")
            if len(attempts) > 1:
                layout.addWidget(self._research_section_header("ALL ATTEMPTS"))
                for a in attempts:
                    n = a.get("attempt")
                    a_pdf = a.get("pdf") or ""
                    a_grade = a.get("grade") or {}
                    a_fill = a.get("fill")
                    a_compile_error = a.get("compile_error") or ""
                    score_part = (
                        f"{a_grade.get('score', 0):.2f}/10"
                        if a_grade else "ungraded"
                    )
                    pages_part = (
                        f"{a_fill:.2f}pg" if a_fill is not None else "compile✗"
                    )
                    mark = " ★" if n == chosen else ""
                    label = f"Attempt {n} ({score_part}, {pages_part}){mark}"

                    btn_frame = QFrame()
                    btn_layout = QHBoxLayout(btn_frame)
                    btn_layout.setContentsMargins(0, 0, 0, 0)
                    btn_layout.setSpacing(8)
                    btn = _secondary_btn(label, 0)
                    btn.setEnabled(bool(a_pdf))
                    if a_pdf:
                        btn.clicked.connect(
                            lambda checked, p=a_pdf:
                            QDesktopServices.openUrl(QUrl.fromLocalFile(p))
                        )
                    btn_layout.addWidget(btn)
                    btn_layout.addStretch()
                    layout.addWidget(btn_frame)

                    a_feedback = a_grade.get("feedback") or ""
                    if a_compile_error:
                        layout.addWidget(self._research_text_row(
                            "Compile error: " + a_compile_error
                        ))
                    elif a_feedback:
                        layout.addWidget(self._research_text_row(
                            "Feedback: " + a_feedback
                        ))

    def _clear_generate_results(self):
        while self._gen_results_layout.count():
            item = self._gen_results_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _refresh_app_picker(self):
        if not hasattr(self, "_gen_app_picker"):
            return
        picker = self._gen_app_picker
        picker.blockSignals(True)
        picker.clear()
        picker.addItem("— Select an application —", None)
        try:
            entries = data_store.load().get("applications") or []
        except Exception:
            logger.exception("_refresh_app_picker — failed to load applications")
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

    def _on_fill_from_application(self, idx: int):
        if idx <= 0:
            return
        entry = self._gen_app_picker.itemData(idx)
        if not isinstance(entry, dict):
            return
        self._gen_name_input.setText(entry.get("company", "") or "")
        self._gen_jd_input.setPlainText(entry.get("description", "") or "")
        self._gen_app_picker.blockSignals(True)
        self._gen_app_picker.setCurrentIndex(0)
        self._gen_app_picker.blockSignals(False)
