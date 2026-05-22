from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox, QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QScrollArea,
    QStackedWidget, QTabBar, QVBoxLayout, QWidget,
)

from api import ai_provider

from ..base import _primary_btn, _secondary_btn, _set_status


def _prompt_label(filename: str) -> str:
    if filename.endswith(".schema.json"):
        stem = filename[: -len(".schema.json")]
    elif filename.endswith(".tool.json"):
        stem = filename[: -len(".tool.json")]
    elif filename.endswith(".txt"):
        stem = filename[: -len(".txt")]
    else:
        stem = filename.rsplit(".", 1)[0]
    return stem.replace("_", " ").replace(".", " ").title()


class PromptsMixin:
    def _build_prompts_page(self) -> QWidget:
        self._prompt_editors: dict[str, QPlainTextEdit] = {}
        self._prompt_statuses: dict[str, QLabel] = {}

        all_files = ai_provider.list_prompt_files()
        schema_stems = {
            f[: -len(".schema.json")] for f in all_files if f.endswith(".schema.json")
        }
        txt_files = sorted(
            (f for f in all_files if f.endswith(".txt")),
            key=lambda f: (f[: -len(".txt")] not in schema_stems, _prompt_label(f)),
        )
        schema_files = sorted(
            (f for f in all_files if not f.endswith(".txt")), key=_prompt_label
        )

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(20)

        container_layout.addWidget(self._build_auto_reload_card())
        container_layout.addWidget(self._build_prompts_card("System Prompts", txt_files))
        container_layout.addWidget(self._build_prompts_card("JSON Schemas", schema_files))

        return self._wrap_scroll(container)

    def _build_auto_reload_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        card.setMaximumWidth(800)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(12)

        title = QLabel("Auto Reload")
        title.setObjectName("card-title")
        layout.addWidget(title)

        hint = QLabel(
            "Customize the AI instructions for each feature. "
            "Changes take effect on the next use."
        )
        hint.setWordWrap(True)
        hint.setObjectName("hint")
        layout.addWidget(hint)

        self._auto_resync_checkbox = QCheckBox("Auto resync all prompts to default on app load")
        self._auto_resync_checkbox.setChecked(ai_provider.get_auto_resync_prompts())
        self._auto_resync_checkbox.stateChanged.connect(self._toggle_auto_resync)
        layout.addWidget(self._auto_resync_checkbox)

        return card

    def _build_prompts_card(self, title_text: str, filenames: list[str]) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        card.setMaximumWidth(800)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(16)

        title = QLabel(title_text)
        title.setObjectName("card-title")
        layout.addWidget(title)

        tab_bar = QTabBar()
        tab_bar.setUsesScrollButtons(False)
        tab_bar.setElideMode(Qt.TextElideMode.ElideNone)
        tab_bar.setExpanding(False)
        tab_bar.setDrawBase(False)
        stack = QStackedWidget()
        tab_bar.currentChanged.connect(stack.setCurrentIndex)

        mono = QFont("Menlo")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        mono.setPointSize(11)

        for filename in filenames:
            tab = QWidget()
            tab_layout = QVBoxLayout(tab)
            tab_layout.setContentsMargins(12, 12, 12, 12)
            tab_layout.setSpacing(10)

            editor = QPlainTextEdit()
            editor.setFont(mono)
            editor.setMinimumHeight(260)
            editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
            editor.setPlainText(ai_provider.load_prompt_raw(filename))
            tab_layout.addWidget(editor)

            btn_row = QHBoxLayout()
            btn_row.setSpacing(12)
            save_btn = _primary_btn("Save", width=100)
            sync_btn = _secondary_btn("Sync with Default", width=160)
            status_lbl = QLabel("")
            status_lbl.setObjectName("status-ok")

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

            tab_bar.addTab(_prompt_label(filename))
            stack.addWidget(tab)
            self._prompt_editors[filename] = editor
            self._prompt_statuses[filename] = status_lbl

        bar_scroll = QScrollArea()
        bar_scroll.setWidgetResizable(True)
        bar_scroll.setFrameShape(QFrame.Shape.NoFrame)
        bar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        bar_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        bar_scroll.setFixedHeight(tab_bar.sizeHint().height() + 16)
        bar_scroll.setWidget(tab_bar)
        layout.addWidget(bar_scroll)
        layout.addWidget(stack)

        return card

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
        _set_status(status_lbl, "ok")
        status_lbl.setText("✓  Synced with default")
        QTimer.singleShot(3000, lambda: status_lbl.setText(""))
        if self._status_bar:
            self._status_bar.showMessage(f"✓  Prompt '{filename}' reset to default.", 3000)

    def _save_prompt(self, filename: str, editor: QPlainTextEdit, status_lbl: QLabel) -> None:
        ai_provider.save_prompt(filename, editor.toPlainText())
        _set_status(status_lbl, "ok")
        status_lbl.setText("✓  Saved")
        QTimer.singleShot(3000, lambda: status_lbl.setText(""))
        if self._status_bar:
            self._status_bar.showMessage(f"✓  Prompt '{filename}' saved.", 3000)
