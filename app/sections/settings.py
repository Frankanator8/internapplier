from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QFrame, QLineEdit, QLabel, QStatusBar, QTabWidget, QPlainTextEdit,
)
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QFont

from .. import ai_provider
from .base import _label, _primary_btn, _secondary_btn


class SettingsPage(QWidget):
    def __init__(self, status_bar: QStatusBar | None = None):
        super().__init__()
        self._status_bar = status_bar

        outer = QVBoxLayout(self)
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

        self._powerful_edit = QLineEdit()
        self._powerful_edit.setText(config.get("powerful", ai_provider.DEFAULT_POWERFUL_MODEL))
        self._powerful_edit.setPlaceholderText(ai_provider.DEFAULT_POWERFUL_MODEL)

        self._resize_edit(self._fast_edit, self._fast_edit.text())
        self._resize_edit(self._powerful_edit, self._powerful_edit.text())
        self._fast_edit.textChanged.connect(lambda t: self._resize_edit(self._fast_edit, t))
        self._powerful_edit.textChanged.connect(lambda t: self._resize_edit(self._powerful_edit, t))

        fast_label = _label("Fast model")
        powerful_label = _label("Powerful model")
        form.addRow(fast_label, self._fast_edit)
        form.addRow(powerful_label, self._powerful_edit)
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

        tabs = QTabWidget()
        mono = QFont("Menlo")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        mono.setPointSize(11)

        self._prompt_editors: dict[str, QPlainTextEdit] = {}
        self._prompt_statuses: dict[str, QLabel] = {}

        for label_text, filename in [
            ("Analyze Bullet", "analyze_bullet.txt"),
            ("Tailor Resume", "tailor_resume.txt"),
            ("Generate Resume", "generate_resume.txt"),
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

    def _resize_edit(self, edit: QLineEdit, text: str) -> None:
        fm = edit.fontMetrics()
        text_px = fm.horizontalAdvance(text or edit.placeholderText())
        edit.setFixedWidth(max(120, min(text_px + 24, 400)))

    def _save(self):
        fast = self._fast_edit.text().strip()
        powerful = self._powerful_edit.text().strip()
        if not fast or not powerful:
            self._inline_status.setStyleSheet("font-size: 12px; color: #b00;")
            self._inline_status.setText("Both fields are required.")
            return

        ai_provider.save_model_config(fast, powerful)

        self._inline_status.setStyleSheet("font-size: 12px; color: #057642;")
        self._inline_status.setText("✓  Saved")
        QTimer.singleShot(3000, lambda: self._inline_status.setText(""))

        if self._status_bar:
            self._status_bar.showMessage("✓  Model settings saved.", 3000)
