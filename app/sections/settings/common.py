from __future__ import annotations

from typing import Callable

from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QStatusBar, QVBoxLayout, QWidget,
)

from app.ui.widgets import button, flash_status, label, scroll_area


class SettingsCard(QFrame):
    """A titled card; add rows to ``body``."""

    def __init__(self, title: str, max_width: int | None = 800, spacing: int = 16):
        super().__init__()
        self.setObjectName("card")
        if max_width:
            self.setMaximumWidth(max_width)
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(28, 24, 28, 28)
        self.body.setSpacing(spacing)
        self.body.addWidget(label(title, "card-title"))


class SettingsPane(QWidget):
    """Base for one Settings sub-page: cards stacked in a padded scroll area."""

    def __init__(self, status_bar: QStatusBar, parent=None):
        super().__init__(parent)
        self._status_bar = status_bar

    def _set_cards(self, *cards: QWidget, spacing: int = 20) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        scroll, inner = scroll_area(margins=(40, 40, 40, 40), spacing=spacing)
        for c in cards:
            inner.addWidget(c)
        inner.addStretch()
        layout.addWidget(scroll)

    def _save_row(self, on_save: Callable[[], None], *extra: QPushButton) -> tuple[QHBoxLayout, QLabel]:
        """[Save] [extra…] status — returns the row and its status label."""
        row = QHBoxLayout()
        row.setSpacing(12)
        save_btn = button("Save", width=100)
        save_btn.clicked.connect(on_save)
        row.addWidget(save_btn)
        for b in extra:
            row.addWidget(b)
        status = label("", "status-ok")
        row.addWidget(status)
        row.addStretch()
        return row, status

    def _announce(self, status: QLabel, bar_message: str, text: str = "✓  Saved") -> None:
        flash_status(status, text)
        self._status_bar.showMessage(bar_message, 3000)
