from __future__ import annotations

import logging
from pathlib import Path

from PyQt6.QtCore import QObject, Qt, QThread, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QFont, QGuiApplication
from PyQt6.QtWebEngineCore import QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
    QSplitter, QStackedWidget, QVBoxLayout, QWidget,
)

from api import data_store
from api.ai_provider import get_resume_page_cap
from api.generate_resume.manual_render import render_manual_resume
from api.generate_resume.persist import build_header_from_general_info, persist_pdf
from api.resume_builder_store import load_draft, save_draft

from ..base import _danger_btn, _label, _primary_btn, _secondary_btn, _set_status
from .builder_widgets import BuilderCanvas, BuilderPalette, BuilderScroll

logger = logging.getLogger(__name__)


def _mono_font() -> QFont:
    font = QFont("Menlo")
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setPointSize(11)
    return font


class _BuilderCompileWorker(QObject):
    finished = pyqtSignal(str, float)  # pdf path, fill
    error = pyqtSignal(str, str)       # message, log excerpt

    def __init__(self, latex: str):
        super().__init__()
        self._latex = latex

    def run(self):
        from api.generate_resume.compile import LatexCompileError, pdf_page_metrics
        from api.generate_resume.manual_render import compile_manual_preview

        try:
            pdf = compile_manual_preview(self._latex)
            fill = float(pdf_page_metrics(pdf)["fill"])
            self.finished.emit(str(pdf), fill)
        except LatexCompileError as exc:
            logger.info("_BuilderCompileWorker.run — latex error")
            self.error.emit(str(exc), exc.log_excerpt)
        except Exception as exc:
            logger.exception("_BuilderCompileWorker.run — failed")
            self.error.emit(str(exc), "")


