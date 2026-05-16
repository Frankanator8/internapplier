from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import QObject, QThread, Qt, pyqtSignal
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QLabel, QScrollArea,
    QSizePolicy, QSplitter, QTextEdit, QVBoxLayout, QWidget,
)

from .base import _label, _primary_btn, _secondary_btn


class _TailorWorker(QObject):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, profile: dict, jd: str):
        super().__init__()
        self._profile = profile
        self._jd = jd

    def run(self):
        from app.ai_provider import get_provider
        try:
            result = get_provider().tailor_resume(self._profile, self._jd)
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


class _GenerateResumeWorker(QObject):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, profile: dict, jd: str):
        super().__init__()
        self._profile = profile
        self._jd = jd

    def run(self):
        from app.ai_provider import get_provider
        try:
            tex = get_provider().generate_resume(self._profile, self._jd)
            self.finished.emit(tex)
        except Exception as exc:
            self.error.emit(str(exc))


class ApplierPage(QWidget):
    def __init__(self, get_profile: Callable[[], dict], parent=None):
        super().__init__(parent)
        self._get_profile = get_profile
        self._threads: list[QThread] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 16)
        outer.setSpacing(14)

        outer.addWidget(_label("AI Resume Tailor", "section-title"))

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # ── Left panel ───────────────────────────────────────────
        left = QWidget()
        left.setMinimumWidth(280)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        left_layout.addWidget(_label("Job Description"))

        self._jd_input = QTextEdit()
        self._jd_input.setObjectName("jd-input")
        self._jd_input.setPlaceholderText("Paste the job description here…")
        left_layout.addWidget(self._jd_input, 1)

        self._tailor_btn = _primary_btn("✦  Tailor My Resume")
        self._tailor_btn.clicked.connect(self._tailor)
        left_layout.addWidget(self._tailor_btn)

        self._pdf_btn = _secondary_btn("Generate Resume PDF", 200)
        self._pdf_btn.clicked.connect(self._generate_pdf)
        left_layout.addWidget(self._pdf_btn)

        splitter.addWidget(left)

        # ── Right panel ──────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._results_content = QWidget()
        self._results_content.setStyleSheet("background: transparent;")
        self._results_layout = QVBoxLayout(self._results_content)
        self._results_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._results_layout.setSpacing(10)
        self._results_layout.setContentsMargins(12, 0, 4, 16)
        scroll.setWidget(self._results_content)

        splitter.addWidget(scroll)
        splitter.setSizes([400, 560])

        outer.addWidget(splitter, 1)

    def _tailor(self):
        jd = self._jd_input.toPlainText().strip()
        if not jd:
            return

        profile = self._get_profile()
        self._tailor_btn.setEnabled(False)
        self._tailor_btn.setText("Tailoring…")
        self._clear_results()

        worker = _TailorWorker(profile, jd)
        thread = QThread(self)
        worker.moveToThread(thread)

        def on_finished(items: list):
            self._tailor_btn.setEnabled(True)
            self._tailor_btn.setText("✦  Tailor My Resume")
            self._populate_results(items)
            thread.quit()

        def on_error(msg: str):
            self._tailor_btn.setEnabled(True)
            self._tailor_btn.setText("✦  Tailor My Resume")
            err_label = QLabel(f"Error: {msg}")
            err_label.setWordWrap(True)
            err_label.setStyleSheet("color: #cc3300; font-size: 13px;")
            self._results_layout.addWidget(err_label)
            thread.quit()

        worker.finished.connect(on_finished)
        worker.error.connect(on_error)
        thread.started.connect(worker.run)
        thread.finished.connect(thread.deleteLater)
        self._threads.append(thread)
        thread.start()

    def _populate_results(self, items: list[dict]):
        if not items:
            empty = QLabel("No bullets found in your profile to tailor.")
            empty.setStyleSheet("color: #777; font-size: 13px;")
            self._results_layout.addWidget(empty)
            return

        grouped: dict[str, list[dict]] = {
            "experience": [], "projects": [], "education": []
        }
        for item in items:
            sec = item.get("section", "")
            if sec in grouped:
                grouped[sec].append(item)

        section_names = {
            "experience": "Experience",
            "projects": "Projects",
            "education": "Education",
        }

        for key in ("experience", "projects", "education"):
            section_items = grouped[key]
            if not section_items:
                continue

            header = QLabel(section_names[key].upper())
            header.setObjectName("applier-section-header")
            self._results_layout.addWidget(header)

            for item in section_items:
                row_frame = QFrame()
                row_frame.setObjectName("result-bullet-row")
                row_layout = QVBoxLayout(row_frame)
                row_layout.setContentsMargins(12, 10, 12, 10)
                row_layout.setSpacing(6)

                if item.get("entry"):
                    entry_lbl = QLabel(item["entry"])
                    entry_lbl.setStyleSheet("font-size: 11px; color: #888;")
                    row_layout.addWidget(entry_lbl)

                orig_lbl = QLabel(item.get("original", ""))
                orig_lbl.setWordWrap(True)
                orig_lbl.setStyleSheet("color: #888; font-style: italic; font-size: 12px;")
                row_layout.addWidget(orig_lbl)

                tailored_lbl = QLabel(item.get("tailored", ""))
                tailored_lbl.setWordWrap(True)
                tailored_lbl.setStyleSheet("color: #1d1d1d; font-size: 13px;")
                row_layout.addWidget(tailored_lbl)

                copy_row = QHBoxLayout()
                copy_row.addStretch()
                copy_btn = _secondary_btn("Copy", 70)
                tailored_text = item.get("tailored", "")
                copy_btn.clicked.connect(
                    lambda checked, t=tailored_text: QGuiApplication.clipboard().setText(t)
                )
                copy_row.addWidget(copy_btn)
                row_layout.addLayout(copy_row)

                self._results_layout.addWidget(row_frame)

    def _generate_pdf(self):
        jd = self._jd_input.toPlainText().strip()
        if not jd:
            return

        profile = self._get_profile()
        self._pdf_btn.setEnabled(False)
        self._pdf_btn.setText("Generating…")

        worker = _GenerateResumeWorker(profile, jd)
        thread = QThread(self)
        worker.moveToThread(thread)

        def on_finished(tex: str):
            self._pdf_btn.setEnabled(True)
            self._pdf_btn.setText("Generate Resume PDF")
            thread.quit()
            self._save_pdf(tex)

        def on_error(msg: str):
            self._pdf_btn.setEnabled(True)
            self._pdf_btn.setText("Generate Resume PDF")
            err_label = QLabel(f"Error: {msg}")
            err_label.setWordWrap(True)
            err_label.setStyleSheet("color: #cc3300; font-size: 13px;")
            self._results_layout.addWidget(err_label)
            thread.quit()

        worker.finished.connect(on_finished)
        worker.error.connect(on_error)
        thread.started.connect(worker.run)
        thread.finished.connect(thread.deleteLater)
        self._threads.append(thread)
        thread.start()

    def _save_pdf(self, tex: str):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Resume PDF", "resume.pdf", "PDF Files (*.pdf)"
        )
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"

        from app.pdf_export import compile_latex_to_pdf
        try:
            compile_latex_to_pdf(tex, path)
        except Exception as exc:
            err_label = QLabel(f"PDF error: {exc}")
            err_label.setWordWrap(True)
            err_label.setStyleSheet("color: #cc3300; font-size: 13px;")
            self._results_layout.addWidget(err_label)
            return

        ok_label = QLabel(f"Resume saved to {path}")
        ok_label.setWordWrap(True)
        ok_label.setStyleSheet("color: #1d7a3a; font-size: 13px;")
        self._results_layout.addWidget(ok_label)

    def _clear_results(self):
        while self._results_layout.count():
            item = self._results_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
