"""Canvas widgets: a draggable section holding draggable item cards."""
from __future__ import annotations

import copy

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDrag
from PyQt6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
    QVBoxLayout, QWidget,
)

from api.generate_resume.manual_render import course_names
from app.ui.widgets import button, icon_button, iter_widgets, label, line_edit

from .model import KIND_LABELS, encode_payload, join_csv, new_id, split_csv

# Per-kind card layout. A tuple is a row of line edits: (key, placeholder,
# stretch). A string names a special field: bullets, courses, items, body.
_DATES = (("start", "Start", 0), ("end", "End", 0))
_ITEM_LAYOUTS: dict[str, list] = {
    "experience": [(("title", "Title / role", 1), ("company", "Company", 1)), _DATES, "bullets"],
    "project": [(("name", "Project name", 1), ("url", "URL", 1)), _DATES, "bullets"],
    "education": [(("school", "School", 1), ("degree", "Degree", 1)), (*_DATES, ("gpa", "GPA", 0)), "courses"],
    "award": [(("title", "Title", 1), ("issuer", "Issuer", 1), ("date", "Date", 0)), "bullets"],
    "skills": ["items"],
    "hobbies": ["items"],
    "text": ["body"],
}
_CSV_PLACEHOLDERS = {
    "courses": "Courses (comma-separated)",
    "items": "Items (comma-separated)",
}


class _DragHandle(QLabel):
    """⠿ grip that emits ``drag_started`` once the mouse moves far enough."""

    drag_started = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("⠿", parent)
        self.setObjectName("builder-handle")
        self.setToolTip("Drag to move")
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setFixedWidth(18)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._press_pos = None

    def mousePressEvent(self, event):  # noqa: N802 (Qt API)
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.position()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):  # noqa: N802 (Qt API)
        if (
            self._press_pos is not None
            and event.buttons() & Qt.MouseButton.LeftButton
            and (event.position() - self._press_pos).manhattanLength()
            >= QApplication.startDragDistance()
        ):
            self._press_pos = None
            self.drag_started.emit()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802 (Qt API)
        self._press_pos = None
        super().mouseReleaseEvent(event)


class _DraggableFrame(QFrame):
    """Frame with a [⠿ … ✕] header that drags itself within the canvas."""

    changed = pyqtSignal()
    remove_requested = pyqtSignal(object)

    drag_kind = ""

    def _header(self, widget: QWidget, stretch: int, remove_tooltip: str) -> QHBoxLayout:
        """[⠿ widget ✕]; with ``stretch`` 0 the widget hugs the handle."""
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        handle = _DragHandle()
        handle.drag_started.connect(self._start_drag)
        row.addWidget(handle)
        row.addWidget(widget, stretch)
        if not stretch:
            row.addStretch()
        remove = icon_button(tooltip=remove_tooltip)
        remove.clicked.connect(lambda: self.remove_requested.emit(self))
        row.addWidget(remove)
        return row

    def drag_id(self) -> str:
        raise NotImplementedError

    def _start_drag(self) -> None:
        drag = QDrag(self)
        drag.setMimeData(encode_payload({"origin": "canvas", "kind": self.drag_kind, "id": self.drag_id()}))
        drag.exec(Qt.DropAction.CopyAction)


class CompactBullets(QWidget):
    changed = pyqtSignal()

    def __init__(self, bullets: list[str] | None = None, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addWidget(label("Bullets"))
        header.addStretch()
        add_btn = button("+ Bullet", "secondary", 90)
        add_btn.clicked.connect(self._add_empty)
        header.addWidget(add_btn)
        layout.addLayout(header)

        self._rows = QVBoxLayout()
        self._rows.setContentsMargins(0, 0, 0, 0)
        self._rows.setSpacing(4)
        layout.addLayout(self._rows)
        for text in bullets or []:
            self._add_row(text)

    def bullets(self) -> list[str]:
        texts = (row.findChild(QLineEdit).text().strip() for row in iter_widgets(self._rows))
        return [t for t in texts if t]

    def _add_empty(self) -> None:
        self._add_row("")
        self.changed.emit()

    def _add_row(self, text: str) -> None:
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)
        edit = line_edit("Describe what you did or built…", text)
        edit.textChanged.connect(self.changed.emit)
        remove = icon_button()
        remove.clicked.connect(lambda: self._remove_row(row))
        h.addWidget(edit, 1)
        h.addWidget(remove)
        self._rows.addWidget(row)

    def _remove_row(self, row: QWidget) -> None:
        self._rows.removeWidget(row)
        row.deleteLater()
        self.changed.emit()


