from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractSpinBox, QDoubleSpinBox, QFileDialog, QFrame, QHBoxLayout,
    QPlainTextEdit, QScrollArea, QSpinBox, QSplitter, QStatusBar, QVBoxLayout,
    QWidget,
)

from api import ai_provider, app_settings
from app.ui.latex_preview import LatexPreviewPane, compile_template
from app.ui.widgets import (
    button, confirm, flash_status, hint, label, line_edit, mono_font, open_path,
    set_status, status_label,
)

from .common import SettingsCard, SettingsPane

_PREVIEW_LABEL = "Compile Preview"


def _labeled_spin(caption: str, spin: QAbstractSpinBox) -> QHBoxLayout:
    spin.setFixedWidth(80)
    row = QHBoxLayout()
    row.setSpacing(12)
    row.addWidget(label(caption))
    row.addWidget(spin)
    row.addStretch()
    return row


class ResumeSettings(SettingsPane):
    """Resume generation settings, the LaTeX template, and a sample-data preview."""

    def __init__(self, status_bar: QStatusBar):
        super().__init__(status_bar)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_settings_pane())
        splitter.addWidget(self._build_preview_pane())
        splitter.setSizes([520, 620])
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)

    # ── Left: settings + template editor ────────────────────────
    def _build_settings_pane(self) -> QWidget:
        card = SettingsCard("Resume", max_width=None)
        layout = card.body
        layout.addWidget(hint(
            "Default resume template (LaTeX). Used as the structural base when "
            "generating tailored resumes. Leave empty to fall back to the built-in style."
        ))

        self._page_cap_spin = QSpinBox()
        self._page_cap_spin.setRange(1, 99)
        self._page_cap_spin.setValue(ai_provider.get_resume_page_cap())
        layout.addLayout(_labeled_spin("Page cap", self._page_cap_spin))

        self._max_iters_spin = QSpinBox()
        self._max_iters_spin.setRange(1, 99)
        self._max_iters_spin.setValue(ai_provider.get_max_generation_attempts())
        layout.addLayout(_labeled_spin("Max iterations", self._max_iters_spin))

        self._score_threshold_spin = QDoubleSpinBox()
        self._score_threshold_spin.setRange(0.0, 10.0)
        self._score_threshold_spin.setSingleStep(0.1)
        self._score_threshold_spin.setDecimals(2)
        self._score_threshold_spin.setValue(ai_provider.get_resume_score_threshold())
        layout.addLayout(_labeled_spin("Accept score ≥", self._score_threshold_spin))

        output_dir_row = QHBoxLayout()
        output_dir_row.setSpacing(12)
        output_dir_row.addWidget(label("Output folder"))
        self._output_dir_edit = line_edit(text=str(app_settings.get_resume_output_dir()))
        output_dir_row.addWidget(self._output_dir_edit, stretch=1)
        browse_btn = button("Browse…", "secondary", 100)
        browse_btn.clicked.connect(self._browse_output_dir)
        output_dir_row.addWidget(browse_btn)
        layout.addLayout(output_dir_row)
        layout.addWidget(hint("Default: ~/Documents/Resumes/. Folder is created automatically."))

        self._template_edit = QPlainTextEdit()
        self._template_edit.setFont(mono_font())
        self._template_edit.setMinimumHeight(240)
        self._template_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._template_edit.setPlaceholderText(
            "Paste a LaTeX resume template here, or click “Load Default” to start "
            "from the built-in one…"
        )
        self._template_edit.setPlainText(ai_provider.get_resume_template())
        layout.addWidget(self._template_edit, stretch=1)

        load_default_btn = button("Load Default", "secondary", 130)
        load_default_btn.clicked.connect(self._load_default_template)
        row, self._save_status = self._save_row(self._save, load_default_btn)
        layout.addLayout(row)

        # The card fills the scroll viewport so the template editor can stretch.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(card)
        pane = QWidget()
        pane.setMinimumWidth(380)
        pane_layout = QVBoxLayout(pane)
        pane_layout.setContentsMargins(24, 24, 12, 24)
        pane_layout.addWidget(scroll)
        return pane

    # ── Right: compiled PDF preview ─────────────────────────────
    def _build_preview_pane(self) -> QWidget:
        pane = QWidget()
        pane.setMinimumWidth(360)
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(12, 24, 24, 24)
        layout.setSpacing(8)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self._preview_btn = button(_PREVIEW_LABEL, width=160)
        toolbar.addWidget(self._preview_btn)
        self._preview_status = status_label()
        self._preview_status.setWordWrap(False)
        toolbar.addWidget(self._preview_status, 1)
        self._open_btn = button("Open Externally", "secondary", 140)
        self._open_btn.setVisible(False)
        toolbar.addWidget(self._open_btn, 0, Qt.AlignmentFlag.AlignRight)
        layout.addLayout(toolbar)

        self._preview_note = hint("")
        self._preview_note.setVisible(False)
        layout.addWidget(self._preview_note)

        self._preview = LatexPreviewPane(
            self._template_edit.toPlainText,
            compile_template,
            "Click “Compile Preview” to render this template\n"
            "as a PDF, filled with sample resume data.",
        )
        self._preview.busy_changed.connect(self._on_preview_busy)
        self._preview.compiled.connect(self._on_preview_compiled)
        self._preview.failed.connect(self._on_preview_failed)
        self._preview_btn.clicked.connect(self._preview.compile_now)
        self._open_btn.clicked.connect(lambda: open_path(self._preview.pdf_path))
        layout.addWidget(self._preview, 1)
        return pane

    def _on_preview_busy(self, busy: bool) -> None:
        self._preview_btn.setEnabled(not busy)
        self._preview_btn.setText("Compiling…" if busy else _PREVIEW_LABEL)
        if busy:
            set_status(self._preview_status, "neutral", "Running pdflatex…")

    def _on_preview_compiled(self, result: dict) -> None:
        flash_status(self._preview_status, "✓  Compiled")
        note = result.get("note", "")
        self._preview_note.setText(note)
        self._preview_note.setVisible(bool(note))
        self._open_btn.setVisible(True)

    def _on_preview_failed(self, _log: str) -> None:
        set_status(self._preview_status, "error", "Compile failed")
        self._preview_note.setVisible(False)
        self._open_btn.setVisible(False)

    # ── Actions ─────────────────────────────────────────────────
    def _load_default_template(self) -> None:
        if self._template_edit.toPlainText().strip() and not confirm(
            self, "Load default template",
            "Replace the template in the editor with the built-in default?\n"
            "Unsaved edits will be lost.",
        ):
            return
        self._template_edit.setPlainText(ai_provider.default_prompt("resume_template.txt"))

    def _browse_output_dir(self) -> None:
        current = self._output_dir_edit.text().strip() or str(app_settings.get_resume_output_dir())
        chosen = QFileDialog.getExistingDirectory(self, "Select resume output folder", current)
        if chosen:
            self._output_dir_edit.setText(chosen)

    def _save(self) -> None:
        ai_provider.save_resume_template(self._template_edit.toPlainText())
        ai_provider.save_resume_page_cap(self._page_cap_spin.value())
        ai_provider.save_max_generation_attempts(self._max_iters_spin.value())
        ai_provider.save_resume_score_threshold(self._score_threshold_spin.value())
        app_settings.save_resume_output_dir(self._output_dir_edit.text())
        self._announce(self._save_status, "✓  Resume template saved.")
        self._preview.compile_now()
