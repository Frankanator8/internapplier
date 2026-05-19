from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QFrame, QLineEdit, QLabel, QStatusBar, QTabWidget, QPlainTextEdit,
    QScrollArea, QSpinBox, QFileDialog, QCheckBox,
)
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QFont

from .. import ai_provider
from .base import _label, _primary_btn, _secondary_btn


class SettingsPage(QWidget):
    def __init__(self, status_bar: QStatusBar | None = None):
        super().__init__()
        self._status_bar = status_bar

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(scroll)

        inner = QWidget()
        scroll.setWidget(inner)

        outer = QVBoxLayout(inner)
        outer.setContentsMargins(40, 40, 40, 40)
        outer.setSpacing(0)

        card = QFrame()
        card.setObjectName("card")
        card.setMaximumWidth(560)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 24, 28, 28)
        card_layout.setSpacing(20)

        title = QLabel("AI Model Settings")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #0a66c2;")
        card_layout.addWidget(title)

        hint = QLabel(
            'Enter any model ID available on <a href="https://openrouter.ai/models">'
            'openrouter.ai/models</a>.'
        )
        hint.setOpenExternalLinks(True)
        hint.setWordWrap(True)
        hint.setStyleSheet("font-size: 12px; color: #666;")
        card_layout.addWidget(hint)

        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(form.labelAlignment())

        config = ai_provider._load_model_config()

        self._fast_edit = QLineEdit()
        self._fast_edit.setText(config.get("fast", ai_provider.DEFAULT_FAST_MODEL))
        self._fast_edit.setPlaceholderText(ai_provider.DEFAULT_FAST_MODEL)

        self._resize_edit(self._fast_edit, self._fast_edit.text())
        self._fast_edit.textChanged.connect(lambda t: self._resize_edit(self._fast_edit, t))

        fast_label = _label("Model")
        form.addRow(fast_label, self._fast_edit)
        card_layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        save_btn = _primary_btn("Save", width=100)
        save_btn.clicked.connect(self._save)
        self._inline_status = QLabel("")
        self._inline_status.setStyleSheet("font-size: 12px; color: #057642;")
        btn_row.addWidget(save_btn)
        btn_row.addWidget(self._inline_status)
        btn_row.addStretch()
        card_layout.addLayout(btn_row)

        outer.addWidget(card)

        # ── Resume card ──────────────────────────────────────────────────
        mono = QFont("Menlo")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        mono.setPointSize(11)

        resume_card = QFrame()
        resume_card.setObjectName("card")
        resume_card.setMaximumWidth(800)
        rc_layout = QVBoxLayout(resume_card)
        rc_layout.setContentsMargins(28, 24, 28, 28)
        rc_layout.setSpacing(16)

        resume_title = QLabel("Resume")
        resume_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #0a66c2;")
        rc_layout.addWidget(resume_title)

        resume_hint = QLabel(
            "Default resume template (LaTeX). Used as the structural base when "
            "generating tailored resumes. Leave empty to fall back to the built-in style."
        )
        resume_hint.setWordWrap(True)
        resume_hint.setStyleSheet("font-size: 12px; color: #666;")
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

        output_dir_row = QHBoxLayout()
        output_dir_row.setSpacing(12)
        output_dir_row.addWidget(_label("Output folder"))
        self._output_dir_edit = QLineEdit()
        self._output_dir_edit.setText(str(ai_provider.get_resume_output_dir()))
        output_dir_row.addWidget(self._output_dir_edit, stretch=1)
        browse_btn = _secondary_btn("Browse…", width=100)
        browse_btn.clicked.connect(self._browse_output_dir)
        output_dir_row.addWidget(browse_btn)
        rc_layout.addLayout(output_dir_row)

        output_dir_hint = QLabel(
            "Default: ~/Documents/Resumes/. Folder is created automatically."
        )
        output_dir_hint.setWordWrap(True)
        output_dir_hint.setStyleSheet("font-size: 12px; color: #666;")
        rc_layout.addWidget(output_dir_hint)

        self._resume_template_edit = QPlainTextEdit()
        self._resume_template_edit.setFont(mono)
        self._resume_template_edit.setMinimumHeight(280)
        self._resume_template_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self._resume_template_edit.setPlaceholderText(
            "Paste a LaTeX resume template here (e.g. Jake's Resume Template)…"
        )
        self._resume_template_edit.setPlainText(ai_provider.get_resume_template())
        rc_layout.addWidget(self._resume_template_edit)

        rt_btn_row = QHBoxLayout()
        rt_btn_row.setSpacing(12)
        rt_save_btn = _primary_btn("Save", width=100)
        rt_save_btn.clicked.connect(self._save_resume_template)
        self._resume_template_status = QLabel("")
        self._resume_template_status.setStyleSheet("font-size: 12px; color: #057642;")
        rt_btn_row.addWidget(rt_save_btn)
        rt_btn_row.addWidget(self._resume_template_status)
        rt_btn_row.addStretch()
        rc_layout.addLayout(rt_btn_row)

        outer.addSpacing(24)
        outer.addWidget(resume_card)

        # ── System Prompts card ──────────────────────────────────────────
        prompts_card = QFrame()
        prompts_card.setObjectName("card")
        prompts_card.setMaximumWidth(800)
        pc_layout = QVBoxLayout(prompts_card)
        pc_layout.setContentsMargins(28, 24, 28, 28)
        pc_layout.setSpacing(16)

        prompts_title = QLabel("System Prompts")
        prompts_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #0a66c2;")
        pc_layout.addWidget(prompts_title)

        prompts_hint = QLabel(
            "Customize the AI instructions for each feature. "
            "Changes take effect on the next use."
        )
        prompts_hint.setWordWrap(True)
        prompts_hint.setStyleSheet("font-size: 12px; color: #666;")
        pc_layout.addWidget(prompts_hint)

        self._auto_resync_checkbox = QCheckBox("Auto resync all prompts to default on app load")
        self._auto_resync_checkbox.setChecked(ai_provider.get_auto_resync_prompts())
        self._auto_resync_checkbox.stateChanged.connect(self._toggle_auto_resync)
        pc_layout.addWidget(self._auto_resync_checkbox)

        tabs = QTabWidget()
        mono = QFont("Menlo")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        mono.setPointSize(11)

        self._prompt_editors: dict[str, QPlainTextEdit] = {}
        self._prompt_statuses: dict[str, QLabel] = {}

        for label_text, filename in [
            ("Analyze Bullet", "analyze_bullet.txt"),
            ("Tailor Bullets", "tailor_resume.txt"),
            ("Generate Resume", "generate_resume.txt"),
            ("Grade Resume", "grade_resume.txt"),
            ("Research Company", "research_company.txt"),
        ]:
            tab = QWidget()
            tab_layout = QVBoxLayout(tab)
            tab_layout.setContentsMargins(12, 12, 12, 12)
            tab_layout.setSpacing(10)

            editor = QPlainTextEdit()
            editor.setFont(mono)
            editor.setMinimumHeight(260)
            editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
            editor.setPlainText(ai_provider.load_prompt(filename))
            tab_layout.addWidget(editor)

            btn_row = QHBoxLayout()
            btn_row.setSpacing(12)
            save_btn = _primary_btn("Save", width=100)
            sync_btn = _secondary_btn("Sync with Default", width=160)
            status_lbl = QLabel("")
            status_lbl.setStyleSheet("font-size: 12px; color: #057642;")

            save_btn.clicked.connect(
                lambda checked, fn=filename, ed=editor, sl=status_lbl: self._save_prompt(fn, ed, sl)
            )
            sync_btn.clicked.connect(
                lambda checked, fn=filename, ed=editor, sl=status_lbl: self._sync_prompt(fn, ed, sl)
            )

            btn_row.addWidget(save_btn)
            btn_row.addWidget(sync_btn)
            btn_row.addWidget(status_lbl)
            btn_row.addStretch()
            tab_layout.addLayout(btn_row)

            tabs.addTab(tab, label_text)
            self._prompt_editors[filename] = editor
            self._prompt_statuses[filename] = status_lbl

        pc_layout.addWidget(tabs)
        outer.addSpacing(24)
        outer.addWidget(prompts_card)
        outer.addStretch()

    def _toggle_auto_resync(self, state: int) -> None:
        enabled = bool(state)
        ai_provider.save_auto_resync_prompts(enabled)
        if self._status_bar:
            msg = "✓  Auto resync on load enabled." if enabled else "✓  Auto resync on load disabled."
            self._status_bar.showMessage(msg, 3000)

    def _sync_prompt(self, filename: str, editor: QPlainTextEdit, status_lbl: QLabel) -> None:
        default = ai_provider.default_prompt(filename)
        editor.setPlainText(default)
        ai_provider.save_prompt(filename, default)
        status_lbl.setStyleSheet("font-size: 12px; color: #057642;")
        status_lbl.setText("✓  Synced with default")
        QTimer.singleShot(3000, lambda: status_lbl.setText(""))
        if self._status_bar:
            self._status_bar.showMessage(f"✓  Prompt '{filename}' reset to default.", 3000)

    def _save_prompt(self, filename: str, editor: QPlainTextEdit, status_lbl: QLabel) -> None:
        ai_provider.save_prompt(filename, editor.toPlainText())
        status_lbl.setStyleSheet("font-size: 12px; color: #057642;")
        status_lbl.setText("✓  Saved")
        QTimer.singleShot(3000, lambda: status_lbl.setText(""))
        if self._status_bar:
            self._status_bar.showMessage(f"✓  Prompt '{filename}' saved.", 3000)

    def _browse_output_dir(self) -> None:
        current = self._output_dir_edit.text().strip() or str(ai_provider.get_resume_output_dir())
        chosen = QFileDialog.getExistingDirectory(self, "Select resume output folder", current)
        if chosen:
            self._output_dir_edit.setText(chosen)

    def _save_resume_template(self) -> None:
        ai_provider.save_resume_template(self._resume_template_edit.toPlainText())
        ai_provider.save_resume_page_cap(self._page_cap_spin.value())
        ai_provider.save_max_generation_attempts(self._max_iters_spin.value())
        ai_provider.save_resume_output_dir(self._output_dir_edit.text())
        self._resume_template_status.setStyleSheet("font-size: 12px; color: #057642;")
        self._resume_template_status.setText("✓  Saved")
        QTimer.singleShot(3000, lambda: self._resume_template_status.setText(""))
        if self._status_bar:
            self._status_bar.showMessage("✓  Resume template saved.", 3000)

    def _resize_edit(self, edit: QLineEdit, text: str) -> None:
        fm = edit.fontMetrics()
        text_px = fm.horizontalAdvance(text or edit.placeholderText())
        edit.setFixedWidth(max(120, min(text_px + 24, 400)))

    def _save(self):
        fast = self._fast_edit.text().strip()
        if not fast:
            self._inline_status.setStyleSheet("font-size: 12px; color: #b00;")
            self._inline_status.setText("Model is required.")
            return

        ai_provider.save_model_config(fast)

        self._inline_status.setStyleSheet("font-size: 12px; color: #057642;")
        self._inline_status.setText("✓  Saved")
        QTimer.singleShot(3000, lambda: self._inline_status.setText(""))

        if self._status_bar:
            self._status_bar.showMessage("✓  Model settings saved.", 3000)
