from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QStackedWidget,
    QVBoxLayout, QWidget,
)

from .base import _label
from .tracker import TrackerPage


class ApplicationsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._sidebar = QListWidget()
        self._sidebar.setObjectName("sidebar")
        self._sidebar.setFixedWidth(200)

        for label in ("📋  Tracker", "🔍  Find Internships"):
            item = QListWidgetItem(label)
            item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            self._sidebar.addItem(item)

        self._tracker_page = TrackerPage()

        self._stack = QStackedWidget()
        self._stack.addWidget(self._tracker_page)
        self._stack.addWidget(self._build_find_page())

        self._sidebar.currentRowChanged.connect(self._stack.setCurrentIndex)
        self._sidebar.setCurrentRow(0)

        outer.addWidget(self._sidebar)
        outer.addWidget(self._stack, 1)

    def _build_find_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 16)
        layout.setSpacing(14)
        layout.addWidget(_label("Find Internships", "section-title"))
        coming = QLabel("Coming soon — discover internships to apply to.")
        coming.setStyleSheet("color: #666;")
        layout.addWidget(coming)
        layout.addStretch()
        return page

    def add_entry(self, data: dict | None = None):
        self._tracker_page.add_entry(data)

    def get_data(self) -> list[dict]:
        return self._tracker_page.get_data()

    def clear(self):
        self._tracker_page.clear()
