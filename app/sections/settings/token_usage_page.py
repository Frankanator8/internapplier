from __future__ import annotations

import datetime

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import (
    QDateEdit, QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget,
)

from api import token_usage

from ..base import _primary_btn


_TIER_LABELS = [("basic", "Basic"), ("fast", "Fast"), ("powerful", "Powerful")]


def _fmt(n: int) -> str:
    return f"{int(n):,}"


class TokenUsageMixin:
    def _build_token_usage_page(self) -> QWidget:
        card = QFrame()
        card.setObjectName("card")
        card.setMaximumWidth(640)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 24, 28, 28)
        card_layout.setSpacing(18)

        title = QLabel("Token Usage")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #0a66c2;")
        card_layout.addWidget(title)

        hint = QLabel(
            "Tracks input and output tokens per model tier, per calendar day. "
            "Pick a start date (inclusive) to see totals since then."
        )
        hint.setWordWrap(True)
        hint.setObjectName("field-label")
        card_layout.addWidget(hint)

        controls = QHBoxLayout()
        controls.setSpacing(10)
        date_label = QLabel("Show usage since (inclusive):")
        date_label.setObjectName("field-label")
        controls.addWidget(date_label)

        self._token_usage_date_edit = QDateEdit()
        self._token_usage_date_edit.setCalendarPopup(True)
        self._token_usage_date_edit.setDisplayFormat("yyyy-MM-dd")
        self._token_usage_date_edit.setDate(QDate.currentDate())
        self._token_usage_date_edit.dateChanged.connect(lambda _d: self._refresh_token_usage())
        controls.addWidget(self._token_usage_date_edit)

        refresh_btn = _primary_btn("Refresh", width=100)
        refresh_btn.clicked.connect(self._refresh_token_usage)
        controls.addWidget(refresh_btn)
        controls.addStretch()
        card_layout.addLayout(controls)

        self._token_usage_total = QLabel("")
        self._token_usage_total.setStyleSheet("font-size: 14px; font-weight: 600;")
        card_layout.addWidget(self._token_usage_total)

        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(28)
        grid.setVerticalSpacing(6)

        for col, text in enumerate(("Tier", "Input", "Output")):
            h = QLabel(text)
            h.setObjectName("field-label")
            grid.addWidget(h, 0, col)

        self._token_usage_rows: dict[str, tuple[QLabel, QLabel]] = {}
        for row_idx, (tier, label) in enumerate(_TIER_LABELS, start=1):
            name = QLabel(label)
            name.setStyleSheet("font-size: 13px;")
            inp = QLabel("0")
            inp.setStyleSheet("font-size: 13px;")
            inp.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            out = QLabel("0")
            out.setStyleSheet("font-size: 13px;")
            out.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            grid.addWidget(name, row_idx, 0)
            grid.addWidget(inp, row_idx, 1)
            grid.addWidget(out, row_idx, 2)
            self._token_usage_rows[tier] = (inp, out)

        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)
        card_layout.addWidget(grid_host)

        self._token_usage_empty = QLabel("No usage recorded since this date.")
        self._token_usage_empty.setObjectName("field-label")
        self._token_usage_empty.setVisible(False)
        card_layout.addWidget(self._token_usage_empty)

        self._refresh_token_usage()
        return self._wrap_scroll(card)

    def _refresh_token_usage(self) -> None:
        qd = self._token_usage_date_edit.date()
        start = datetime.date(qd.year(), qd.month(), qd.day())
        try:
            totals = token_usage.usage_since(start)
        except Exception:
            totals = {"__total__": {"input": 0, "output": 0}}

        grand = totals.get("__total__", {"input": 0, "output": 0})
        self._token_usage_total.setText(
            f"Total: {_fmt(grand.get('input', 0))} input / "
            f"{_fmt(grand.get('output', 0))} output tokens"
        )

        for tier, (inp_label, out_label) in self._token_usage_rows.items():
            entry = totals.get(tier) or {"input": 0, "output": 0}
            inp_label.setText(_fmt(entry.get("input", 0)))
            out_label.setText(_fmt(entry.get("output", 0)))

        empty = (grand.get("input", 0) == 0 and grand.get("output", 0) == 0)
        self._token_usage_empty.setVisible(empty)
