from __future__ import annotations

import datetime

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import QDateEdit, QGridLayout, QHBoxLayout, QLabel, QStatusBar, QWidget

from api import token_usage
from app.ui.widgets import button, label

from .common import SettingsCard, SettingsPane

_TIER_LABELS = [("basic", "Basic"), ("fast", "Fast"), ("powerful", "Powerful")]
_ZERO = {"input": 0, "output": 0}


def _fmt(n: int) -> str:
    return f"{int(n):,}"


class TokenUsageSettings(SettingsPane):
    """Read-only token totals since a chosen date; refreshes whenever shown."""

    def __init__(self, status_bar: QStatusBar):
        super().__init__(status_bar)
        card = SettingsCard("Token Usage", max_width=640, spacing=18)
        layout = card.body
        layout.addWidget(label(
            "Tracks input and output tokens per model tier, per calendar day. "
            "Pick a start date (inclusive) to see totals since then.",
            wrap=True,
        ))

        controls = QHBoxLayout()
        controls.setSpacing(10)
        controls.addWidget(label("Show usage since (inclusive):"))
        self._date_edit = QDateEdit()
        self._date_edit.setCalendarPopup(True)
        self._date_edit.setDisplayFormat("yyyy-MM-dd")
        self._date_edit.setDate(QDate.currentDate())
        self._date_edit.dateChanged.connect(lambda _d: self.on_shown())
        controls.addWidget(self._date_edit)
        refresh_btn = button("Refresh", width=100)
        refresh_btn.clicked.connect(self.on_shown)
        controls.addWidget(refresh_btn)
        controls.addStretch()
        layout.addLayout(controls)

        self._total = label("", "group-subtitle")
        layout.addWidget(self._total)

        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(28)
        grid.setVerticalSpacing(6)
        for col, text in enumerate(("Tier", "Input", "Output")):
            grid.addWidget(label(text), 0, col)

        self._rows: dict[str, tuple[QLabel, QLabel]] = {}
        right = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        for row_idx, (tier, tier_label) in enumerate(_TIER_LABELS, start=1):
            inp, out = label("0", ""), label("0", "")
            inp.setAlignment(right)
            out.setAlignment(right)
            grid.addWidget(label(tier_label, ""), row_idx, 0)
            grid.addWidget(inp, row_idx, 1)
            grid.addWidget(out, row_idx, 2)
            self._rows[tier] = (inp, out)
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)
        layout.addWidget(grid_host)

        self._empty = label("No usage recorded since this date.")
        self._empty.setVisible(False)
        layout.addWidget(self._empty)

        self._set_cards(card)
        self.on_shown()

    def on_shown(self) -> None:
        qd = self._date_edit.date()
        try:
            totals = token_usage.usage_since(datetime.date(qd.year(), qd.month(), qd.day()))
        except Exception:
            totals = {}

        grand = totals.get("__total__") or _ZERO
        self._total.setText(
            f"Total: {_fmt(grand.get('input', 0))} input / "
            f"{_fmt(grand.get('output', 0))} output tokens"
        )
        for tier, (inp, out) in self._rows.items():
            entry = totals.get(tier) or _ZERO
            inp.setText(_fmt(entry.get("input", 0)))
            out.setText(_fmt(entry.get("output", 0)))
        self._empty.setVisible(not grand.get("input", 0) and not grand.get("output", 0))
