from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox, QFrame, QLabel, QPlainTextEdit, QScrollArea, QStackedWidget,
    QStatusBar, QTabBar, QVBoxLayout, QWidget,
)

from api import ai_provider, app_settings
from app.ui.widgets import button, hint, mono_font

from .common import SettingsCard, SettingsPane

_SUFFIXES = (".schema.json", ".tool.json", ".txt")


def _stem(filename: str) -> str:
    for suffix in _SUFFIXES:
        if filename.endswith(suffix):
            return filename[: -len(suffix)]
    return filename.rsplit(".", 1)[0]


def _prompt_label(filename: str) -> str:
    return _stem(filename).replace("_", " ").replace(".", " ").title()


class PromptsSettings(SettingsPane):
    def __init__(self, status_bar: QStatusBar):
        super().__init__(status_bar)
        all_files = ai_provider.list_prompt_files()
        schema_stems = {_stem(f) for f in all_files if f.endswith(".schema.json")}
        # Prompts that have a JSON schema first, then alphabetical.
        txt_files = sorted(
            (f for f in all_files if f.endswith(".txt")),
            key=lambda f: (_stem(f) not in schema_stems, _prompt_label(f)),
        )
        schema_files = sorted((f for f in all_files if not f.endswith(".txt")), key=_prompt_label)

        self._set_cards(
            self._auto_reload_card(),
            self._prompts_card("System Prompts", txt_files),
            self._prompts_card("JSON Schemas", schema_files),
        )

    def _auto_reload_card(self) -> QFrame:
        card = SettingsCard("Auto Reload", spacing=12)
        card.body.addWidget(hint(
            "Customize the AI instructions for each feature. "
            "Changes take effect on the next use."
        ))
        checkbox = QCheckBox("Auto resync all prompts to default on app load")
        checkbox.setChecked(app_settings.get_auto_resync_prompts())
        checkbox.stateChanged.connect(self._toggle_auto_resync)
        card.body.addWidget(checkbox)
        return card

    def _prompts_card(self, title: str, filenames: list[str]) -> QFrame:
        card = SettingsCard(title)
        tab_bar = QTabBar()
        tab_bar.setUsesScrollButtons(False)
        tab_bar.setElideMode(Qt.TextElideMode.ElideNone)
        tab_bar.setExpanding(False)
        tab_bar.setDrawBase(False)
        stack = QStackedWidget()
        tab_bar.currentChanged.connect(stack.setCurrentIndex)

        for filename in filenames:
            tab_bar.addTab(_prompt_label(filename))
            stack.addWidget(self._prompt_editor(filename))

        bar_scroll = QScrollArea()
        bar_scroll.setWidgetResizable(True)
        bar_scroll.setFrameShape(QFrame.Shape.NoFrame)
        bar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        bar_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        bar_scroll.setFixedHeight(tab_bar.sizeHint().height() + 16)
        bar_scroll.setWidget(tab_bar)
        card.body.addWidget(bar_scroll)
        card.body.addWidget(stack)
        return card

    def _prompt_editor(self, filename: str) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        editor = QPlainTextEdit()
        editor.setFont(mono_font())
        editor.setMinimumHeight(260)
        editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        editor.setPlainText(ai_provider.load_prompt_raw(filename))
        layout.addWidget(editor)

        sync_btn = button("Sync with Default", "secondary", 160)
        row, status = self._save_row(lambda: self._save_prompt(filename, editor, status), sync_btn)
        sync_btn.clicked.connect(lambda: self._sync_prompt(filename, editor, status))
        layout.addLayout(row)
        return tab

    def _toggle_auto_resync(self, state: int) -> None:
        enabled = bool(state)
        app_settings.save_auto_resync_prompts(enabled)
        self._status_bar.showMessage(
            f"✓  Auto resync on load {'enabled' if enabled else 'disabled'}.", 3000
        )

    def _sync_prompt(self, filename: str, editor: QPlainTextEdit, status: QLabel) -> None:
        default = ai_provider.default_prompt(filename)
        editor.setPlainText(default)
        ai_provider.save_prompt(filename, default)
        self._announce(status, f"✓  Prompt '{filename}' reset to default.", "✓  Synced with default")

    def _save_prompt(self, filename: str, editor: QPlainTextEdit, status: QLabel) -> None:
        ai_provider.save_prompt(filename, editor.toPlainText())
        self._announce(status, f"✓  Prompt '{filename}' saved.")
