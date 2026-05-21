from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox, QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QTabWidget,
    QVBoxLayout, QWidget,
)

from api import ai_provider

from ..base import _primary_btn, _secondary_btn


class PromptsMixin:
    def _build_prompts_page(self) -> QWidget:
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
        tabs.setUsesScrollButtons(True)
        tabs.setElideMode(Qt.TextElideMode.ElideNone)
        tabs.tabBar().setUsesScrollButtons(True)
        tabs.tabBar().setElideMode(Qt.TextElideMode.ElideNone)
        mono = QFont("Menlo")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        mono.setPointSize(11)

        self._prompt_editors: dict[str, QPlainTextEdit] = {}
        self._prompt_statuses: dict[str, QLabel] = {}

        for label_text, filename in [
            ("Analyze Bullet", "analyze_bullet.txt"),
            ("Generate Resume", "generate_resume.txt"),
            ("Grade Resume", "grade_resume.txt"),
            ("Score Alignment", "score_alignment.txt"),
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

        return self._wrap_scroll(prompts_card)

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
