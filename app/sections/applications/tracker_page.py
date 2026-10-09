from __future__ import annotations

import html
import logging

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QDialog, QHBoxLayout,
    QHeaderView, QMessageBox, QTableWidget, QTableWidgetItem, QWidget,
)

from api.applications import app_label
from api.constants import STATUS_OPTIONS
from app.context import AppContext
from app.ui.widgets import button, icon_button, label, line_edit, page_layout, section_header, status_label

from .entry_dialog import EntryDialog, empty_entry
from .prep_runner import PrepAllRunner

logger = logging.getLogger(__name__)

_COLUMNS = ["Company", "Role", "Date Applied", "Status", "Notes", "JD", "Resume", ""]
(
    _COL_COMPANY,
    _COL_ROLE,
    _COL_DATE,
    _COL_STATUS,
    _COL_NOTES,
    _COL_JD,
    _COL_RESUME,
    _COL_DEL,
) = range(8)
# (column, resize mode, initial width)
_COLUMN_SIZING = [
    (_COL_COMPANY, QHeaderView.ResizeMode.Interactive, 160),
    (_COL_ROLE, QHeaderView.ResizeMode.Interactive, 160),
    (_COL_DATE, QHeaderView.ResizeMode.Interactive, 110),
    (_COL_STATUS, QHeaderView.ResizeMode.Interactive, 120),
    (_COL_NOTES, QHeaderView.ResizeMode.Stretch, None),
    (_COL_JD, QHeaderView.ResizeMode.Interactive, 220),
    (_COL_RESUME, QHeaderView.ResizeMode.Fixed, 70),
    (_COL_DEL, QHeaderView.ResizeMode.Fixed, 48),
]

_JD_PREVIEW_MAX = 80
_DELETE_SELECTED_LABEL = "🗑  Delete Selected"
_PREP_LABEL = "⚙  Prep All Materials"
_PREPPED_STATUS = "Materials Prepped"


def _jd_preview(description: str) -> str:
    collapsed = " ".join(description.split())
    if len(collapsed) > _JD_PREVIEW_MAX:
        return collapsed[: _JD_PREVIEW_MAX - 1].rstrip() + "…"
    return collapsed


def _search_text(entry: dict) -> str:
    parts = [entry.get(k, "") for k in ("company", "role", "date", "status", "notes", "description")]
    links = entry.get("links")
    if isinstance(links, list):
        parts.extend(str(link) for link in links)
    return " ".join(p for p in parts if p).lower()


