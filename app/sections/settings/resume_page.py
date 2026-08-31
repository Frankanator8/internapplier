from __future__ import annotations

import logging

from PyQt6.QtCore import QObject, Qt, QThread, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QFont
from PyQt6.QtWebEngineCore import QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QDoubleSpinBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPlainTextEdit, QScrollArea, QSpinBox, QSplitter,
    QStackedWidget, QVBoxLayout, QWidget,
)

from api import ai_provider, app_settings

from ..base import _label, _primary_btn, _secondary_btn, _set_status

logger = logging.getLogger(__name__)


def _mono_font() -> QFont:
    font = QFont("Menlo")
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setPointSize(11)
    return font


class _TemplatePreviewWorker(QObject):
    """Renders a template with sample resume data and compiles it to PDF."""

    finished = pyqtSignal(str, str)  # (pdf path, note — '' when none)
    error = pyqtSignal(str, str)     # (message, log excerpt)

    def __init__(self, template: str):
        super().__init__()
        self._template = template

    def run(self):
        from api.generate_resume.compile import LatexCompileError
        from api.generate_resume.preview import (
            TemplateRenderError, compile_template_preview,
        )
        try:
            pdf, note = compile_template_preview(self._template)
            self.finished.emit(str(pdf), note or "")
        except TemplateRenderError as exc:
            logger.info("_TemplatePreviewWorker.run — template error")
            self.error.emit(str(exc), "")
        except LatexCompileError as exc:
            logger.info("_TemplatePreviewWorker.run — latex error")
            self.error.emit(str(exc), exc.log_excerpt)
        except Exception as exc:
            logger.exception("_TemplatePreviewWorker.run — failed")
            self.error.emit(str(exc), "")


