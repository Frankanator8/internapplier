from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QListWidget, QListWidgetItem, QWidget

from app.ui.widgets import button, icon_button, label, line_edit, page_layout, section_header


class StringListPage(QWidget):
    """Editor for a flat list of short strings (skills, hobbies)."""

    def __init__(self, title: str, noun: str, parent=None):
        super().__init__(parent)
        layout = page_layout(self)
        layout.addLayout(section_header(title))

        add_row = QHBoxLayout()
        add_row.setSpacing(10)
        self._input = line_edit(f"Type a {noun} and press Enter or click Add…")
        self._input.returnPressed.connect(self._add_from_input)
        add_btn = button(f"+ Add {noun.capitalize()}", width=110)
        add_btn.clicked.connect(self._add_from_input)
        add_row.addWidget(self._input)
        add_row.addWidget(add_btn)
        layout.addLayout(add_row)

        self._list = QListWidget()
        self._list.setObjectName("skills-list")
        self._list.setSpacing(2)
        layout.addWidget(self._list)

    def _add_from_input(self) -> None:
        text = self._input.text().strip()
        if text:
            self.add_item(text)
            self._input.clear()

    def add_item(self, text: str) -> None:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(8, 4, 6, 4)
        row_layout.setSpacing(8)
        remove_btn = icon_button()
        row_layout.addWidget(label(text, ""))
        row_layout.addStretch()
        row_layout.addWidget(remove_btn)

        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, text)
        item.setSizeHint(row.sizeHint())
        self._list.addItem(item)
        self._list.setItemWidget(item, row)
        remove_btn.clicked.connect(lambda: self._list.takeItem(self._list.row(item)))

    def add_unique(self, text: str) -> None:
        """Add ``text`` unless it's already listed (case-insensitive)."""
        if text.lower() not in {s.lower() for s in self.get_data()}:
            self.add_item(text)

    # ── Profile section interface ───────────────────────────────
    def load(self, items: list[str] | None) -> None:
        self._list.clear()
        for s in items or []:
            self.add_item(s)

    def merge(self, items: list[str] | None, mode: str) -> None:
        if mode == "replace":
            self.load(items)
            return
        # Dedupe case-insensitively, matching api.profile_merge.
        for item in items or []:
            self.add_unique(item)

    def clear(self) -> None:
        self._list.clear()

    def has_data(self) -> bool:
        return self._list.count() > 0

    def get_data(self) -> list[str]:
        return [self._list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self._list.count())]
