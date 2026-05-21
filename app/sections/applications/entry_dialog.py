from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QButtonGroup, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QHBoxLayout, QLineEdit, QPushButton, QRadioButton, QTextEdit,
    QVBoxLayout, QWidget,
)

from api.constants import DEFAULT_STATUS, STATUS_OPTIONS

_STATUS_OPTIONS = STATUS_OPTIONS

_ENTRY_FIELDS = ("company", "role", "date", "status", "notes", "description")


def _empty_entry() -> dict:
    return {k: "" for k in _ENTRY_FIELDS} | {
        "status": DEFAULT_STATUS,
        "links": [],
        "interview_questions": [],
    }


class _LinksEditor(QWidget):
    def __init__(self, links: list[str], parent=None):
        super().__init__(parent)
        self._rows: list[tuple[QWidget, QRadioButton, QLineEdit]] = []
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)

        self._rows_holder = QVBoxLayout()
        self._rows_holder.setContentsMargins(0, 0, 0, 0)
        self._rows_holder.setSpacing(4)
        self._layout.addLayout(self._rows_holder)

        add_btn = QPushButton("+ Add link")
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(lambda: self._add_row("", check_primary=False))
        self._layout.addWidget(add_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        if not links:
            self._add_row("", check_primary=True)
        else:
            for i, u in enumerate(links):
                self._add_row(u, check_primary=(i == 0))

    def _add_row(self, url: str, check_primary: bool):
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)

        radio = QRadioButton()
        radio.setToolTip("Primary link")
        self._group.addButton(radio)
        edit = QLineEdit(url)
        edit.setPlaceholderText("https://…")
        remove_btn = QPushButton("✕")
        remove_btn.setFixedSize(24, 24)
        remove_btn.setToolTip("Remove link")
        remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_btn.clicked.connect(lambda _=False, w=row_widget: self._remove_row(w))

        row_layout.addWidget(radio)
        row_layout.addWidget(edit, 1)
        row_layout.addWidget(remove_btn)

        self._rows_holder.addWidget(row_widget)
        self._rows.append((row_widget, radio, edit))

        if check_primary or not any(r.isChecked() for _, r, _ in self._rows):
            radio.setChecked(True)

    def _remove_row(self, row_widget: QWidget):
        for i, (w, radio, _edit) in enumerate(self._rows):
            if w is row_widget:
                was_primary = radio.isChecked()
                self._group.removeButton(radio)
                self._rows_holder.removeWidget(w)
                w.deleteLater()
                self._rows.pop(i)
                break
        if self._rows and not any(r.isChecked() for _, r, _ in self._rows):
            self._rows[0][1].setChecked(True)

    def get_links(self) -> list[str]:
        primary: str | None = None
        others: list[str] = []
        for _w, radio, edit in self._rows:
            url = edit.text().strip()
            if not url:
                continue
            if radio.isChecked() and primary is None:
                primary = url
            else:
                others.append(url)
        result = []
        if primary is not None:
            result.append(primary)
        result.extend(others)
        return result


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
        links_value = data.get("links")
        if not isinstance(links_value, list):
            links_value = []
        self._links = _LinksEditor([u for u in links_value if isinstance(u, str)])
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
        form.addRow("Links", self._links)
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
            "links": self._links.get_links(),
            "status": self._status.currentText(),
            "notes": self._notes.text().strip(),
            "description": self._description.toPlainText().strip(),
        }
