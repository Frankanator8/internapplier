from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QComboBox, QPushButton, QLabel, QHeaderView, QAbstractItemView,
)
from PyQt6.QtCore import Qt

from .base import _label, _primary_btn

_STATUS_OPTIONS = ["Applied", "Phone Screen", "Interview", "Offer", "Rejected"]

_COLUMNS = ["Company", "Role", "Date Applied", "Status", "Notes", ""]
_COL_COMPANY, _COL_ROLE, _COL_DATE, _COL_STATUS, _COL_NOTES, _COL_DEL = range(6)


class TrackerPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 16)
        outer.setSpacing(14)

        header_row = QHBoxLayout()
        header_row.addWidget(_label("Application Tracker", "section-title"))
        header_row.addStretch()
        add_btn = _primary_btn("+ Add Application")
        add_btn.clicked.connect(lambda: self.add_entry())
        header_row.addWidget(add_btn)
        outer.addLayout(header_row)

        self._table = QTableWidget(0, len(_COLUMNS))
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.SelectedClicked)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(True)
        self._table.setWordWrap(False)

        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(_COL_COMPANY, QHeaderView.ResizeMode.Interactive)
        hdr.setSectionResizeMode(_COL_ROLE, QHeaderView.ResizeMode.Interactive)
        hdr.setSectionResizeMode(_COL_DATE, QHeaderView.ResizeMode.Interactive)
        hdr.setSectionResizeMode(_COL_STATUS, QHeaderView.ResizeMode.Interactive)
        hdr.setSectionResizeMode(_COL_NOTES, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(_COL_DEL, QHeaderView.ResizeMode.Fixed)

        self._table.setColumnWidth(_COL_COMPANY, 160)
        self._table.setColumnWidth(_COL_ROLE, 160)
        self._table.setColumnWidth(_COL_DATE, 110)
        self._table.setColumnWidth(_COL_STATUS, 120)
        self._table.setColumnWidth(_COL_DEL, 40)

        outer.addWidget(self._table)

    def add_entry(self, data: dict | None = None):
        data = data or {}
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setRowHeight(row, 34)

        self._table.setItem(row, _COL_COMPANY, QTableWidgetItem(data.get("company", "")))
        self._table.setItem(row, _COL_ROLE, QTableWidgetItem(data.get("role", "")))
        self._table.setItem(row, _COL_DATE, QTableWidgetItem(data.get("date", "")))

        combo = QComboBox()
        combo.setObjectName("status-combo")
        for s in _STATUS_OPTIONS:
            combo.addItem(s)
        current = data.get("status", "Applied")
        if current in _STATUS_OPTIONS:
            combo.setCurrentText(current)
        self._table.setCellWidget(row, _COL_STATUS, combo)

        self._table.setItem(row, _COL_NOTES, QTableWidgetItem(data.get("notes", "")))

        del_btn = QPushButton("✕")
        del_btn.setObjectName("icon-btn")
        del_btn.setFixedSize(28, 28)
        del_btn.clicked.connect(lambda: self._remove_row(del_btn))

        cell_widget = QWidget()
        cell_layout = QHBoxLayout(cell_widget)
        cell_layout.setContentsMargins(4, 0, 4, 0)
        cell_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cell_layout.addWidget(del_btn)
        self._table.setCellWidget(row, _COL_DEL, cell_widget)

    def _remove_row(self, btn: QPushButton):
        for r in range(self._table.rowCount()):
            w = self._table.cellWidget(r, _COL_DEL)
            if w and w.findChild(QPushButton) is btn:
                self._table.removeRow(r)
                return

    def get_data(self) -> list[dict]:
        result = []
        for r in range(self._table.rowCount()):
            company_item = self._table.item(r, _COL_COMPANY)
            role_item = self._table.item(r, _COL_ROLE)
            date_item = self._table.item(r, _COL_DATE)
            notes_item = self._table.item(r, _COL_NOTES)
            combo = self._table.cellWidget(r, _COL_STATUS)
            result.append({
                "company": company_item.text() if company_item else "",
                "role": role_item.text() if role_item else "",
                "date": date_item.text() if date_item else "",
                "status": combo.currentText() if combo else "Applied",
                "notes": notes_item.text() if notes_item else "",
            })
        return result

    def clear(self):
        self._table.setRowCount(0)
