from __future__ import annotations

from PyQt6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QTextEdit,
)

from api.leetcode_store import DEFAULT_DECK


class CardEditorDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        decks: list[str] | None = None,
        card: dict | None = None,
        default_deck: str = DEFAULT_DECK,
    ):
        super().__init__(parent)
        self.setWindowTitle("Edit card" if card else "Add card")
        self.setMinimumWidth(520)

        card = card or {}
        layout = QFormLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        self._deck = QComboBox()
        self._deck.setEditable(True)
        self._deck.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._deck.addItems(list(dict.fromkeys(name for name in decks or [] if name)))
        initial_deck = card.get("deck") or default_deck or DEFAULT_DECK
        idx = self._deck.findText(initial_deck)
        if idx >= 0:
            self._deck.setCurrentIndex(idx)
        else:
            self._deck.setEditText(initial_deck)
        layout.addRow("Deck", self._deck)

        self._front = QTextEdit()
        self._front.setPlaceholderText("Front (question). HTML is allowed.")
        self._front.setAcceptRichText(False)
        self._front.setPlainText(card.get("front") or "")
        self._front.setMinimumHeight(120)
        layout.addRow("Front", self._front)

        self._back = QTextEdit()
        self._back.setPlaceholderText("Back (answer). HTML is allowed.")
        self._back.setAcceptRichText(False)
        self._back.setPlainText(card.get("back") or "")
        self._back.setMinimumHeight(140)
        layout.addRow("Back", self._back)

        self._tags = QLineEdit()
        self._tags.setPlaceholderText("space-separated tags")
        self._tags.setText(" ".join(card.get("tags") or []))
        layout.addRow("Tags", self._tags)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        self._front.setFocus()

    def get_data(self) -> dict:
        deck = self._deck.currentText().strip() or DEFAULT_DECK
        return {
            "deck": deck,
            "front": self._front.toPlainText(),
            "back": self._back.toPlainText(),
            "tags": [t for t in self._tags.text().split() if t],
        }
