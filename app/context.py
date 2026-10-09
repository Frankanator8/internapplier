"""State and services shared between the main window's tabs."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QStatusBar

from api import research_cache


class ResearchCache(QObject):
    """Company research results, persisted in the profile as ``research_cache``.

    Shape: ``{company: {"url": str, "result": dict}}``.
    """

    changed = pyqtSignal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._data: dict[str, dict] = {}

    def load(self, data: dict | None) -> None:
        self._data = dict(data or {})
        self.changed.emit()

    def to_dict(self) -> dict:
        return dict(self._data)

    def companies(self) -> list[str]:
        return sorted(self._data, key=str.lower)

    def entry(self, company: str) -> dict | None:
        """The raw ``{url, result}`` entry for an exact company name."""
        return self._data.get(company)

    def lookup(self, company: str) -> dict | None:
        """The research result for ``company`` (case-insensitive), if cached."""
        return research_cache.lookup(self._data, company)

    def put(self, company: str, url: str, result: dict) -> None:
        research_cache.store(self._data, company, url, result)
        self.changed.emit()

    def remove(self, company: str) -> None:
        if self._data.pop(company, None) is not None:
            self.changed.emit()


@dataclass
class AppContext:
    """What a tab may ask of the rest of the app.

    Passed to every tab in place of a constructor full of callbacks.
    """

    get_profile: Callable[[], dict]
    get_applications: Callable[[], list[dict]]
    set_application_interviews: Callable[[int, list[dict]], None]
    research: ResearchCache
    save: Callable[[], None]
    status_bar: QStatusBar

    def show_status(self, message: str, ms: int = 3000) -> None:
        self.status_bar.showMessage(message, ms)