class ResumeBuilderMixin:
    def _build_resume_builder_page(self) -> QWidget:
        self._builder_loading = True
        self._builder_latex = ""
        self._builder_pdf_path: str | None = None
        self._builder_busy = False
        self._builder_pending = False
        self._builder_did_initial_compile = False

        root = QWidget()
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 8, 0, 0)
        outer.setSpacing(10)

        outer.addLayout(self._build_builder_toolbar())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_builder_palette_pane())
        splitter.addWidget(self._build_builder_canvas_pane())
        splitter.addWidget(self._build_builder_preview_pane())
        splitter.setSizes([240, 440, 480])
        outer.addWidget(splitter, 1)

        self._builder_save_timer = QTimer(self)
        self._builder_save_timer.setSingleShot(True)
        self._builder_save_timer.setInterval(400)
        self._builder_save_timer.timeout.connect(self._builder_save_draft)

        self._builder_compile_timer = QTimer(self)
        self._builder_compile_timer.setSingleShot(True)
        self._builder_compile_timer.setInterval(800)
        self._builder_compile_timer.timeout.connect(self._builder_compile)

        self._builder_canvas.changed.connect(self._on_builder_canvas_changed)
        self._builder_company.textChanged.connect(self._builder_schedule_save)
        self._builder_title.textChanged.connect(self._builder_schedule_save)

        self._builder_load_draft()
        self._refresh_builder_palette()
        self._builder_loading = False
        return self._wrap_page("Resume Builder", root)

    def _build_builder_toolbar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setSpacing(8)

        bar.addWidget(_label("Company"))
        self._builder_company = QLineEdit()
        self._builder_company.setPlaceholderText("For the PDF filename")
        self._builder_company.setMaximumWidth(180)
        bar.addWidget(self._builder_company)

        bar.addWidget(_label("Job title"))
        self._builder_title = QLineEdit()
        self._builder_title.setPlaceholderText("Optional")
        self._builder_title.setMaximumWidth(180)
        bar.addWidget(self._builder_title)

        self._builder_compile_btn = _primary_btn("Compile", 100)
        self._builder_compile_btn.clicked.connect(self._builder_compile_now)
        bar.addWidget(self._builder_compile_btn)

        export_btn = _secondary_btn("Export PDF", 110)
        export_btn.clicked.connect(self._builder_export_pdf)
        bar.addWidget(export_btn)

        copy_btn = _secondary_btn("Copy LaTeX", 110)
        copy_btn.clicked.connect(self._builder_copy_latex)
        bar.addWidget(copy_btn)

        clear_btn = _danger_btn("Clear", 80)
        clear_btn.clicked.connect(self._builder_clear)
        bar.addWidget(clear_btn)

        self._builder_status = QLabel("")
        self._builder_status.setObjectName("status-neutral")
        self._builder_status.setWordWrap(True)
        bar.addWidget(self._builder_status, 1)
        return bar

    def _build_builder_palette_pane(self) -> QWidget:
        pane = QWidget()
        pane.setMinimumWidth(180)
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(6)
        layout.addWidget(_label("Profile items"))
        hint = QLabel("Drag onto the canvas, or double-click to add.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self._builder_palette = BuilderPalette()
        self._builder_palette.item_activated.connect(self._builder_add_from_palette)
        layout.addWidget(self._builder_palette, 1)
        return pane

    def _build_builder_canvas_pane(self) -> QWidget:
        pane = QWidget()
        pane.setMinimumWidth(260)
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(_label("Resume"))
        self._builder_canvas = BuilderCanvas()
        layout.addWidget(BuilderScroll(self._builder_canvas), 1)
        return pane

    def _build_builder_preview_pane(self) -> QWidget:
        pane = QWidget()
        pane.setMinimumWidth(280)
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(8, 0, 0, 0)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.addWidget(_label("Preview"))
        header.addStretch()
        self._builder_open_btn = _secondary_btn("Open Externally", 140)
        self._builder_open_btn.clicked.connect(self._builder_open_preview)
        self._builder_open_btn.setVisible(False)
        header.addWidget(self._builder_open_btn)
        layout.addLayout(header)

        self._builder_preview_stack = QStackedWidget()

        self._builder_preview_placeholder = QLabel(
            "Add items to the canvas to compile a PDF preview."
        )
        self._builder_preview_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._builder_preview_placeholder.setObjectName("muted")
        self._builder_preview_placeholder.setWordWrap(True)
        self._builder_preview_stack.addWidget(self._builder_preview_placeholder)

        self._builder_pdf_view = QWebEngineView()
        view_settings = self._builder_pdf_view.settings()
        view_settings.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, True)
        view_settings.setAttribute(QWebEngineSettings.WebAttribute.PdfViewerEnabled, True)
        self._builder_preview_stack.addWidget(self._builder_pdf_view)

        self._builder_error_view = QPlainTextEdit()
        self._builder_error_view.setReadOnly(True)
        self._builder_error_view.setFont(_mono_font())
        self._builder_preview_stack.addWidget(self._builder_error_view)

        layout.addWidget(self._builder_preview_stack, 1)
        return pane

    # ── palette / draft ─────────────────────────────────────────

    def _refresh_builder_palette(self) -> None:
        if not hasattr(self, "_builder_palette"):
            return
        profile = dict(self._get_profile() or {})
        if "skills" not in profile:
            try:
                profile["skills"] = data_store.load().get("skills") or []
            except Exception:
                logger.exception("_refresh_builder_palette — failed to load skills")
                profile["skills"] = []
        self._builder_palette.populate(profile)

    def _builder_add_from_palette(self, payload: dict) -> None:
        self._builder_canvas.add_from_palette(payload)

    def _builder_collect(self) -> dict:
        return {
            "company": self._builder_company.text().strip(),
            "job_title": self._builder_title.text().strip(),
            "sections": self._builder_canvas.serialize(),
        }

    def _builder_header(self) -> dict:
        profile = self._get_profile() or {}
        return build_header_from_general_info(profile.get("general_info") or {})

    def _builder_save_draft(self) -> None:
        try:
            save_draft(self._builder_collect())
        except Exception:
            logger.exception("_builder_save_draft — failed")

    def _builder_load_draft(self) -> None:
        try:
            draft = load_draft()
        except Exception:
            logger.exception("_builder_load_draft — failed")
            return
        self._builder_company.setText(draft.get("company") or "")
        self._builder_title.setText(draft.get("job_title") or "")
        self._builder_canvas.load_sections(draft.get("sections") or [])

    def _builder_schedule_save(self) -> None:
        if self._builder_loading:
            return
        self._builder_save_timer.start()

    def _on_builder_canvas_changed(self) -> None:
        if self._builder_loading:
            return
        self._builder_save_timer.start()
        self._builder_compile_timer.start()

    def _builder_compile_now(self) -> None:
        self._builder_compile_timer.stop()
        self._builder_compile()

    # ── compile / preview ───────────────────────────────────────

    def _builder_compile(self) -> None:
        if self._builder_loading:
            return
        if self._builder_busy:
            self._builder_pending = True
            return

        latex = render_manual_resume(self._builder_header(), self._builder_canvas.serialize())
        self._builder_latex = latex
        self._builder_busy = True
        self._builder_compile_btn.setEnabled(False)
        self._builder_compile_btn.setText("Compiling…")
        _set_status(self._builder_status, "neutral")
        self._builder_status.setText("Running pdflatex…")

        worker = _BuilderCompileWorker(latex)
        thread = QThread(self)
        worker.moveToThread(thread)

        def reset_button():
            self._builder_compile_btn.setEnabled(True)
            self._builder_compile_btn.setText("Compile")
            self._builder_busy = False

        def on_finished(pdf_path: str, fill: float):
            reset_button()
            page_cap = get_resume_page_cap()
            overflow = fill > page_cap + 1e-6
            _set_status(self._builder_status, "error" if overflow else "ok")
            self._builder_status.setText(
                f"{fill:.2f} / {page_cap} page{'s' if page_cap != 1 else ''}"
                + (" — over the page cap" if overflow else "")
            )
            self._builder_pdf_path = pdf_path
            self._builder_open_btn.setVisible(True)
            self._builder_pdf_view.setUrl(QUrl.fromLocalFile(pdf_path))
            self._builder_preview_stack.setCurrentWidget(self._builder_pdf_view)
            thread.quit()
            if self._builder_pending:
                self._builder_pending = False
                self._builder_compile()

        def on_error(message: str, log_excerpt: str):
            reset_button()
            _set_status(self._builder_status, "error")
            self._builder_status.setText("Compile failed")
            self._builder_open_btn.setVisible(False)
            body = message if not log_excerpt else f"{message}\n\n{log_excerpt}"
            self._builder_error_view.setPlainText(body)
            self._builder_preview_stack.setCurrentWidget(self._builder_error_view)
            thread.quit()
            if self._builder_pending:
                self._builder_pending = False
                self._builder_compile()

        worker.finished.connect(on_finished)
        worker.error.connect(on_error)
        thread.started.connect(worker.run)
        thread.finished.connect(thread.deleteLater)
        self._threads.append(thread)
        self._workers.append(worker)

        def on_thread_finished():
            if worker in self._workers:
                self._workers.remove(worker)
            if thread in self._threads:
                self._threads.remove(thread)

        thread.finished.connect(on_thread_finished)
        thread.start()

    def _builder_export_pdf(self) -> None:
        if not self._builder_pdf_path or not Path(self._builder_pdf_path).exists():
            _set_status(self._builder_status, "error")
            self._builder_status.setText("Compile a preview before exporting.")
            return
        company = self._builder_company.text().strip()
        job_title = self._builder_title.text().strip()
        written, desired, collided = persist_pdf(
            Path(self._builder_pdf_path), None, company or None, job_title or None,
        )
        payload = {
            "pdf": str(written) if written else "",
            "pdf_desired": str(desired) if desired else "",
            "pdf_collision": collided,
        }
        self._maybe_resolve_pdf_collision(payload)
        final = payload.get("pdf") or ""
        if not final:
            _set_status(self._builder_status, "error")
            self._builder_status.setText("Export failed.")
            return
        _set_status(self._builder_status, "ok")
        self._builder_status.setText(f"Saved to {final}")

    def _builder_copy_latex(self) -> None:
        latex = self._builder_latex or render_manual_resume(
            self._builder_header(), self._builder_canvas.serialize(),
        )
        self._builder_latex = latex
        QGuiApplication.clipboard().setText(latex)
        _set_status(self._builder_status, "ok")
        self._builder_status.setText("LaTeX copied to clipboard.")

    def _builder_clear(self) -> None:
        if self._builder_canvas.serialize():
            confirm = QMessageBox.question(
                self,
                "Clear canvas",
                "Remove every section from this resume? Your profile is not changed.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return
        self._builder_loading = True
        self._builder_canvas.load_sections([])
        self._builder_loading = False
        self._builder_compile_timer.stop()
        self._builder_pending = False
        self._builder_latex = ""
        self._builder_pdf_path = None
        self._builder_open_btn.setVisible(False)
        self._builder_preview_stack.setCurrentWidget(self._builder_preview_placeholder)
        self._builder_status.setText("")
        self._builder_save_draft()

    def _builder_open_preview(self) -> None:
        if self._builder_pdf_path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._builder_pdf_path))
