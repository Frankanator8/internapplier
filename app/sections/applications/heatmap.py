from __future__ import annotations

from bisect import bisect_right
from datetime import date, timedelta

from PyQt6.QtCore import QEvent, QRect, Qt
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QWidget

from api import app_settings
from app.theme import current_palette


_COLUMNS = 7
_ROWS = 2  # row 0 = weeks, row 1 = days
_CELL = 12
_GAP = 3


def _heatmap_colors() -> list[QColor]:
    p = current_palette()
    return [
        QColor(p["heatmap_0"]),
        QColor(p["heatmap_1"]),
        QColor(p["heatmap_2"]),
        QColor(p["heatmap_3"]),
        QColor(p["heatmap_4"]),
    ]


def _bucket(count: int, edges: list[int]) -> int:
    if count <= 0:
        return 0
    return min(bisect_right(edges, count), 4)


class ApplicationsHeatmap(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._counts: dict[date, int] = {}
        self._day_edges = app_settings.get_heatmap_day_thresholds()
        self._week_edges = app_settings.get_heatmap_week_thresholds()
        width = _COLUMNS * _CELL + (_COLUMNS - 1) * _GAP
        height = _ROWS * _CELL + (_ROWS - 1) * _GAP
        self.setFixedSize(width, height)
        self.setMouseTracking(True)
        self.setToolTip("Applications — last 7 weeks (top) and last 7 days (bottom)")

    def reload_thresholds(self) -> None:
        self._day_edges = app_settings.get_heatmap_day_thresholds()
        self._week_edges = app_settings.get_heatmap_week_thresholds()
        self.update()

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
            colors = _heatmap_colors()
            painter.setBrush(colors[_bucket(week_count, self._week_edges)])
            painter.drawRect(self._cell_rect(col, 0))

            day = self._day_for_col(col)
            day_count = self._counts.get(day, 0)
            painter.setBrush(colors[_bucket(day_count, self._day_edges)])
            painter.drawRect(self._cell_rect(col, 1))
        painter.end()

    def changeEvent(self, event):
        if event.type() in (QEvent.Type.StyleChange, QEvent.Type.PaletteChange):
            self.update()
        super().changeEvent(event)

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
