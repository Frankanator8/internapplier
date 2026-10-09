from __future__ import annotations

import logging
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QHBoxLayout, QWidget

from api.generate_resume.manual_render import render_manual_resume
from api.generate_resume.persist import build_header_from_general_info, persist_pdf
from api.resume_builder_store import load_draft, save_draft
from app.context import AppContext
from app.ui.latex_preview import LatexPreviewPane, compile_with_fill, page_fill_status
from app.ui.widgets import (
    BusyButton, button, confirm, copy_text, hint, hsplitter, label, line_edit,
    open_path, set_status, set_titled_content, status_label, vbox_widget,
)

from .builder import BuilderCanvas, BuilderPalette, BuilderScroll
from .collision import resolve_pdf_collision

logger = logging.getLogger(__name__)

_EMPTY_PREVIEW = "Add items to the canvas to compile a PDF preview."


class ResumeBuilderPage(QWidget):
    """Hand-assemble a resume from profile items, with a live PDF preview.

    The canvas is auto-saved as a draft and recompiled shortly after each edit.
    """

    def __init__(self, ctx: AppContext, parent=None):
        super().__init__(parent)
        self._ctx = ctx
        self._loading = True  # suppress autosave/compile while populating
        self._did_initial_compile = False
        self._latex = ""  # source of the last successful compile, for export

        root, outer = vbox_widget((0, 8, 0, 0), spacing=10)
        outer.addLayout(self._build_toolbar())

        palette_pane, palette_layout = vbox_widget((0, 0, 8, 0))
        palette_pane.setMinimumWidth(180)
        palette_layout.addWidget(label("Profile items"))
        palette_layout.addWidget(hint("Drag onto the canvas, or double-click to add."))
        self._palette = BuilderPalette()
        palette_layout.addWidget(self._palette, 1)

        canvas_pane, canvas_layout = vbox_widget()
        canvas_pane.setMinimumWidth(260)
        canvas_layout.addWidget(label("Resume"))
        self._canvas = BuilderCanvas()
        canvas_layout.addWidget(BuilderScroll(self._canvas), 1)
        self._palette.item_activated.connect(self._canvas.add_from_palette)

        preview_pane, preview_layout = vbox_widget((8, 0, 0, 0))
        preview_pane.setMinimumWidth(280)
        self._open_btn = button("Open Externally", "secondary", 140)
        self._open_btn.setVisible(False)
        header = QHBoxLayout()
        header.addWidget(label("Preview"))
        header.addStretch()
        header.addWidget(self._open_btn)
        preview_layout.addLayout(header)
        self._preview = LatexPreviewPane(self._render_latex, compile_with_fill, _EMPTY_PREVIEW)
        self._preview.busy_changed.connect(self._on_compile_busy)
        self._preview.compiled.connect(self._on_compiled)
        self._preview.failed.connect(self._on_compile_failed)
        self._open_btn.clicked.connect(lambda: open_path(self._preview.pdf_path))
        preview_layout.addWidget(self._preview, 1)

        outer.addWidget(hsplitter(palette_pane, canvas_pane, preview_pane, sizes=[240, 440, 480]), 1)
        set_titled_content(self, "Resume Builder", root)

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(400)
        self._save_timer.timeout.connect(self._save_draft)

        self._canvas.changed.connect(self._on_canvas_changed)
        self._company.textChanged.connect(self._schedule_save)
        self._title.textChanged.connect(self._schedule_save)

        self._load_draft()
        self.refresh_palette()
        self._loading = False

    def _build_toolbar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setSpacing(8)
        self._company = line_edit("For the PDF filename")
        self._title = line_edit("Optional")
        for caption, edit in (("Company", self._company), ("Job title", self._title)):
            edit.setMaximumWidth(180)
            bar.addWidget(label(caption))
            bar.addWidget(edit)

        self._compile_btn = BusyButton("Compile", "Compiling…", width=100)
        self._compile_btn.clicked.connect(lambda: self._preview.compile_now())
        bar.addWidget(self._compile_btn)
        for text, kind, width, slot in (
            ("Export PDF", "secondary", 110, self._export_pdf),
            ("Copy LaTeX", "secondary", 110, self._copy_latex),
            ("Clear", "danger", 80, self._clear),
        ):
            btn = button(text, kind, width)
            btn.clicked.connect(slot)
            bar.addWidget(btn)

        self._status = status_label()
        bar.addWidget(self._status, 1)
        return bar

    # ── Lifecycle ───────────────────────────────────────────────
    def on_shown(self) -> None:
        self.refresh_palette()
        if not self._did_initial_compile:
            self._did_initial_compile = True
            if self._canvas.serialize():
                self._preview.compile_now()

    def refresh_palette(self) -> None:
        self._palette.populate(self._ctx.get_profile())

    # ── Draft ───────────────────────────────────────────────────
    def _render_latex(self) -> str:
        header = build_header_from_general_info(self._ctx.get_profile().get("general_info") or {})
        return render_manual_resume(header, self._canvas.serialize())

    def _save_draft(self) -> None:
        try:
            save_draft({
                "company": self._company.text().strip(),
                "job_title": self._title.text().strip(),
                "sections": self._canvas.serialize(),
            })
        except Exception:
            logger.exception("ResumeBuilderPage — saving draft failed")

    def _load_draft(self) -> None:
        try:
            draft = load_draft()
        except Exception:
            logger.exception("ResumeBuilderPage — loading draft failed")
            return
        self._company.setText(draft.get("company") or "")
        self._title.setText(draft.get("job_title") or "")
        self._canvas.load_sections(draft.get("sections") or [])

    def _schedule_save(self) -> None:
        if not self._loading:
            self._save_timer.start()

    def _on_canvas_changed(self) -> None:
        if not self._loading:
            self._save_timer.start()
            self._preview.schedule()

    # ── Compile results ─────────────────────────────────────────
    def _on_compile_busy(self, busy: bool) -> None:
        self._compile_btn.set_busy(busy)
        if busy:
            set_status(self._status, "neutral", "Running pdflatex…")

    def _on_compiled(self, result: dict) -> None:
        self._latex = result["latex"]
        set_status(self._status, *page_fill_status(result["fill"]))
        self._open_btn.setVisible(True)

    def _on_compile_failed(self, _log: str) -> None:
        set_status(self._status, "error", "Compile failed")
        self._open_btn.setVisible(False)

    # ── Actions ─────────────────────────────────────────────────
    def _export_pdf(self) -> None:
        pdf_path = self._preview.pdf_path
        if not pdf_path or not Path(pdf_path).exists():
            set_status(self._status, "error", "Compile a preview before exporting.")
            return
        company = self._company.text().strip()
        job_title = self._title.text().strip()
        written, desired, collided = persist_pdf(
            Path(pdf_path), None, company or None, job_title or None,
            latex=self._latex or None,
        )
        payload = {
            "pdf": str(written) if written else "",
            "pdf_desired": str(desired) if desired else "",
            "pdf_collision": collided,
        }
        resolve_pdf_collision(self, payload)
        if payload["pdf"]:
            set_status(self._status, "ok", f"Saved to {payload['pdf']}")
        else:
            set_status(self._status, "error", "Export failed.")

    def _copy_latex(self) -> None:
        copy_text(self._render_latex())
        set_status(self._status, "ok", "LaTeX copied to clipboard.")

    def _clear(self) -> None:
        if self._canvas.serialize() and not confirm(
            self, "Clear canvas",
            "Remove every section from this resume? Your profile is not changed.",
        ):
            return
        self._loading = True
        self._canvas.load_sections([])
        self._loading = False
        self._latex = ""
        self._preview.reset()
        self._open_btn.setVisible(False)
        self._status.setText("")
        self._save_draft()
