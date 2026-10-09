"""Compound inputs used inside profile entry cards.

Each exposes ``value()`` so ``EntryCard`` can read any field uniformly.
"""
from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QListWidget, QListWidgetItem, QMessageBox,
    QVBoxLayout, QWidget,
)

from app.ui.feedback_panel import FeedbackPanel
from app.ui.widgets import button, icon_button, iter_widgets, label, line_edit
from app.ui.workers import StreamWorker, WorkerPool


def _list_header(title: str, *trailing: QWidget) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setSpacing(8)
    row.addWidget(label(title, "bullets-label"))
    row.addStretch()
    for w in trailing:
        row.addWidget(w)
    return row


class _BulletRow(QWidget):
    """One bullet: text, ✦ analyze, ✕ remove, plus an AI suggestion panel."""

    def __init__(self, text: str):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(4)
        self.edit = line_edit("Describe what you did or built…", text)
        self.ai_btn = icon_button("✦", tooltip="Analyze this bullet with AI", name="ai-btn")
        self.remove_btn = icon_button()
        top.addWidget(self.edit)
        top.addWidget(self.ai_btn)
        top.addWidget(self.remove_btn)
        layout.addLayout(top)

        self.panel = FeedbackPanel()
        layout.addWidget(self.panel)

    def set_busy(self, busy: bool) -> None:
        self.ai_btn.setEnabled(not busy)
        self.ai_btn.setText("…" if busy else "✦")


class BulletsWidget(QWidget):
    def __init__(
        self,
        bullets: list[str] | None = None,
        get_context: Callable[[], dict] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._get_context = get_context
        self._pool = WorkerPool(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(4)

        add_btn = button("+ Add Bullet", "secondary", 110)
        add_btn.clicked.connect(lambda: self._add_item(""))
        layout.addLayout(_list_header("Bullets", add_btn))

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("bullets-list")
        self.list_widget.setSpacing(4)
        self.list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_widget.setSizeAdjustPolicy(QListWidget.SizeAdjustPolicy.AdjustToContents)
        layout.addWidget(self.list_widget)

        for b in bullets or []:
            self._add_item(b)

    def _add_item(self, text: str) -> None:
        row = _BulletRow(text)
        item = QListWidgetItem()
        item.setSizeHint(row.sizeHint())
        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, row)

        row.remove_btn.clicked.connect(lambda: self._remove_item(item))
        row.ai_btn.clicked.connect(lambda: self._analyze(row))
        row.panel.changed.connect(lambda: self._refresh_row_size(item, row))
        self._resize_to_contents()

    def _remove_item(self, item: QListWidgetItem) -> None:
        self.list_widget.takeItem(self.list_widget.row(item))
        self._resize_to_contents()

    def _resize_to_contents(self) -> None:
        lw = self.list_widget
        total = 2 * lw.frameWidth()
        for i in range(lw.count()):
            total += lw.sizeHintForRow(i) + 2 * lw.spacing()
        lw.setFixedHeight(total)

    def _refresh_row_size(self, item: QListWidgetItem, row: QWidget) -> None:
        width = self.list_widget.viewport().width()
        if width > 0:
            row.setFixedWidth(width)
        row.layout().activate()
        row.adjustSize()
        hint = row.sizeHint()
        if width > 0:
            hint.setWidth(width)
        item.setSizeHint(hint)
        self.list_widget.doItemsLayout()
        self._resize_to_contents()

    def _analyze(self, row: _BulletRow) -> None:
        bullet = row.edit.text().strip()
        if not bullet:
            QMessageBox.information(self, "Empty Bullet", "Please enter a bullet point before analyzing.")
            return
        context = self._get_context() if self._get_context else {}

        row.set_busy(True)
        row.panel.begin()

        def on_error(msg: str):
            row.set_busy(False)
            if not row.panel.text():
                row.panel.dismiss()
            QMessageBox.warning(self, "AI Analysis Failed", msg)

        self._pool.start(
            StreamWorker.provider("analyze_bullet_stream", bullet, context),
            chunk=row.panel.append,
            finished=lambda _text: row.set_busy(False),
            error=on_error,
        )

    def value(self) -> list[str]:
        result = []
        for i in range(self.list_widget.count()):
            row = self.list_widget.itemWidget(self.list_widget.item(i))
            text = row.edit.text().strip()
            if text:
                result.append(text)
        return result


class _CourseRow(QFrame):
    def __init__(self, name: str, grade: str):
        super().__init__()
        self.setObjectName("course-row")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(8)
        self.name = line_edit("CS 189: Machine Learning", name)
        self.grade = line_edit("Grade", grade)
        self.grade.setFixedWidth(72)
        self.remove_btn = icon_button(tooltip="Remove this course")
        layout.addWidget(self.name, 1)
        layout.addWidget(self.grade, 0)
        layout.addWidget(self.remove_btn, 0)


class CoursesWidget(QWidget):
    """Coursework editor — one row per course: name and grade.

    Rows live in a plain layout rather than a QListWidget so each one keeps its
    own size hint; a list item's hint is frozen at insertion and clips the row.
    """

    def __init__(self, courses: list[dict] | None = None, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(6)

        add_btn = button("+ Add Course", "secondary", 120)
        add_btn.clicked.connect(lambda: self._add_row())
        layout.addLayout(_list_header("Coursework", add_btn))

        self._rows_layout = QVBoxLayout()
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(6)
        layout.addLayout(self._rows_layout)

        self._empty = label(
            "No coursework yet — add the courses most relevant to your target roles.",
            "field-sublabel", wrap=True,
        )
        layout.addWidget(self._empty)

        for c in courses or []:
            self._add_row(c.get("name", ""), c.get("grade", ""))
        self._sync_empty()

    def _add_row(self, name: str = "", grade: str = "") -> None:
        row = _CourseRow(name, grade)
        row.remove_btn.clicked.connect(lambda: self._remove_row(row))
        self._rows_layout.addWidget(row)
        self._sync_empty()

    def _remove_row(self, row: _CourseRow) -> None:
        self._rows_layout.removeWidget(row)
        row.deleteLater()
        self._sync_empty()

    def _sync_empty(self) -> None:
        self._empty.setVisible(self._rows_layout.count() == 0)

    def value(self) -> list[dict]:
        return [
            {"name": row.name.text().strip(), "grade": row.grade.text().strip()}
            for row in iter_widgets(self._rows_layout)
            if row.name.text().strip()
        ]
