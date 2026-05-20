from __future__ import annotations

import html

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QComboBox, QPushButton, QLabel, QHeaderView, QAbstractItemView,
    QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QTextEdit,
)
from PyQt6.QtCore import Qt

from .base import _label, _primary_btn

_STATUS_OPTIONS = ["Applied", "Phone Screen", "Interview", "Offer", "Rejected"]

_COLUMNS = ["Company", "Role", "Date Applied", "Status", "Notes", ""]
_COL_COMPANY, _COL_ROLE, _COL_DATE, _COL_STATUS, _COL_NOTES, _COL_DEL = range(6)

_ENTRY_FIELDS = ("company", "role", "date", "link", "status", "notes", "description")


def _empty_entry() -> dict:
    return {k: "" for k in _ENTRY_FIELDS} | {"status": "Applied"}


class _EntryDialog(QDialog):
    def __init__(self, parent=None, data: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle("Application")
        self.setMinimumWidth(520)

        data = {**_empty_entry(), **(data or {})}

        form = QFormLayout()
        self._company = QLineEdit(data["company"])
        self._role = QLineEdit(data["role"])
        self._date = QLineEdit(data["date"])
        self._link = QLineEdit(data["link"])
        self._status = QComboBox()
        for s in _STATUS_OPTIONS:
            self._status.addItem(s)
        if data["status"] in _STATUS_OPTIONS:
            self._status.setCurrentText(data["status"])
        self._notes = QLineEdit(data["notes"])
        self._description = QTextEdit()
        self._description.setPlainText(data["description"])
        self._description.setMinimumHeight(160)

        form.addRow("Company", self._company)
        form.addRow("Role", self._role)
        form.addRow("Date Applied", self._date)
        form.addRow("Link", self._link)
        form.addRow("Status", self._status)
        form.addRow("Notes", self._notes)
        form.addRow("Job Description", self._description)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def get_data(self) -> dict:
        return {
            "company": self._company.text().strip(),
            "role": self._role.text().strip(),
            "date": self._date.text().strip(),
            "link": self._link.text().strip(),
            "status": self._status.currentText(),
            "notes": self._notes.text().strip(),
            "description": self._description.toPlainText().strip(),
        }


class TrackerPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[dict] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 16)
        outer.setSpacing(14)

        header_row = QHBoxLayout()
        header_row.addWidget(_label("Application Tracker", "section-title"))
        header_row.addStretch()
        add_btn = _primary_btn("+ Add Application")
        add_btn.clicked.connect(self._on_add_clicked)
        header_row.addWidget(add_btn)
        outer.addLayout(header_row)

        self._table = QTableWidget(0, len(_COLUMNS))
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(True)
        self._table.setWordWrap(False)
        self._table.cellClicked.connect(self._on_cell_clicked)

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

    def _on_add_clicked(self):
        dlg = _EntryDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.add_entry(dlg.get_data())

    def add_entry(self, data: dict | None = None):
        entry = {**_empty_entry(), **(data or {})}
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setRowHeight(row, 34)
        self._rows.append(entry)

        self._refresh_row(row)

    def _refresh_row(self, row: int):
        entry = self._rows[row]

        self._table.setItem(row, _COL_COMPANY, QTableWidgetItem(entry["company"]))
        self._render_role_cell(row, entry["role"], entry["link"])
        self._table.setItem(row, _COL_DATE, QTableWidgetItem(entry["date"]))
        self._table.setItem(row, _COL_NOTES, QTableWidgetItem(entry["notes"]))

        existing_combo = self._table.cellWidget(row, _COL_STATUS)
        if isinstance(existing_combo, QComboBox):
            if entry["status"] in _STATUS_OPTIONS:
                existing_combo.setCurrentText(entry["status"])
        else:
            combo = QComboBox()
            combo.setObjectName("status-combo")
            for s in _STATUS_OPTIONS:
                combo.addItem(s)
            if entry["status"] in _STATUS_OPTIONS:
                combo.setCurrentText(entry["status"])
            combo.currentTextChanged.connect(lambda txt, r=row: self._on_status_changed(r, txt))
            self._table.setCellWidget(row, _COL_STATUS, combo)

        if self._table.cellWidget(row, _COL_DEL) is None:
            del_btn = QPushButton("✕")
            del_btn.setObjectName("icon-btn")
            del_btn.setFixedSize(28, 28)
            del_btn.clicked.connect(lambda _checked=False, b=del_btn: self._remove_row(b))

            cell_widget = QWidget()
            cell_layout = QHBoxLayout(cell_widget)
            cell_layout.setContentsMargins(4, 0, 4, 0)
            cell_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cell_layout.addWidget(del_btn)
            self._table.setCellWidget(row, _COL_DEL, cell_widget)

    def _render_role_cell(self, row: int, role: str, link: str):
        if link:
            label = QLabel(f'<a href="{html.escape(link, quote=True)}">{html.escape(role)}</a>')
            label.setOpenExternalLinks(True)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
            label.setContentsMargins(6, 0, 6, 0)
            self._table.setItem(row, _COL_ROLE, QTableWidgetItem())
            self._table.setCellWidget(row, _COL_ROLE, label)
        else:
            self._table.removeCellWidget(row, _COL_ROLE)
            self._table.setItem(row, _COL_ROLE, QTableWidgetItem(role))

    def _on_status_changed(self, row: int, text: str):
        if 0 <= row < len(self._rows):
            self._rows[row]["status"] = text

    def _on_cell_clicked(self, row: int, col: int):
        if col in (_COL_STATUS, _COL_DEL):
            return
        if not (0 <= row < len(self._rows)):
            return
        dlg = _EntryDialog(self, self._rows[row])
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._rows[row] = dlg.get_data()
            self._refresh_row(row)

    def _remove_row(self, btn: QPushButton):
        for r in range(self._table.rowCount()):
            w = self._table.cellWidget(r, _COL_DEL)
            if w and w.findChild(QPushButton) is btn:
                self._table.removeRow(r)
                del self._rows[r]
                self._rebind_row_callbacks()
                return

    def _rebind_row_callbacks(self):
        for r in range(self._table.rowCount()):
            combo = self._table.cellWidget(r, _COL_STATUS)
            if isinstance(combo, QComboBox):
                try:
                    combo.currentTextChanged.disconnect()
                except TypeError:
                    pass
                combo.currentTextChanged.connect(lambda txt, row=r: self._on_status_changed(row, txt))

    def get_data(self) -> list[dict]:
        return [dict(entry) for entry in self._rows]

    def clear(self):
        self._table.setRowCount(0)
        self._rows.clear()
