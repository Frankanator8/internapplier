from __future__ import annotations

from typing import Callable

from PyQt6.QtWidgets import QComboBox

from api.applications import app_label


class JobPicker(QComboBox):
    """"Generic — no job" plus each named application; keeps its choice across refreshes."""

    def __init__(self, get_applications: Callable[[], list[dict]], parent=None):
        super().__init__(parent)
        self._get_applications = get_applications
        self.setMinimumWidth(220)

    def refresh(self) -> None:
        current = self.currentData()
        self.blockSignals(True)
        self.clear()
        self.addItem("Generic — no job", None)
        for idx, entry in enumerate(self._get_applications() or []):
            if (entry.get("company") or "").strip() or (entry.get("role") or "").strip():
                self.addItem(app_label(entry), idx)
        self.setCurrentIndex(max(self.findData(current), 0) if current is not None else 0)
        self.blockSignals(False)

    def current_entry(self) -> dict | None:
        idx = self.currentData()
        apps = self._get_applications() or []
        return apps[idx] if isinstance(idx, int) and 0 <= idx < len(apps) else None
