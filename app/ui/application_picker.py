from __future__ import annotations

import logging
from typing import Callable

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QComboBox

from api.applications import app_label

logger = logging.getLogger(__name__)


class ApplicationPicker(QComboBox):
    """"Fill from application" combo: choosing an entry emits ``picked`` and
    snaps back to the placeholder, so it acts like a menu."""

    picked = pyqtSignal(dict)

    def __init__(self, source: Callable[[], list[dict]], parent=None):
        super().__init__(parent)
        self._source = source
        self.currentIndexChanged.connect(self._on_index_changed)
        self.refresh()

    def refresh(self) -> None:
        try:
            entries = self._source() or []
        except Exception:
            logger.exception("ApplicationPicker — failed to load applications")
            entries = []
        self.blockSignals(True)
        self.clear()
        self.addItem("— Select an application —", None)
        for entry in entries:
            self.addItem(app_label(entry), entry)
        self.setCurrentIndex(0)
        self.blockSignals(False)

    def _on_index_changed(self, index: int) -> None:
        entry = self.itemData(index) if index > 0 else None
        if not isinstance(entry, dict):
            return
        self.blockSignals(True)
        self.setCurrentIndex(0)
        self.blockSignals(False)
        self.picked.emit(entry)
