from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem,
)
from .base import _label, _primary_btn, _icon_btn


class HobbiesPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 16)
        layout.setSpacing(14)

        header_row = QHBoxLayout()
        header_row.addWidget(_label("Hobbies", "section-title"))
        header_row.addStretch()
        layout.addLayout(header_row)

        add_row = QHBoxLayout()
        add_row.setSpacing(10)
        self._input = QLineEdit()
        self._input.setPlaceholderText("Type a hobby and press Enter or click Add…")
        self._input.returnPressed.connect(self._add_hobby)
        add_btn = _primary_btn("+ Add Hobby", 110)
        add_btn.clicked.connect(self._add_hobby)
        add_row.addWidget(self._input)
        add_row.addWidget(add_btn)
        layout.addLayout(add_row)

        self._list = QListWidget()
        self._list.setObjectName("skills-list")
        self._list.setSpacing(2)
        layout.addWidget(self._list)

    def _add_hobby(self):
        text = self._input.text().strip()
        if not text:
            return
        self._add_item(text)
        self._input.clear()

    def _add_item(self, text: str):
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(8, 4, 6, 4)
        row_layout.setSpacing(8)

        label = QLabel(text)
        label.setStyleSheet("font-size: 13px; color: #1d1d1d;")
        remove_btn = _icon_btn("✕")

        row_layout.addWidget(label)
        row_layout.addStretch()
        row_layout.addWidget(remove_btn)

        item = QListWidgetItem()
        item.setSizeHint(row.sizeHint())
        self._list.addItem(item)
        self._list.setItemWidget(item, row)

        remove_btn.clicked.connect(lambda: self._list.takeItem(self._list.row(item)))

    def load(self, hobbies: list[str]):
        self._list.clear()
        for h in hobbies:
            self._add_item(h)

    def get_data(self) -> list[str]:
        result = []
        for i in range(self._list.count()):
            item = self._list.item(i)
            widget = self._list.itemWidget(item)
            label = widget.findChild(QLabel)
            if label:
                result.append(label.text())
        return result
