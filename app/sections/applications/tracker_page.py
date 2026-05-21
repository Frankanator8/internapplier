from __future__ import annotations

import html
import logging
from typing import Callable

from PyQt6.QtCore import Qt, QThread
from PyQt6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QHBoxLayout, QHeaderView, QLabel,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget,
)

from ..base import _label, _primary_btn, _secondary_btn
from .entry_dialog import _EntryDialog, _empty_entry, _STATUS_OPTIONS

logger = logging.getLogger(__name__)


_COLUMNS = ["Company", "Role", "Date Applied", "Status", "Notes", ""]
_COL_COMPANY, _COL_ROLE, _COL_DATE, _COL_STATUS, _COL_NOTES, _COL_DEL = range(6)


class TrackerPage(QWidget):
    def __init__(
        self,
        parent=None,
        get_profile: Callable[[], dict] | None = None,
        get_research_cache: Callable[[], dict] | None = None,
        save_fn: Callable[[], None] | None = None,
    ):
        super().__init__(parent)
        self._rows: list[dict] = []
        self._get_profile = get_profile
        self._get_research_cache = get_research_cache
        self._save_fn = save_fn
        self._prep_queue: list[int] = []
        self._prep_threads: list[QThread] = []
        self._prep_workers: list = []
        self._prep_btn: QPushButton | None = None
        self._prep_status: QLabel | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 16)
        outer.setSpacing(14)

        header_row = QHBoxLayout()
        header_row.addWidget(_label("Application Tracker", "section-title"))
        header_row.addStretch()
        self._prep_status = QLabel("")
        self._prep_status.setStyleSheet("color: #555; font-size: 12px;")
        header_row.addWidget(self._prep_status)
        self._prep_btn = _secondary_btn("⚙  Prep All Materials", 170)
        self._prep_btn.clicked.connect(self._on_prep_all_clicked)
        header_row.addWidget(self._prep_btn)
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
        self._table.setColumnWidth(_COL_DEL, 48)

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
        links = entry.get("links") if isinstance(entry.get("links"), list) else []
        primary_link = links[0] if links else ""
        self._render_role_cell(row, entry["role"], primary_link)
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
            del_btn.setToolTip("Delete application")
            del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            del_btn.clicked.connect(lambda _checked=False, b=del_btn: self._remove_row(b))

            cell_widget = QWidget()
            cell_layout = QHBoxLayout(cell_widget)
            cell_layout.setContentsMargins(0, 0, 0, 0)
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
            self._rows[row] = {**self._rows[row], **dlg.get_data()}
            self._refresh_row(row)

    def _remove_row(self, btn: QPushButton):
        for r in range(self._table.rowCount()):
            w = self._table.cellWidget(r, _COL_DEL)
            if w and w.findChild(QPushButton) is btn:
                self._table.removeRow(r)
                del self._rows[r]
                self._rebind_row_callbacks()
                if self._save_fn:
                    try:
                        self._save_fn()
                    except Exception:
                        logger.exception("Delete row: save_fn failed")
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

    def _on_prep_all_clicked(self):
        if self._get_profile is None:
            QMessageBox.warning(self, "Prep All Materials", "Profile not available.")
            return

        queue = [i for i, e in enumerate(self._rows) if e.get("status") == "Added"]
        if not queue:
            QMessageBox.information(
                self, "Prep All Materials", "No applications with status 'Added'."
            )
            return

        self._prep_queue = queue
        if self._prep_btn is not None:
            self._prep_btn.setEnabled(False)
            self._prep_btn.setText("Prepping…")
        self._prep_next()

    def _prep_next(self):
        if not self._prep_queue:
            if self._prep_btn is not None:
                self._prep_btn.setEnabled(True)
                self._prep_btn.setText("⚙  Prep All Materials")
            if self._prep_status is not None:
                self._prep_status.setText("✓  Done.")
            if self._save_fn:
                try:
                    self._save_fn()
                except Exception:
                    logger.exception("Prep All: save_fn failed")
            return

        row = self._prep_queue.pop(0)
        if not (0 <= row < len(self._rows)):
            self._prep_next()
            return

        entry = self._rows[row]
        jd = (entry.get("description") or "").strip()
        company = (entry.get("company") or "").strip()
        if not jd:
            logger.info("Prep All: skipping row %d (%r) — no description", row, company)
            if self._prep_status is not None:
                self._prep_status.setText(f"Skipped {company or 'row'} — no JD.")
            self._prep_next()
            return

        from ..applier.workers import _GenerateResumeWorker  # lazy import to avoid cycle

        profile = self._get_profile() if self._get_profile else {}
        cache = self._get_research_cache() if self._get_research_cache else {}
        links_val = entry.get("links") or []
        url = (links_val[0] if links_val else "").strip()

        remaining = len(self._prep_queue)
        if self._prep_status is not None:
            self._prep_status.setText(
                f"Generating for {company or 'application'}… ({remaining} more queued)"
            )

        worker = _GenerateResumeWorker(profile, jd, company, url, cache)
        thread = QThread(self)
        worker.moveToThread(thread)
        self._prep_threads.append(thread)
        self._prep_workers.append(worker)

        def cleanup():
            thread.quit()

        def on_finished(_payload: dict):
            if 0 <= row < len(self._rows):
                self._rows[row]["status"] = "Materials Prepped"
                combo = self._table.cellWidget(row, _COL_STATUS)
                if isinstance(combo, QComboBox):
                    combo.setCurrentText("Materials Prepped")
            if self._save_fn:
                try:
                    self._save_fn()
                except Exception:
                    logger.exception("Prep All: save_fn failed mid-batch")
            cleanup()
            self._prep_next()

        def on_error(msg: str):
            logger.error("Prep All: row %d (%r) failed — %s", row, company, msg)
            if self._prep_status is not None:
                self._prep_status.setText(f"Error on {company or 'row'}: {msg}")
            cleanup()
            self._prep_next()

        def on_progress(msg: str):
            if self._prep_status is not None:
                self._prep_status.setText(f"{company}: {msg}")

        worker.finished.connect(on_finished)
        worker.error.connect(on_error)
        worker.progress.connect(on_progress)
        thread.started.connect(worker.run)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(
            lambda: self._prep_workers.remove(worker) if worker in self._prep_workers else None
        )
        thread.start()

    def get_data(self) -> list[dict]:
        return [dict(entry) for entry in self._rows]

    def set_interview_questions(self, row: int, value: list[dict]) -> None:
        if 0 <= row < len(self._rows):
            self._rows[row]["interview_questions"] = value

    def clear(self):
        self._table.setRowCount(0)
        self._rows.clear()
