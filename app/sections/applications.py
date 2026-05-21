from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout, QListWidget, QListWidgetItem, QStackedWidget, QWidget,
)

from .tracker import TrackerPage


class ApplicationsPage(QWidget):
    def __init__(
        self,
        parent=None,
        get_profile: Callable[[], dict] | None = None,
        get_research_cache: Callable[[], dict] | None = None,
        save_fn: Callable[[], None] | None = None,
    ):
        super().__init__(parent)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._sidebar = QListWidget()
        self._sidebar.setObjectName("sidebar")
        self._sidebar.setFixedWidth(200)

        item = QListWidgetItem("📋  Tracker")
        item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._sidebar.addItem(item)

        self._tracker_page = TrackerPage(
            get_profile=get_profile,
            get_research_cache=get_research_cache,
            save_fn=save_fn,
        )

        self._stack = QStackedWidget()
        self._stack.addWidget(self._tracker_page)

        self._sidebar.currentRowChanged.connect(self._stack.setCurrentIndex)
        self._sidebar.setCurrentRow(0)

        outer.addWidget(self._sidebar)
        outer.addWidget(self._stack, 1)

    def add_entry(self, data: dict | None = None):
        self._tracker_page.add_entry(data)

    def get_data(self) -> list[dict]:
        return self._tracker_page.get_data()

    def set_interview_questions(self, row: int, value: list[dict]) -> None:
        self._tracker_page.set_interview_questions(row, value)

    def clear(self):
        self._tracker_page.clear()
