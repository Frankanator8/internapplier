from __future__ import annotations

from typing import Callable

from PyQt6.QtWidgets import QComboBox

from api import leetcode_store


class DeckCombo(QComboBox):
    """"All decks" plus one entry per deck; ``reload`` keeps the selection."""

    def __init__(
        self,
        all_label: Callable[[list[dict]], str] = lambda _decks: "All decks",
        deck_label: Callable[[dict], str] = lambda deck: deck["name"],
        parent=None,
    ):
        super().__init__(parent)
        self._all_label = all_label
        self._deck_label = deck_label

    def selected_deck(self) -> str | None:
        return self.currentData() or None

    def reload(self) -> None:
        previous = self.selected_deck()
        decks = leetcode_store.list_decks()
        self.blockSignals(True)
        self.clear()
        self.addItem(self._all_label(decks), "")
        for deck in decks:
            self.addItem(self._deck_label(deck), deck["name"])
        if previous and (idx := self.findData(previous)) >= 0:
            self.setCurrentIndex(idx)
        self.blockSignals(False)
