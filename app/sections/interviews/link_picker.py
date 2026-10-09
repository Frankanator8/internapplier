from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QListWidget, QListWidgetItem, QVBoxLayout

from app.ui.widgets import label, line_edit


class LinkPickerDialog(QDialog):
    """Pick another question to link with. Candidates are (text, group label)."""

    def __init__(self, candidates: list[tuple[str, str | None]], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Link to question")
        self.setMinimumWidth(420)
        self._candidates = candidates
        self._selected_index: int | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        layout.addWidget(label("Select a question to link with:", ""))

        search = line_edit("Search…")
        search.textChanged.connect(self._populate)
        layout.addWidget(search)

        self._list = QListWidget()
        self._list.itemDoubleClicked.connect(lambda _i: self._accept())
        layout.addWidget(self._list, 1)
        self._populate("")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate(self, query: str) -> None:
        self._list.clear()
        q = query.strip().lower()
        for idx, (text, group_label) in enumerate(self._candidates):
            if q and q not in text.lower():
                continue
            display = text or "(empty question)"
            if group_label:
                display = f"{display}   · {group_label}"
            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, idx)
            self._list.addItem(item)

    def _accept(self) -> None:
        item = self._list.currentItem()
        if item is not None:
            self._selected_index = item.data(Qt.ItemDataRole.UserRole)
            self.accept()

    def selected_index(self) -> int | None:
        return self._selected_index
