from __future__ import annotations

from datetime import date, timedelta

from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QWidget


_COLUMNS = 7
_ROWS = 2  # row 0 = weeks, row 1 = days
_CELL = 12
_GAP = 3

_PALETTE = [
    QColor("#ebedf0"),
    QColor("#cfe2f3"),
    QColor("#7fb3e6"),
    QColor("#3d85c6"),
    QColor("#0a66c2"),
]


def _bucket_day(count: int) -> int:
    if count <= 0:
        return 0
    if count == 1:
        return 1
    if count == 2:
        return 2
    if count == 3:
        return 3
    return 4


def _bucket_week(count: int) -> int:
    if count <= 0:
        return 0
    if count <= 2:
        return 1
    if count <= 5:
        return 2
    if count <= 9:
        return 3
    return 4


class ApplicationsHeatmap(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._counts: dict[date, int] = {}
        width = _COLUMNS * _CELL + (_COLUMNS - 1) * _GAP
        height = _ROWS * _CELL + (_ROWS - 1) * _GAP
        self.setFixedSize(width, height)
        self.setMouseTracking(True)
        self.setToolTip("Applications — last 7 weeks (top) and last 7 days (bottom)")

    def set_applications(self, apps: list[dict]) -> None:
        counts: dict[date, int] = {}
        for app in apps or []:
            raw = (app.get("date") or "").strip()
            if not raw:
                continue
            try:
                d = date.fromisoformat(raw)
            except ValueError:
                continue
            counts[d] = counts.get(d, 0) + 1
        self._counts = counts
        self.update()

    def _day_for_col(self, col: int) -> date:
        # bottom row: rightmost cell = today, leftward = older
        return date.today() - timedelta(days=(_COLUMNS - 1 - col))

    def _week_range_for_col(self, col: int) -> tuple[date, date]:
        # top row: rightmost cell = the 7 days immediately before the days row
        # i.e. days [today-7 .. today-13]; older to the left
        offset_weeks = (_COLUMNS - 1 - col)
        end = date.today() - timedelta(days=7 + offset_weeks * 7)
        start = end - timedelta(days=6)
        return start, end

    def _week_count(self, start: date, end: date) -> int:
        total = 0
        d = start
        while d <= end:
            total += self._counts.get(d, 0)
            d += timedelta(days=1)
        return total

    def _cell_rect(self, col: int, row: int) -> QRect:
        x = col * (_CELL + _GAP)
        y = row * (_CELL + _GAP)
        return QRect(x, y, _CELL, _CELL)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setPen(Qt.PenStyle.NoPen)
        for col in range(_COLUMNS):
            start, end = self._week_range_for_col(col)
            week_count = self._week_count(start, end)
            painter.setBrush(_PALETTE[_bucket_week(week_count)])
            painter.drawRect(self._cell_rect(col, 0))

            day = self._day_for_col(col)
            day_count = self._counts.get(day, 0)
            painter.setBrush(_PALETTE[_bucket_day(day_count)])
            painter.drawRect(self._cell_rect(col, 1))
        painter.end()

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        col = pos.x() // (_CELL + _GAP)
        row = pos.y() // (_CELL + _GAP)
        if 0 <= col < _COLUMNS and 0 <= row < _ROWS and self._cell_rect(col, row).contains(pos):
            if row == 1:
                d = self._day_for_col(col)
                count = self._counts.get(d, 0)
                noun = "application" if count == 1 else "applications"
                self.setToolTip(f"{d.isoformat()} — {count} {noun}")
            else:
                start, end = self._week_range_for_col(col)
                count = self._week_count(start, end)
                noun = "application" if count == 1 else "applications"
                self.setToolTip(
                    f"Week {start.isoformat()} → {end.isoformat()} — {count} {noun}"
                )
            return
        self.setToolTip("Applications — last 7 weeks (top) and last 7 days (bottom)")