class TrackerPage(QWidget):
    """The Applications tab: a table of tracked job applications.

    ``self._entries`` holds the application dicts in table-row order. Row
    widgets capture the entry dict itself (never its row index), and edits
    update it in place, so callbacks stay correct as rows come and go.
    """

    def __init__(self, ctx: AppContext, parent=None):
        super().__init__(parent)
        self._ctx = ctx
        self._entries: list[dict] = []

        self._prep = PrepAllRunner(ctx, self)
        self._prep.progress.connect(lambda msg: self._prep_status.setText(msg))
        self._prep.job_done.connect(self._on_prepped)
        self._prep.all_done.connect(self._on_prep_all_done)

        outer = page_layout(self)

        self._search_edit = line_edit("Search applications…")
        self._search_edit.setFixedWidth(240)
        self._search_edit.textChanged.connect(self._apply_filter)
        self._prep_status = status_label()
        self._prep_status.setWordWrap(False)
        self._del_selected_btn = button(_DELETE_SELECTED_LABEL, "danger", 150)
        self._del_selected_btn.setEnabled(False)
        self._del_selected_btn.setToolTip(
            "Delete every selected application.\n"
            "Select a range with Shift-click, or pick individual rows with ⌘-click."
        )
        self._del_selected_btn.clicked.connect(self._on_delete_selected_clicked)
        self._prep_btn = button(_PREP_LABEL, "secondary", 170)
        self._prep_btn.clicked.connect(self._on_prep_all_clicked)
        add_btn = button("+ Add Application")
        add_btn.clicked.connect(self._on_add_clicked)
        outer.addLayout(section_header(
            "Application Tracker",
            self._search_edit, self._prep_status, self._del_selected_btn, self._prep_btn, add_btn,
        ))

        self._table = QTableWidget(0, len(_COLUMNS))
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(True)
        self._table.setWordWrap(False)
        self._table.cellClicked.connect(self._on_cell_clicked)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)

        for key in (QKeySequence(QKeySequence.StandardKey.Delete), QKeySequence(Qt.Key.Key_Backspace)):
            shortcut = QShortcut(key, self._table)
            shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
            shortcut.activated.connect(self._on_delete_selected_clicked)

        hdr = self._table.horizontalHeader()
        for col, mode, width in _COLUMN_SIZING:
            hdr.setSectionResizeMode(col, mode)
            if width is not None:
                self._table.setColumnWidth(col, width)

        outer.addWidget(self._table)

    # ── Public API ──────────────────────────────────────────────
    def load(self, entries: list[dict] | None) -> None:
        self.clear()
        for entry in entries or []:
            self.add_entry(entry)

    def add_entry(self, data: dict | None = None) -> None:
        entry = {**empty_entry(), **(data or {})}
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setRowHeight(row, 34)
        self._entries.append(entry)
        self._render_row(row)
        self._apply_filter(self._search_edit.text())

    def get_data(self) -> list[dict]:
        return [dict(entry) for entry in self._entries]

    def set_interview_questions(self, row: int, value: list[dict]) -> None:
        if 0 <= row < len(self._entries):
            self._entries[row]["interview_questions"] = value

    def clear(self) -> None:
        self._table.setRowCount(0)
        self._entries.clear()
        self._on_selection_changed()

    # ── Rendering ───────────────────────────────────────────────
    def _row_of(self, entry: dict) -> int:
        """Current row of ``entry`` (by identity), or -1 if it was deleted."""
        return next((i for i, e in enumerate(self._entries) if e is entry), -1)

    def _render_row(self, row: int) -> None:
        entry = self._entries[row]
        self._table.setItem(row, _COL_COMPANY, QTableWidgetItem(entry["company"]))
        links = entry.get("links") if isinstance(entry.get("links"), list) else []
        self._render_role_cell(row, entry["role"], links[0] if links else "")
        self._table.setItem(row, _COL_DATE, QTableWidgetItem(entry["date"]))
        self._table.setItem(row, _COL_NOTES, QTableWidgetItem(entry["notes"]))

        description = entry.get("description") or ""
        jd_item = QTableWidgetItem(_jd_preview(description))
        if description:
            jd_item.setToolTip(description)
        self._table.setItem(row, _COL_JD, jd_item)

        resume_path = entry.get("resume_pdf") or ""
        resume_item = QTableWidgetItem("✓" if resume_path else "")
        resume_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if resume_path:
            resume_item.setToolTip(str(resume_path))
        self._table.setItem(row, _COL_RESUME, resume_item)

        combo = self._table.cellWidget(row, _COL_STATUS)
        if not isinstance(combo, QComboBox):
            combo = QComboBox()
            combo.addItems(STATUS_OPTIONS)
            combo.currentTextChanged.connect(lambda text, e=entry: e.update(status=text))
            self._table.setCellWidget(row, _COL_STATUS, combo)
        if entry["status"] in STATUS_OPTIONS:
            combo.setCurrentText(entry["status"])

        if self._table.cellWidget(row, _COL_DEL) is None:
            del_btn = icon_button(size=28, tooltip="Delete application")
            del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            del_btn.clicked.connect(lambda _checked=False, e=entry: self._delete([self._row_of(e)]))
            cell = QWidget()
            cell_layout = QHBoxLayout(cell)
            cell_layout.setContentsMargins(0, 0, 0, 0)
            cell_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cell_layout.addWidget(del_btn)
            self._table.setCellWidget(row, _COL_DEL, cell)

    def _render_role_cell(self, row: int, role: str, link: str) -> None:
        if link:
            link_label = label(f'<a href="{html.escape(link, quote=True)}">{html.escape(role)}</a>', "")
            link_label.setOpenExternalLinks(True)
            link_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
            link_label.setContentsMargins(6, 0, 6, 0)
            self._table.setItem(row, _COL_ROLE, QTableWidgetItem())
            self._table.setCellWidget(row, _COL_ROLE, link_label)
        else:
            self._table.removeCellWidget(row, _COL_ROLE)
            self._table.setItem(row, _COL_ROLE, QTableWidgetItem(role))

    def _apply_filter(self, text: str) -> None:
        query = (text or "").strip().lower()
        for r, entry in enumerate(self._entries):
            self._table.setRowHidden(r, bool(query) and query not in _search_text(entry))

    # ── Editing ─────────────────────────────────────────────────
    def _on_add_clicked(self) -> None:
        dlg = EntryDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.add_entry(dlg.get_data())

    def _on_cell_clicked(self, row: int, col: int) -> None:
        if col in (_COL_STATUS, _COL_DEL) or not (0 <= row < len(self._entries)):
            return
        # Shift/⌘-click is the user building a multi-row selection, not asking to edit.
        if QApplication.keyboardModifiers() & (
            Qt.KeyboardModifier.ShiftModifier
            | Qt.KeyboardModifier.ControlModifier
            | Qt.KeyboardModifier.MetaModifier
        ):
            return
        dlg = EntryDialog(self, self._entries[row])
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._entries[row].update(dlg.get_data())
            self._render_row(row)
            self._apply_filter(self._search_edit.text())

    def _save(self) -> None:
        try:
            self._ctx.save()
        except Exception:
            logger.exception("TrackerPage — save failed")

    # ── Deletion ────────────────────────────────────────────────
    def _selected_rows(self) -> list[int]:
        """Selected row indices, ascending. Rows hidden by the search filter never count."""
        model = self._table.selectionModel()
        if model is None:
            return []
        return sorted(
            idx.row()
            for idx in model.selectedRows()
            if not self._table.isRowHidden(idx.row()) and 0 <= idx.row() < len(self._entries)
        )

    def _on_selection_changed(self) -> None:
        count = len(self._selected_rows())
        self._del_selected_btn.setEnabled(count > 0)
        self._del_selected_btn.setText(
            f"{_DELETE_SELECTED_LABEL} ({count})" if count else _DELETE_SELECTED_LABEL
        )

    def _on_delete_selected_clicked(self) -> None:
        rows = self._selected_rows()
        if not rows:
            return
        names = [app_label(self._entries[r]) for r in rows]
        preview = "\n".join(f"  • {n}" for n in names[:8])
        if len(names) > 8:
            preview += f"\n  … and {len(names) - 8} more"
        noun = "application" if len(rows) == 1 else "applications"
        reply = QMessageBox.warning(
            self,
            "Delete Applications",
            f"Permanently delete {len(rows)} {noun}?\n\n{preview}\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes,
            QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._delete(rows)

    def _delete(self, rows: list[int]) -> None:
        rows = sorted(r for r in rows if 0 <= r < len(self._entries))
        for r in reversed(rows):
            self._table.removeRow(r)
            del self._entries[r]
        self._table.clearSelection()
        self._on_selection_changed()
        self._save()
        logger.info("Deleted %d application(s) from the tracker", len(rows))

    # ── Prep All ────────────────────────────────────────────────
    def _on_prep_all_clicked(self) -> None:
        queue = [e for e in self._entries if e.get("status") == "Added"]
        if not queue:
            QMessageBox.information(self, "Prep All Materials", "No applications with status 'Added'.")
            return
        self._prep_btn.setEnabled(False)
        self._prep_btn.setText("Prepping…")
        self._prep.start(queue)

    def _on_prepped(self, entry: dict) -> None:
        row = self._row_of(entry)
        if row >= 0:
            entry["status"] = _PREPPED_STATUS
            combo = self._table.cellWidget(row, _COL_STATUS)
            if isinstance(combo, QComboBox):
                combo.setCurrentText(_PREPPED_STATUS)
        self._save()

    def _on_prep_all_done(self) -> None:
        self._prep_btn.setEnabled(True)
        self._prep_btn.setText(_PREP_LABEL)
        self._save()
