from __future__ import annotations

from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLineEdit, QStatusBar, QVBoxLayout, QWidget

from api import ai_provider
from app.ui.widgets import SecretEdit, hint, hline, label, line_edit, set_status

from .common import SettingsCard, SettingsPane

# (slot, label, default, required capabilities, used for)
_MODEL_SLOTS = [
    ("basic", "Basic model", ai_provider.DEFAULT_BASIC_MODEL,
     ["Streaming", "Text generation"],
     ["Bullet analysis", "Answer questions", "Interview chat", "Interview notes"]),
    ("fast", "Fast model", ai_provider.DEFAULT_FAST_MODEL,
     ["Streaming", "JSON output"],
     ["Company research", "Interview grading", "Resume grading", "Resume PDF import"]),
    ("powerful", "Powerful model", ai_provider.DEFAULT_POWERFUL_MODEL,
     ["Streaming", "Tool / function calling", "Agentic loop (4 rounds)"],
     ["Resume generation"]),
]


def _fit_to_text(edit: QLineEdit) -> None:
    """Size a line edit to its content, within sensible bounds."""
    text_px = edit.fontMetrics().horizontalAdvance(edit.text() or edit.placeholderText())
    edit.setFixedWidth(max(120, min(text_px + 24, 400)))


def _capability_chip(text: str) -> QFrame:
    chip = QFrame()
    chip.setObjectName("capability-chip")
    chip.setFixedHeight(22)
    layout = QHBoxLayout(chip)
    layout.setContentsMargins(8, 3, 8, 3)
    layout.setSpacing(0)
    layout.addWidget(label(text, ""))
    return chip


def _labeled_row(caption: str, *widgets: QWidget) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setSpacing(6)
    row.addWidget(label(caption, "field-sublabel"))
    for w in widgets:
        row.addWidget(w)
    row.addStretch()
    return row


class AiModelSettings(SettingsPane):
    def __init__(self, status_bar: QStatusBar):
        super().__init__(status_bar)
        card = SettingsCard("AI Model Settings", max_width=560, spacing=20)
        layout = card.body

        layout.addWidget(label("OpenRouter API key"))
        self._api_key = SecretEdit(ai_provider.get_openrouter_api_key(), "sk-or-...")
        self._api_key.edit.setMinimumWidth(360)
        key_row = QHBoxLayout()
        key_row.addWidget(self._api_key)
        key_row.addStretch()
        layout.addLayout(key_row)
        layout.addWidget(hint(
            "Stored in ~/Library/Application Support/InternApplier/.env and "
            "loaded into the environment as OPENROUTER_API_KEY."
        ))

        config = ai_provider.get_model_config()
        self._model_edits: dict[str, QLineEdit] = {}
        for slot, slot_label, default, capabilities, used_for in _MODEL_SLOTS:
            layout.addWidget(hline())
            edit = self._model_edits[slot] = line_edit(default, config.get(slot, default))
            _fit_to_text(edit)
            edit.textChanged.connect(lambda _t, e=edit: _fit_to_text(e))
            layout.addWidget(self._model_section(slot_label, edit, capabilities, used_for))

        row, self._status = self._save_row(self._save)
        layout.addLayout(row)
        self._set_cards(card)

    @staticmethod
    def _model_section(slot_label: str, edit: QLineEdit, capabilities: list[str], used_for: list[str]) -> QWidget:
        container = QWidget()
        container.setObjectName("scroll-inner")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(label(slot_label))
        input_row = QHBoxLayout()
        input_row.setSpacing(0)
        input_row.addWidget(edit)
        input_row.addStretch()
        layout.addLayout(input_row)
        layout.addLayout(_labeled_row("Required:", *(_capability_chip(c) for c in capabilities)))
        layout.addLayout(_labeled_row("Used for:", label(", ".join(used_for), "hint")))
        return container

    def _save(self) -> None:
        models = [self._model_edits[slot].text().strip() for slot, *_ in _MODEL_SLOTS]
        if not all(models):
            set_status(self._status, "error", "All three models are required.")
            return
        ai_provider.save_model_config(*models)
        ai_provider.save_openrouter_api_key(self._api_key.text())
        self._announce(self._status, "✓  Model settings saved.")
