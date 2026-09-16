from __future__ import annotations

from typing import Callable

from PyQt6.QtWidgets import QVBoxLayout, QWidget

from .tracker_page import TrackerPage


class ApplicationsPage(QWidget):
    def __init__(
        self,
        parent=None,
        get_profile: Callable[[], dict] | None = None,
        get_research_cache: Callable[[], dict] | None = None,
        save_fn: Callable[[], None] | None = None,
    ):
        super().__init__(parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._tracker_page = TrackerPage(
            get_profile=get_profile,
            get_research_cache=get_research_cache,
            save_fn=save_fn,
        )
        outer.addWidget(self._tracker_page)

    def add_entry(self, data: dict | None = None):
        self._tracker_page.add_entry(data)

    def get_data(self) -> list[dict]:
        return self._tracker_page.get_data()

    def set_interview_questions(self, row: int, value: list[dict]) -> None:
        self._tracker_page.set_interview_questions(row, value)

    def clear(self):
        self._tracker_page.clear()

    def cleanup_threads(self) -> None:
        self._tracker_page.cleanup_threads()
