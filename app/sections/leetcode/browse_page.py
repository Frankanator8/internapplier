from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QAbstractItemView, QFileDialog, QHBoxLayout, QHeaderView, QMessageBox,
    QTableWidget, QTableWidgetItem, QWidget,
)

from api import anki_import, leetcode_store
from app.ui.widgets import button, confirm, label, line_edit, page_layout, section_header

from .card_dialog import CardEditorDialog
from .deck_combo import DeckCombo

_COLUMNS = ["Deck", "Front", "Due", "Tags"]
_COL_DECK, _COL_FRONT, _COL_DUE, _COL_TAGS = range(4)


def _plural(n: int, noun: str) -> str:
    return f"{n} {noun}" + ("" if n == 1 else "s")


class BrowsePage(QWidget):
    """Table of all flashcards: filter by deck or text, add, edit, delete, import."""

    cards_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[dict] = []

        outer = page_layout(self)
        self._count = label("", "muted")
        outer.addLayout(section_header("Browse", self._count))

        toolbar = QHBoxLayout()
        self._deck_filter = DeckCombo()
        self._deck_filter.setMinimumWidth(200)
        self._deck_filter.currentIndexChanged.connect(self._reload_table)
        toolbar.addWidget(self._deck_filter)

        self._search = line_edit("Search cards…")
        self._search.setFixedWidth(240)
        self._search.textChanged.connect(self._apply_filter)
        toolbar.addWidget(self._search)
        toolbar.addStretch()

        import_btn = button("Import Anki deck", "secondary", 150)
        import_btn.clicked.connect(self._on_import)
        toolbar.addWidget(import_btn)

        add_btn = button("+ Add card")
        add_btn.clicked.connect(self._on_add)
        toolbar.addWidget(add_btn)

        self._edit_btn = button("Edit", "secondary", 80)
        self._edit_btn.clicked.connect(self._on_edit)
        toolbar.addWidget(self._edit_btn)

        self._delete_btn = button("Delete", "danger", 90)
        self._delete_btn.clicked.connect(self._on_delete)
        toolbar.addWidget(self._delete_btn)
        outer.addLayout(toolbar)

        self._table = QTableWidget(0, len(_COLUMNS))
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(True)
        self._table.setWordWrap(False)
        self._table.doubleClicked.connect(lambda _idx: self._on_edit())
        self._table.itemSelectionChanged.connect(self._on_selection_changed)

        hdr = self._table.horizontalHeader()
        for col, width in ((_COL_DECK, 180), (_COL_DUE, 110), (_COL_TAGS, 160)):
            hdr.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
            self._table.setColumnWidth(col, width)
        hdr.setSectionResizeMode(_COL_FRONT, QHeaderView.ResizeMode.Stretch)
        outer.addWidget(self._table)

        for key in (QKeySequence(QKeySequence.StandardKey.Delete), QKeySequence(Qt.Key.Key_Backspace)):
            shortcut = QShortcut(key, self._table)
            shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
            shortcut.activated.connect(self._on_delete)

        self._on_selection_changed()
        self.refresh()

    def refresh(self) -> None:
        self._deck_filter.reload()
        self._reload_table()

    on_shown = refresh

    def _deck_names(self) -> list[str]:
        return [d["name"] for d in leetcode_store.list_decks()]

    def _reload_table(self) -> None:
        self._rows = leetcode_store.list_cards(self._deck_filter.selected_deck())
        self._table.setRowCount(0)
        for card in self._rows:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setRowHeight(row, 34)
            deck_item = QTableWidgetItem(card["deck"])
            deck_item.setData(Qt.ItemDataRole.UserRole, card["id"])
            self._table.setItem(row, _COL_DECK, deck_item)
            self._table.setItem(
                row, _COL_FRONT, QTableWidgetItem(leetcode_store.plain_preview(card["front"]))
            )
            self._table.setItem(row, _COL_DUE, QTableWidgetItem(card["due"]))
            self._table.setItem(row, _COL_TAGS, QTableWidgetItem(" ".join(card.get("tags") or [])))
        self._apply_filter(self._search.text())
        self._on_selection_changed()

    def _apply_filter(self, text: str) -> None:
        query = (text or "").strip().lower()
        visible = 0
        for row, card in enumerate(self._rows):
            if not query:
                hidden = False
            else:
                haystack = " ".join([
                    card.get("deck") or "",
                    leetcode_store.plain_preview(card.get("front") or "", 400),
                    leetcode_store.plain_preview(card.get("back") or "", 400),
                    " ".join(card.get("tags") or []),
                ]).lower()
                hidden = query not in haystack
            self._table.setRowHidden(row, hidden)
            if not hidden:
                visible += 1
        self._count.setText(_plural(visible, "card"))

    def _selected_ids(self) -> list[str]:
        ids: list[str] = []
        for idx in self._table.selectionModel().selectedRows():
            item = self._table.item(idx.row(), _COL_DECK)
            if item is None:
                continue
            card_id = item.data(Qt.ItemDataRole.UserRole)
            if card_id:
                ids.append(card_id)
        return ids

    def _on_selection_changed(self) -> None:
        n = len(self._selected_ids())
        self._edit_btn.setEnabled(n == 1)
        self._delete_btn.setEnabled(n >= 1)

    def _on_add(self) -> None:
        dlg = CardEditorDialog(
            self,
            decks=self._deck_names(),
            default_deck=self._deck_filter.selected_deck() or leetcode_store.DEFAULT_DECK,
        )
        if dlg.exec() != dlg.DialogCode.Accepted:
            return
        data = dlg.get_data()
        if not data["front"].strip() and not data["back"].strip():
            QMessageBox.information(self, "Empty card", "Enter a front or back before saving.")
            return
        leetcode_store.add_card(data["front"], data["back"], data["deck"], data["tags"])
        self._after_change()

    def _on_edit(self) -> None:
        ids = self._selected_ids()
        if len(ids) != 1:
            return
        card = leetcode_store.get_card(ids[0])
        if card is None:
            return
        dlg = CardEditorDialog(self, decks=self._deck_names(), card=card)
        if dlg.exec() != dlg.DialogCode.Accepted:
            return
        data = dlg.get_data()
        leetcode_store.update_card(card["id"], **data)
        self._after_change()

    def _on_delete(self) -> None:
        ids = self._selected_ids()
        if not ids:
            return
        if not confirm(self, "Delete cards", f"Delete {_plural(len(ids), 'card')}? This cannot be undone."):
            return
        leetcode_store.delete_cards(ids)
        self._after_change()

    def _on_import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Anki deck",
            "",
            "Anki decks (*.apkg *.txt *.tsv *.csv);;Anki package (*.apkg);;Text export (*.txt *.tsv *.csv)",
        )
        if not path:
            return
        default_deck = self._deck_filter.selected_deck() or Path(path).stem or "Imported"
        try:
            imported = anki_import.import_anki_file(path, leetcode_store.media_dir(), default_deck=default_deck)
        except Exception as exc:
            message = str(exc) if isinstance(exc, anki_import.AnkiImportError) else f"Could not import that file:\n{exc}"
            QMessageBox.critical(self, "Import failed", message)
            return
        created = leetcode_store.add_cards(imported)
        decks = sorted({c["deck"] for c in created})
        deck_note = f" into {', '.join(decks)}" if decks else ""
        QMessageBox.information(
            self,
            "Import complete",
            f"Imported {_plural(len(created), 'card')}{deck_note}.",
        )
        self._after_change()

    def _after_change(self) -> None:
        self.refresh()
        self.cards_changed.emit()