class BuilderItemCard(_DraggableFrame):
    """One resume entry on the canvas, editable without touching the profile."""

    def __init__(self, kind: str, data: dict | None = None, item_id: str | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.kind = kind
        self.drag_kind = kind
        self.item_id = item_id or new_id()
        self._data = copy.deepcopy(data or {})
        self._lines: dict[str, QLineEdit] = {}
        self._bullets: CompactBullets | None = None
        self._body: QPlainTextEdit | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
        badge = label(KIND_LABELS.get(kind, kind.title()), "applier-section-header")
        layout.addLayout(self._header(badge, 0, remove_tooltip="Remove from resume"))
        for spec in _ITEM_LAYOUTS.get(kind, []):
            self._add_field(layout, spec)

    def drag_id(self) -> str:
        return self.item_id

    def _line(self, key: str, placeholder: str, value: str) -> QLineEdit:
        edit = line_edit(placeholder, value)
        edit.textChanged.connect(self.changed.emit)
        self._lines[key] = edit
        return edit

    def _initial_text(self, key: str) -> str:
        data = self._data
        if key == "title" and self.kind == "experience":
            return data.get("title") or data.get("role") or ""
        if key == "courses":
            return join_csv(course_names(data))
        if key == "items":
            items = data.get("items") or data.get(self.kind) or []
            return join_csv(items if isinstance(items, list) else [items])
        return data.get(key) or ""

    def _add_field(self, layout: QVBoxLayout, spec) -> None:
        if isinstance(spec, tuple):
            row = QHBoxLayout()
            row.setSpacing(8)
            for key, placeholder, stretch in spec:
                row.addWidget(self._line(key, placeholder, self._initial_text(key)), stretch)
            layout.addLayout(row)
        elif spec == "bullets":
            self._bullets = CompactBullets(self._data.get("bullets") or [])
            self._bullets.changed.connect(self.changed.emit)
            layout.addWidget(self._bullets)
        elif spec == "body":
            self._body = QPlainTextEdit()
            self._body.setPlaceholderText("Free-text block…")
            self._body.setPlainText(self._data.get("body") or "")
            self._body.setMinimumHeight(72)
            self._body.setMaximumHeight(140)
            self._body.textChanged.connect(self.changed.emit)
            layout.addWidget(self._body)
        else:  # comma-separated list
            layout.addWidget(self._line(spec, _CSV_PLACEHOLDERS[spec], self._initial_text(spec)))

    def current_data(self) -> dict:
        """The original data with every edited field written back over it."""
        data = copy.deepcopy(self._data)
        for spec in _ITEM_LAYOUTS.get(self.kind, []):
            if isinstance(spec, tuple):
                for key, *_ in spec:
                    data[key] = self._lines[key].text()
            elif spec == "bullets":
                data["bullets"] = self._bullets.bullets()
            elif spec == "body":
                data["body"] = self._body.toPlainText()
            elif spec == "courses":
                # Keep grades of courses that survived the edit.
                old = {
                    (c.get("name") or "").strip(): c
                    for c in self._data.get("courses") or []
                    if isinstance(c, dict)
                }
                data["courses"] = [
                    old.get(n) or {"name": n, "grade": ""}
                    for n in split_csv(self._lines["courses"].text())
                ]
            else:
                data[spec] = split_csv(self._lines[spec].text())
        return data

    def to_dict(self) -> dict:
        return {"id": self.item_id, "kind": self.kind, "data": self.current_data()}


class BuilderSection(_DraggableFrame):
    """A titled group of item cards."""

    drag_kind = "section"

    def __init__(self, title: str = "New Section", section_id: str | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("builder-section")
        self.section_id = section_id or new_id()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(8)

        self._title = line_edit("Section title", title)
        self._title.textChanged.connect(self.changed.emit)
        self._header_widget = QWidget()
        self._header_widget.setLayout(self._header(self._title, 1, remove_tooltip="Remove section"))
        layout.addWidget(self._header_widget)

        self._items_layout = QVBoxLayout()
        self._items_layout.setContentsMargins(18, 0, 0, 0)
        self._items_layout.setSpacing(8)
        layout.addLayout(self._items_layout)

    def drag_id(self) -> str:
        return self.section_id

    def title(self) -> str:
        return self._title.text().strip()

    def header_height(self) -> int:
        return max(self._header_widget.height(), self._header_widget.sizeHint().height())

    def item_widgets(self) -> list[BuilderItemCard]:
        return [w for w in iter_widgets(self._items_layout) if isinstance(w, BuilderItemCard)]

    def item_count(self) -> int:
        return len(self.item_widgets())

    def item_index(self, card: BuilderItemCard) -> int:
        return next((i for i, w in enumerate(self.item_widgets()) if w is card), -1)

    def insert_item(self, index: int, card: BuilderItemCard) -> None:
        self._items_layout.insertWidget(max(0, min(index, self.item_count())), card)
        card.show()

    def take_item(self, card: BuilderItemCard) -> BuilderItemCard:
        self._items_layout.removeWidget(card)
        card.setParent(None)
        return card