class ResumeMixin:
    def _build_resume_page(self) -> QWidget:
        self._preview_threads: list[QThread] = []
        self._preview_workers: list[_TemplatePreviewWorker] = []
        self._preview_pdf_path: str | None = None

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_resume_settings_pane())
        splitter.addWidget(self._build_resume_preview_pane())
        splitter.setSizes([520, 620])
        return splitter

    # ---------- left pane: settings + template editor ----------

    def _build_resume_settings_pane(self) -> QWidget:
        resume_card = QFrame()
        resume_card.setObjectName("card")
        rc_layout = QVBoxLayout(resume_card)
        rc_layout.setContentsMargins(28, 24, 28, 28)
        rc_layout.setSpacing(16)

        resume_title = QLabel("Resume")
        resume_title.setObjectName("card-title")
        rc_layout.addWidget(resume_title)

        resume_hint = QLabel(
            "Default resume template (LaTeX). Used as the structural base when "
            "generating tailored resumes. Leave empty to fall back to the built-in style."
        )
        resume_hint.setWordWrap(True)
        resume_hint.setObjectName("hint")
        rc_layout.addWidget(resume_hint)

        page_cap_row = QHBoxLayout()
        page_cap_row.setSpacing(12)
        page_cap_row.addWidget(_label("Page cap"))
        self._page_cap_spin = QSpinBox()
        self._page_cap_spin.setMinimum(1)
        self._page_cap_spin.setMaximum(99)
        self._page_cap_spin.setValue(ai_provider.get_resume_page_cap())
        self._page_cap_spin.setFixedWidth(80)
        page_cap_row.addWidget(self._page_cap_spin)
        page_cap_row.addStretch()
        rc_layout.addLayout(page_cap_row)

        max_iters_row = QHBoxLayout()
        max_iters_row.setSpacing(12)
        max_iters_row.addWidget(_label("Max iterations"))
        self._max_iters_spin = QSpinBox()
        self._max_iters_spin.setMinimum(1)
        self._max_iters_spin.setMaximum(99)
        self._max_iters_spin.setValue(ai_provider.get_max_generation_attempts())
        self._max_iters_spin.setFixedWidth(80)
        max_iters_row.addWidget(self._max_iters_spin)
        max_iters_row.addStretch()
        rc_layout.addLayout(max_iters_row)

        score_row = QHBoxLayout()
        score_row.setSpacing(12)
        score_row.addWidget(_label("Accept score ≥"))
        self._score_threshold_spin = QDoubleSpinBox()
        self._score_threshold_spin.setMinimum(0.0)
        self._score_threshold_spin.setMaximum(10.0)
        self._score_threshold_spin.setSingleStep(0.1)
        self._score_threshold_spin.setDecimals(2)
        self._score_threshold_spin.setValue(ai_provider.get_resume_score_threshold())
        self._score_threshold_spin.setFixedWidth(80)
        score_row.addWidget(self._score_threshold_spin)
        score_row.addStretch()
        rc_layout.addLayout(score_row)

        output_dir_row = QHBoxLayout()
        output_dir_row.setSpacing(12)
        output_dir_row.addWidget(_label("Output folder"))
        self._output_dir_edit = QLineEdit()
        self._output_dir_edit.setText(str(app_settings.get_resume_output_dir()))
        output_dir_row.addWidget(self._output_dir_edit, stretch=1)
        browse_btn = _secondary_btn("Browse…", width=100)
        browse_btn.clicked.connect(self._browse_output_dir)
        output_dir_row.addWidget(browse_btn)
        rc_layout.addLayout(output_dir_row)

        output_dir_hint = QLabel(
            "Default: ~/Documents/Resumes/. Folder is created automatically."
        )
        output_dir_hint.setWordWrap(True)
        output_dir_hint.setObjectName("hint")
        rc_layout.addWidget(output_dir_hint)

        self._resume_template_edit = QPlainTextEdit()
        self._resume_template_edit.setFont(_mono_font())
        self._resume_template_edit.setMinimumHeight(240)
        self._resume_template_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._resume_template_edit.setPlaceholderText(
            "Paste a LaTeX resume template here, or click “Load Default” to start "
            "from the built-in one…"
        )
        self._resume_template_edit.setPlainText(ai_provider.get_resume_template())
        rc_layout.addWidget(self._resume_template_edit, stretch=1)

        rt_btn_row = QHBoxLayout()
        rt_btn_row.setSpacing(12)
        rt_save_btn = _primary_btn("Save", width=100)
        rt_save_btn.clicked.connect(self._save_resume_template)
        rt_btn_row.addWidget(rt_save_btn)
        load_default_btn = _secondary_btn("Load Default", width=130)
        load_default_btn.clicked.connect(self._load_default_template)
        rt_btn_row.addWidget(load_default_btn)
        self._resume_template_status = QLabel("")
        self._resume_template_status.setObjectName("status-ok")
        rt_btn_row.addWidget(self._resume_template_status)
        rt_btn_row.addStretch()
        rc_layout.addLayout(rt_btn_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(resume_card)

        pane = QWidget()
        pane.setMinimumWidth(380)
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(24, 24, 12, 24)
        layout.addWidget(scroll)
        return pane

    # ---------- right pane: compiled PDF preview ----------

    def _build_resume_preview_pane(self) -> QWidget:
        pane = QWidget()
        pane.setMinimumWidth(360)
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(12, 24, 24, 24)
        layout.setSpacing(8)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self._preview_btn = _primary_btn("Compile Preview", width=160)
        self._preview_btn.clicked.connect(self._compile_template_preview)
        toolbar.addWidget(self._preview_btn)
        self._preview_status = QLabel("")
        self._preview_status.setObjectName("status-neutral")
        toolbar.addWidget(self._preview_status, 1)
        self._preview_open_btn = _secondary_btn("Open Externally", 140)
        self._preview_open_btn.clicked.connect(self._open_preview_external)
        self._preview_open_btn.setVisible(False)
        toolbar.addWidget(self._preview_open_btn, 0, Qt.AlignmentFlag.AlignRight)
        layout.addLayout(toolbar)

        self._preview_note = QLabel("")
        self._preview_note.setWordWrap(True)
        self._preview_note.setObjectName("hint")
        self._preview_note.setVisible(False)
        layout.addWidget(self._preview_note)

        self._preview_stack = QStackedWidget()

        self._preview_placeholder = QLabel(
            "Click “Compile Preview” to render this template\n"
            "as a PDF, filled with sample resume data."
        )
        self._preview_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_placeholder.setObjectName("muted")
        self._preview_stack.addWidget(self._preview_placeholder)

        self._preview_pdf_view = QWebEngineView()
        view_settings = self._preview_pdf_view.settings()
        view_settings.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, True)
        view_settings.setAttribute(QWebEngineSettings.WebAttribute.PdfViewerEnabled, True)
        self._preview_stack.addWidget(self._preview_pdf_view)

        self._preview_error_view = QPlainTextEdit()
        self._preview_error_view.setReadOnly(True)
        self._preview_error_view.setFont(_mono_font())
        self._preview_stack.addWidget(self._preview_error_view)

        layout.addWidget(self._preview_stack, 1)
        return pane

    def _compile_template_preview(self) -> None:
        template = self._resume_template_edit.toPlainText()

        self._preview_btn.setEnabled(False)
        self._preview_btn.setText("Compiling…")
        _set_status(self._preview_status, "neutral")
        self._preview_status.setText("Running pdflatex…")

        worker = _TemplatePreviewWorker(template)
        thread = QThread(self)
        worker.moveToThread(thread)

        def reset_button():
            self._preview_btn.setEnabled(True)
            self._preview_btn.setText("Compile Preview")

        def on_finished(pdf_path: str, note: str):
            reset_button()
            _set_status(self._preview_status, "ok")
            self._preview_status.setText("✓  Compiled")
            QTimer.singleShot(3000, lambda: self._preview_status.setText(""))
            self._preview_note.setText(note)
            self._preview_note.setVisible(bool(note))
            self._preview_pdf_path = pdf_path
            self._preview_open_btn.setVisible(True)
            self._preview_pdf_view.setUrl(QUrl.fromLocalFile(pdf_path))
            self._preview_stack.setCurrentWidget(self._preview_pdf_view)
            thread.quit()

        def on_error(message: str, log_excerpt: str):
            reset_button()
            _set_status(self._preview_status, "error")
            self._preview_status.setText("Compile failed")
            self._preview_note.setVisible(False)
            self._preview_open_btn.setVisible(False)
            self._preview_pdf_path = None
            body = message if not log_excerpt else f"{message}\n\n{log_excerpt}"
            self._preview_error_view.setPlainText(body)
            self._preview_stack.setCurrentWidget(self._preview_error_view)
            thread.quit()

        worker.finished.connect(on_finished)
        worker.error.connect(on_error)
        thread.started.connect(worker.run)
        thread.finished.connect(thread.deleteLater)
        self._preview_threads.append(thread)
        self._preview_workers.append(worker)
        def on_thread_finished():
            # Drop both before deleteLater runs, so cleanup_threads() never
            # touches a wrapper whose C++ object is gone.
            if worker in self._preview_workers:
                self._preview_workers.remove(worker)
            if thread in self._preview_threads:
                self._preview_threads.remove(thread)

        thread.finished.connect(on_thread_finished)
        thread.start()

    def _open_preview_external(self) -> None:
        if self._preview_pdf_path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._preview_pdf_path))

    def _load_default_template(self) -> None:
        from api.generate_resume.render import DEFAULT_TEMPLATE

        if self._resume_template_edit.toPlainText().strip():
            confirm = QMessageBox.question(
                self,
                "Load default template",
                "Replace the template in the editor with the built-in default?\n"
                "Unsaved edits will be lost.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return
        self._resume_template_edit.setPlainText(DEFAULT_TEMPLATE)

    # ---------- shared ----------

    def _browse_output_dir(self) -> None:
        current = self._output_dir_edit.text().strip() or str(app_settings.get_resume_output_dir())
        chosen = QFileDialog.getExistingDirectory(self, "Select resume output folder", current)
        if chosen:
            self._output_dir_edit.setText(chosen)

    def _save_resume_template(self) -> None:
        ai_provider.save_resume_template(self._resume_template_edit.toPlainText())
        ai_provider.save_resume_page_cap(self._page_cap_spin.value())
        ai_provider.save_max_generation_attempts(self._max_iters_spin.value())
        ai_provider.save_resume_score_threshold(self._score_threshold_spin.value())
        app_settings.save_resume_output_dir(self._output_dir_edit.text())
        _set_status(self._resume_template_status, "ok")
        self._resume_template_status.setText("✓  Saved")
        QTimer.singleShot(3000, lambda: self._resume_template_status.setText(""))
        if self._status_bar:
            self._status_bar.showMessage("✓  Resume template saved.", 3000)
        self._compile_template_preview()
