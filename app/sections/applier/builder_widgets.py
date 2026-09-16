"""Palette and canvas widgets for the drag-and-drop resume builder."""
from __future__ import annotations

import copy
import json
import uuid

from PyQt6.QtCore import QMimeData, QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QDrag
from PyQt6.QtWidgets import (
    QAbstractItemView, QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QPlainTextEdit, QScrollArea, QSizePolicy, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from ..base import _icon_btn, _label, _secondary_btn

MIME_TYPE = "application/x-internapplier-resume-item"

KIND_LABELS = {
    "experience": "Experience",
    "project": "Project",
    "education": "Education",
    "award": "Award",
    "skills": "Skills",
    "hobbies": "Interests",
    "text": "Text",
}

_DEFAULT_SECTION_TITLES = {
    "experience": "Relevant Experience",
    "project": "Projects",
    "education": "Education",
    "award": "Achievements",
    "skills": "Technical Skills",
    "hobbies": "Interests",
    "text": "Additional",
    "section": "New Section",
}


def new_id() -> str:
    return uuid.uuid4().hex[:10]


def default_section_title(kind: str, data: dict | None = None) -> str:
    if kind == "experience" and (data or {}).get("category") == "other":
        return "Leadership Experience"
    return _DEFAULT_SECTION_TITLES.get(kind, "Section")


def encode_payload(payload: dict) -> QMimeData:
    mime = QMimeData()
    mime.setData(MIME_TYPE, json.dumps(payload).encode("utf-8"))
    return mime


def decode_payload(mime: QMimeData | None) -> dict | None:
    if mime is None or not mime.hasFormat(MIME_TYPE):
        return None
    try:
        return json.loads(bytes(mime.data(MIME_TYPE)).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, TypeError):
        return None


def _split_csv(text: str) -> list[str]:
    return [p.strip() for p in (text or "").split(",") if p.strip()]


def _join_csv(items: list) -> str:
    return ", ".join(str(s).strip() for s in items if str(s).strip())


def palette_groups(profile: dict) -> list[tuple[str, list[dict]]]:
    """Build (group title, leaf payloads) from a profile dict."""
    profile = profile or {}
    groups: list[tuple[str, list[dict]]] = []

    exp_items: list[dict] = []
    for entry in profile.get("experience") or []:
        if not isinstance(entry, dict):
            continue
        title = (entry.get("title") or entry.get("role") or "").strip()
        company = (entry.get("company") or "").strip()
        if title and company:
            label = f"{title} @ {company}"
        else:
            label = title or company or "Experience"
        exp_items.append({
            "kind": "experience", "label": label, "data": copy.deepcopy(entry),
        })
    groups.append(("Experience", exp_items))

    proj_items: list[dict] = []
    for entry in profile.get("projects") or []:
        if not isinstance(entry, dict):
            continue
        label = (entry.get("name") or "").strip() or "Project"
        proj_items.append({
            "kind": "project", "label": label, "data": copy.deepcopy(entry),
        })
    groups.append(("Projects", proj_items))

    edu_items: list[dict] = []
    for entry in profile.get("education") or []:
        if not isinstance(entry, dict):
            continue
        school = (entry.get("school") or "").strip()
        degree = (entry.get("degree") or "").strip()
        if school and degree:
            label = f"{school} — {degree}"
        else:
            label = school or degree or "Education"
        edu_items.append({
            "kind": "education", "label": label, "data": copy.deepcopy(entry),
        })
    groups.append(("Education", edu_items))

    award_items: list[dict] = []
    for entry in profile.get("awards") or []:
        if not isinstance(entry, dict):
            continue
        title = (entry.get("title") or "").strip()
        issuer = (entry.get("issuer") or "").strip()
        if title and issuer:
            label = f"{title} — {issuer}"
        else:
            label = title or issuer or "Award"
        award_items.append({
            "kind": "award", "label": label, "data": copy.deepcopy(entry),
        })
    groups.append(("Awards", award_items))

    skills = [str(s).strip() for s in (profile.get("skills") or []) if str(s).strip()]
    skill_items: list[dict] = []
    if skills:
        preview = ", ".join(skills[:4])
        if len(skills) > 4:
            preview += "…"
        skill_items.append({
            "kind": "skills",
            "label": preview,
            "data": {"items": skills, "label": "Skills"},
        })
    groups.append(("Skills", skill_items))

    hobbies = [str(s).strip() for s in (profile.get("hobbies") or []) if str(s).strip()]
    hobby_items: list[dict] = []
    if hobbies:
        preview = ", ".join(hobbies[:4])
        if len(hobbies) > 4:
            preview += "…"
        hobby_items.append({
            "kind": "hobbies",
            "label": preview,
            "data": {"items": hobbies, "label": "Interests"},
        })
    groups.append(("Hobbies", hobby_items))

    groups.append(("Building blocks", [
        {"kind": "section", "label": "Section header", "data": {"title": "New Section"}},
        {"kind": "text", "label": "Free-text block", "data": {"body": ""}},
    ]))
    return groups


class _DragHandle(QLabel):
    def __init__(self, parent=None):
        super().__init__("⠿", parent)
        self.setObjectName("builder-handle")
        self.setToolTip("Drag to move")
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setFixedWidth(18)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.start_drag = None
        self._press_pos = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.position()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (
            self._press_pos is not None
            and event.buttons() & Qt.MouseButton.LeftButton
            and (event.position() - self._press_pos).manhattanLength()
            >= QApplication.startDragDistance()
        ):
            self._press_pos = None
            if callable(self.start_drag):
                self.start_drag()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._press_pos = None
        super().mouseReleaseEvent(event)


class CompactBullets(QWidget):
    changed = pyqtSignal()

    def __init__(self, bullets: list[str] | None = None, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addWidget(_label("Bullets"))
        header.addStretch()
        add_btn = _secondary_btn("+ Bullet", 90)
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
        out: list[str] = []
        for i in range(self._rows.count()):
            row = self._rows.itemAt(i).widget()
            if row is None:
                continue
            edit = row.findChild(QLineEdit)
            if edit is not None:
                text = edit.text().strip()
                if text:
                    out.append(text)
        return out

    def _add_empty(self):
        self._add_row("")
        self.changed.emit()

    def _add_row(self, text: str):
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)
        edit = QLineEdit(text)
        edit.setPlaceholderText("Describe what you did or built…")
        edit.textChanged.connect(self.changed.emit)
        remove = _icon_btn("✕")
        remove.clicked.connect(lambda: self._remove_row(row))
        h.addWidget(edit, 1)
        h.addWidget(remove)
        self._rows.addWidget(row)

    def _remove_row(self, row: QWidget):
        self._rows.removeWidget(row)
        row.deleteLater()
        self.changed.emit()


class BuilderItemCard(QFrame):
    changed = pyqtSignal()
    remove_requested = pyqtSignal(object)

    def __init__(self, kind: str, data: dict | None = None, item_id: str | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.kind = kind
        self.item_id = item_id or new_id()
        self._data = copy.deepcopy(data or {})

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(6)
        handle = _DragHandle()
        handle.start_drag = self._start_drag
        top.addWidget(handle)
        badge = QLabel(KIND_LABELS.get(kind, kind.title()))
        badge.setObjectName("applier-section-header")
        top.addWidget(badge)
        top.addStretch()
        remove = _icon_btn("✕")
        remove.setToolTip("Remove from resume")
        remove.clicked.connect(lambda: self.remove_requested.emit(self))
        top.addWidget(remove)
        layout.addLayout(top)

        self._fields: dict = {}
        self._build_fields(layout)

    def _line(self, key: str, placeholder: str, value: str) -> QLineEdit:
        edit = QLineEdit(value)
        edit.setPlaceholderText(placeholder)
        edit.textChanged.connect(self.changed.emit)
        self._fields[key] = edit
        return edit

    def _build_fields(self, layout: QVBoxLayout) -> None:
        data = self._data
        kind = self.kind

        if kind == "experience":
            row = QHBoxLayout()
            row.setSpacing(8)
            row.addWidget(self._line("title", "Title / role", data.get("title") or data.get("role") or ""), 1)
            row.addWidget(self._line("company", "Company", data.get("company") or ""), 1)
            layout.addLayout(row)
            dates = QHBoxLayout()
            dates.setSpacing(8)
            dates.addWidget(self._line("start", "Start", data.get("start") or ""))
            dates.addWidget(self._line("end", "End", data.get("end") or ""))
            layout.addLayout(dates)
            self._bullets = CompactBullets(data.get("bullets") or [])
            self._bullets.changed.connect(self.changed.emit)
            layout.addWidget(self._bullets)
            layout.addWidget(self._line("skills", "Skills (comma-separated)", _join_csv(data.get("skills") or [])))

        elif kind == "project":
            row = QHBoxLayout()
            row.setSpacing(8)
            row.addWidget(self._line("name", "Project name", data.get("name") or ""), 1)
            row.addWidget(self._line("url", "URL", data.get("url") or ""), 1)
            layout.addLayout(row)
            dates = QHBoxLayout()
            dates.setSpacing(8)
            dates.addWidget(self._line("start", "Start", data.get("start") or ""))
            dates.addWidget(self._line("end", "End", data.get("end") or ""))
            layout.addLayout(dates)
            self._bullets = CompactBullets(data.get("bullets") or [])
            self._bullets.changed.connect(self.changed.emit)
            layout.addWidget(self._bullets)
            layout.addWidget(self._line("skills", "Skills (comma-separated)", _join_csv(data.get("skills") or [])))

        elif kind == "education":
            row = QHBoxLayout()
            row.setSpacing(8)
            row.addWidget(self._line("school", "School", data.get("school") or ""), 1)
            row.addWidget(self._line("degree", "Degree", data.get("degree") or ""), 1)
            layout.addLayout(row)
            dates = QHBoxLayout()
            dates.setSpacing(8)
            dates.addWidget(self._line("start", "Start", data.get("start") or ""))
            dates.addWidget(self._line("end", "End", data.get("end") or ""))
            dates.addWidget(self._line("gpa", "GPA", data.get("gpa") or ""))
            layout.addLayout(dates)
            names = []
            for course in data.get("courses") or []:
                if isinstance(course, dict):
                    name = (course.get("name") or "").strip()
                else:
                    name = str(course).strip()
                if name:
                    names.append(name)
            layout.addWidget(self._line("courses", "Courses (comma-separated)", _join_csv(names)))

        elif kind == "award":
            row = QHBoxLayout()
            row.setSpacing(8)
            row.addWidget(self._line("title", "Title", data.get("title") or ""), 1)
            row.addWidget(self._line("issuer", "Issuer", data.get("issuer") or ""), 1)
            row.addWidget(self._line("date", "Date", data.get("date") or ""))
            layout.addLayout(row)
            self._bullets = CompactBullets(data.get("bullets") or [])
            self._bullets.changed.connect(self.changed.emit)
            layout.addWidget(self._bullets)

        elif kind in ("skills", "hobbies"):
            items = data.get("items") or data.get(kind) or []
            layout.addWidget(self._line(
                "items",
                "Items (comma-separated)",
                _join_csv(items if isinstance(items, list) else [items]),
            ))

        elif kind == "text":
            body = QPlainTextEdit()
            body.setPlaceholderText("Free-text block…")
            body.setPlainText(data.get("body") or "")
            body.setMinimumHeight(72)
            body.setMaximumHeight(140)
            body.textChanged.connect(self.changed.emit)
            self._fields["body"] = body
            layout.addWidget(body)

    def current_data(self) -> dict:
        data = copy.deepcopy(self._data)
        fields = self._fields
        if self.kind == "experience":
            data["title"] = fields["title"].text()
            data["company"] = fields["company"].text()
            data["start"] = fields["start"].text()
            data["end"] = fields["end"].text()
            data["bullets"] = self._bullets.bullets()
            data["skills"] = _split_csv(fields["skills"].text())
        elif self.kind == "project":
            data["name"] = fields["name"].text()
            data["url"] = fields["url"].text()
            data["start"] = fields["start"].text()
            data["end"] = fields["end"].text()
            data["bullets"] = self._bullets.bullets()
            data["skills"] = _split_csv(fields["skills"].text())
        elif self.kind == "education":
            data["school"] = fields["school"].text()
            data["degree"] = fields["degree"].text()
            data["start"] = fields["start"].text()
            data["end"] = fields["end"].text()
            data["gpa"] = fields["gpa"].text()
            names = _split_csv(fields["courses"].text())
            old = {
                (c.get("name") or "").strip(): c
                for c in (self._data.get("courses") or [])
                if isinstance(c, dict)
            }
            data["courses"] = [
                old[n] if n in old else {"name": n, "grade": "", "skills": []}
                for n in names
            ]
        elif self.kind == "award":
            data["title"] = fields["title"].text()
            data["issuer"] = fields["issuer"].text()
            data["date"] = fields["date"].text()
            data["bullets"] = self._bullets.bullets()
        elif self.kind in ("skills", "hobbies"):
            data["items"] = _split_csv(fields["items"].text())
        elif self.kind == "text":
            data["body"] = fields["body"].toPlainText()
        return data

    def to_dict(self) -> dict:
        return {"id": self.item_id, "kind": self.kind, "data": self.current_data()}

    def _start_drag(self):
        drag = QDrag(self)
        drag.setMimeData(encode_payload({
            "origin": "canvas",
            "kind": self.kind,
            "id": self.item_id,
        }))
        drag.exec(Qt.DropAction.CopyAction)


class BuilderSection(QFrame):
    changed = pyqtSignal()
    remove_requested = pyqtSignal(object)

    def __init__(self, title: str = "New Section", section_id: str | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("builder-section")
        self.section_id = section_id or new_id()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(8)

        self._header = QWidget()
        header = QHBoxLayout(self._header)
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(6)
        handle = _DragHandle()
        handle.start_drag = self._start_drag
        header.addWidget(handle)
        self._title = QLineEdit(title)
        self._title.setPlaceholderText("Section title")
        self._title.textChanged.connect(self.changed.emit)
        header.addWidget(self._title, 1)
        remove = _icon_btn("✕")
        remove.setToolTip("Remove section")
        remove.clicked.connect(lambda: self.remove_requested.emit(self))
        header.addWidget(remove)
        layout.addWidget(self._header)

        self._items_layout = QVBoxLayout()
        self._items_layout.setContentsMargins(18, 0, 0, 0)
        self._items_layout.setSpacing(8)
        layout.addLayout(self._items_layout)

    def title(self) -> str:
        return self._title.text().strip()

    def header_height(self) -> int:
        return max(self._header.height(), self._header.sizeHint().height())

    def item_widgets(self) -> list[BuilderItemCard]:
        out: list[BuilderItemCard] = []
        for i in range(self._items_layout.count()):
            widget = self._items_layout.itemAt(i).widget()
            if isinstance(widget, BuilderItemCard):
                out.append(widget)
        return out

    def item_count(self) -> int:
        return len(self.item_widgets())

    def item_index(self, card: BuilderItemCard) -> int:
        for i, widget in enumerate(self.item_widgets()):
            if widget is card:
                return i
        return -1

    def insert_item(self, index: int, card: BuilderItemCard) -> None:
        index = max(0, min(index, self.item_count()))
        self._items_layout.insertWidget(index, card)
        card.show()

    def take_item(self, card: BuilderItemCard) -> BuilderItemCard:
        self._items_layout.removeWidget(card)
        card.setParent(None)
        return card

    def _start_drag(self):
        drag = QDrag(self)
        drag.setMimeData(encode_payload({
            "origin": "canvas",
            "kind": "section",
            "id": self.section_id,
        }))
        drag.exec(Qt.DropAction.CopyAction)


class BuilderPalette(QTreeWidget):
    item_activated = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("builder-palette")
        self.setHeaderHidden(True)
        self.setRootIsDecorated(True)
        self.setIndentation(14)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(False)
        self.setDropIndicatorShown(False)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)
        self.itemDoubleClicked.connect(self._on_double_clicked)

    def populate(self, profile: dict) -> None:
        self.clear()
        for group_title, items in palette_groups(profile):
            group = QTreeWidgetItem([group_title])
            group.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.addTopLevelItem(group)
            if items:
                for payload in items:
                    leaf = QTreeWidgetItem([payload.get("label") or payload.get("kind") or "Item"])
                    leaf.setFlags(
                        Qt.ItemFlag.ItemIsEnabled
                        | Qt.ItemFlag.ItemIsSelectable
                        | Qt.ItemFlag.ItemIsDragEnabled
                    )
                    leaf.setData(0, Qt.ItemDataRole.UserRole, payload)
                    leaf.setToolTip(0, "Drag onto the canvas, or double-click to add")
                    group.addChild(leaf)
            else:
                empty = QTreeWidgetItem(["(none in profile)"])
                empty.setFlags(Qt.ItemFlag.ItemIsEnabled)
                empty.setDisabled(True)
                group.addChild(empty)
            group.setExpanded(True)

    def mimeTypes(self):
        return [MIME_TYPE]

    def mimeData(self, items):
        mime = QMimeData()
        for item in items:
            payload = item.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(payload, dict) and payload.get("kind"):
                bundled = {**payload, "origin": "palette"}
                mime.setData(MIME_TYPE, json.dumps(bundled).encode("utf-8"))
                mime.setText(item.text(0))
                return mime
        return mime

    def startDrag(self, supportedActions):
        item = self.currentItem()
        if item is None or not isinstance(item.data(0, Qt.ItemDataRole.UserRole), dict):
            return
        super().startDrag(supportedActions)

    def _on_double_clicked(self, item: QTreeWidgetItem, _column: int):
        payload = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(payload, dict) and payload.get("kind"):
            self.item_activated.emit({**payload, "origin": "palette"})


class BuilderCanvas(QWidget):
    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumWidth(240)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(10)

        self._sections_layout = QVBoxLayout()
        self._sections_layout.setContentsMargins(0, 0, 0, 0)
        self._sections_layout.setSpacing(10)
        layout.addLayout(self._sections_layout)

        self._placeholder = QLabel(
            "Drag items from the palette, or double-click to add.\n"
            "Drop a section header to start a new group."
        )
        self._placeholder.setObjectName("muted")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setWordWrap(True)
        layout.addWidget(self._placeholder)

        add_btn = _secondary_btn("+ Add section", 130)
        add_btn.clicked.connect(self._add_section_clicked)
        layout.addWidget(add_btn, 0, Qt.AlignmentFlag.AlignLeft)

        layout.addStretch(1)

        self._indicator = QFrame(self)
        self._indicator.setObjectName("builder-drop-indicator")
        self._indicator.setFixedHeight(3)
        self._indicator.hide()
        self._indicator.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def _section_widgets(self) -> list[BuilderSection]:
        out: list[BuilderSection] = []
        for i in range(self._sections_layout.count()):
            widget = self._sections_layout.itemAt(i).widget()
            if isinstance(widget, BuilderSection):
                out.append(widget)
        return out

    def _sync_placeholder(self):
        self._placeholder.setVisible(not self._section_widgets())

    def serialize(self) -> list[dict]:
        return [
            {
                "id": sec.section_id,
                "title": sec.title(),
                "items": [card.to_dict() for card in sec.item_widgets()],
            }
            for sec in self._section_widgets()
        ]

    def load_sections(self, sections: list[dict] | None) -> None:
        for sec in list(self._section_widgets()):
            self._sections_layout.removeWidget(sec)
            sec.deleteLater()
        for section in sections or []:
            if not isinstance(section, dict):
                continue
            self.insert_section(
                self._sections_layout.count(),
                section.get("title") or "Section",
                section_id=section.get("id"),
                items=section.get("items") or [],
            )
        self._sync_placeholder()

    def insert_section(
        self,
        index: int,
        title: str,
        section_id: str | None = None,
        items: list | None = None,
    ) -> BuilderSection:
        sec = BuilderSection(title, section_id=section_id)
        sec.changed.connect(self.changed.emit)
        sec.remove_requested.connect(self._on_remove_section)
        index = max(0, min(index, self._sections_layout.count()))
        self._sections_layout.insertWidget(index, sec)
        for item in items or []:
            if not isinstance(item, dict):
                continue
            card = self._new_card(
                item.get("kind") or "text",
                item.get("data") or {},
                item_id=item.get("id"),
            )
            sec.insert_item(sec.item_count(), card)
        self._sync_placeholder()
        return sec

    def add_from_palette(self, payload: dict) -> None:
        kind = payload.get("kind") or ""
        if kind == "section":
            title = (payload.get("data") or {}).get("title") or "New Section"
            self.insert_section(len(self._section_widgets()), title)
            self.changed.emit()
            return
        data = copy.deepcopy(payload.get("data") or {})
        card = self._new_card(kind, data)
        sections = self._section_widgets()
        if not sections:
            self.insert_section(0, default_section_title(kind, data)).insert_item(0, card)
        else:
            last = sections[-1]
            last.insert_item(last.item_count(), card)
        self.changed.emit()

    def _add_section_clicked(self):
        self.insert_section(len(self._section_widgets()), "New Section")
        self.changed.emit()

    def _new_card(self, kind: str, data: dict, item_id: str | None = None) -> BuilderItemCard:
        card = BuilderItemCard(kind, data, item_id=item_id)
        card.changed.connect(self.changed.emit)
        card.remove_requested.connect(self._on_remove_card)
        return card

    def _on_remove_card(self, card: BuilderItemCard):
        for sec in self._section_widgets():
            if sec.item_index(card) >= 0:
                sec.take_item(card)
                card.deleteLater()
                self.changed.emit()
                return

    def _on_remove_section(self, section: BuilderSection):
        self._sections_layout.removeWidget(section)
        section.deleteLater()
        self._sync_placeholder()
        self.changed.emit()

    def _find_card(self, item_id: str) -> tuple[BuilderItemCard | None, BuilderSection | None]:
        for sec in self._section_widgets():
            for card in sec.item_widgets():
                if card.item_id == item_id:
                    return card, sec
        return None, None

    def _find_section(self, section_id: str) -> tuple[BuilderSection | None, int]:
        for i, sec in enumerate(self._section_widgets()):
            if sec.section_id == section_id:
                return sec, i
        return None, -1

    # ---- drag / drop ---------------------------------------------------

    def dragEnterEvent(self, event):
        if decode_payload(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        payload = decode_payload(event.mimeData())
        if not payload:
            event.ignore()
            return
        event.acceptProposedAction()
        pos = event.position().toPoint()
        if payload.get("kind") == "section":
            idx = self._section_drop_index(pos.y())
            self._show_indicator(self._indicator_y_section(idx))
        else:
            si, ii = self._item_drop_index(pos.y())
            self._show_indicator(self._indicator_y_item(si, ii))

    def dragLeaveEvent(self, event):
        self._indicator.hide()
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        payload = decode_payload(event.mimeData())
        self._indicator.hide()
        if not payload:
            event.ignore()
            return
        event.acceptProposedAction()
        self._drop_payload(payload, event.position().toPoint())

    def _drop_payload(self, payload: dict, pos: QPoint) -> None:
        kind = payload.get("kind") or ""
        origin = payload.get("origin") or "palette"
        if kind == "section":
            idx = self._section_drop_index(pos.y())
            if origin == "canvas":
                self._move_section(payload.get("id") or "", idx)
            else:
                title = (payload.get("data") or {}).get("title") or "New Section"
                self.insert_section(idx, title)
            self.changed.emit()
            return

        if origin == "canvas":
            si, ii = self._item_drop_index(pos.y())
            self._move_item(payload.get("id") or "", si, ii)
            self.changed.emit()
            return

        data = copy.deepcopy(payload.get("data") or {})
        card = self._new_card(kind, data)
        sections = self._section_widgets()
        if not sections:
            self.insert_section(0, default_section_title(kind, data)).insert_item(0, card)
        else:
            si, ii = self._item_drop_index(pos.y())
            si = max(0, min(si, len(self._section_widgets()) - 1))
            self._section_widgets()[si].insert_item(ii, card)
        self.changed.emit()

    def _move_section(self, section_id: str, dest_idx: int) -> None:
        sec, src_idx = self._find_section(section_id)
        if sec is None:
            return
        if dest_idx > src_idx:
            dest_idx -= 1
        if dest_idx == src_idx:
            return
        self._sections_layout.removeWidget(sec)
        dest_idx = max(0, min(dest_idx, self._sections_layout.count()))
        self._sections_layout.insertWidget(dest_idx, sec)

    def _move_item(self, item_id: str, dest_si: int, dest_ii: int) -> None:
        card, src_sec = self._find_card(item_id)
        if card is None or src_sec is None:
            return
        src_ii = src_sec.item_index(card)
        sections = self._section_widgets()
        src_si = next((i for i, s in enumerate(sections) if s is src_sec), dest_si)
        if src_si == dest_si and dest_ii in (src_ii, src_ii + 1):
            return
        src_sec.take_item(card)
        sections = self._section_widgets()
        if not sections:
            title = default_section_title(card.kind, card.current_data())
            self.insert_section(0, title).insert_item(0, card)
            return
        src_si = next((i for i, s in enumerate(sections) if s is src_sec), dest_si)
        if src_si == dest_si and dest_ii > src_ii:
            dest_ii -= 1
        dest_si = max(0, min(dest_si, len(sections) - 1))
        sections[dest_si].insert_item(dest_ii, card)

    def _section_drop_index(self, y: int) -> int:
        sections = self._section_widgets()
        for i, sec in enumerate(sections):
            top = sec.mapTo(self, QPoint(0, 0)).y()
            if y < top + sec.height() / 2:
                return i
        return len(sections)

    def _item_drop_index(self, y: int) -> tuple[int, int]:
        sections = self._section_widgets()
        if not sections:
            return 0, 0
        for si, sec in enumerate(sections):
            top = sec.mapTo(self, QPoint(0, 0)).y()
            bottom = top + sec.height()
            if y < top:
                return si, 0
            if y > bottom:
                continue
            items = sec.item_widgets()
            header_bottom = top + sec.header_height()
            if y <= header_bottom or not items:
                return si, 0
            for ii, item in enumerate(items):
                iy = item.mapTo(self, QPoint(0, 0)).y()
                if y < iy + item.height() / 2:
                    return si, ii
            return si, len(items)
        last = sections[-1]
        return len(sections) - 1, last.item_count()

    def _indicator_y_section(self, idx: int) -> int:
        sections = self._section_widgets()
        if not sections:
            return 16
        if idx >= len(sections):
            last = sections[-1]
            return last.mapTo(self, QPoint(0, last.height())).y()
        return sections[idx].mapTo(self, QPoint(0, 0)).y()

    def _indicator_y_item(self, si: int, ii: int) -> int:
        sections = self._section_widgets()
        if not sections:
            return 24
        si = max(0, min(si, len(sections) - 1))
        sec = sections[si]
        items = sec.item_widgets()
        if not items:
            return sec.mapTo(self, QPoint(0, sec.header_height())).y()
        if ii >= len(items):
            last = items[-1]
            return last.mapTo(self, QPoint(0, last.height())).y()
        return items[ii].mapTo(self, QPoint(0, 0)).y()

    def _show_indicator(self, y: int) -> None:
        y = max(0, min(y, max(0, self.height() - 3)))
        self._indicator.setGeometry(8, y, max(40, self.width() - 16), 3)
        self._indicator.show()
        self._indicator.raise_()


class BuilderScroll(QScrollArea):
    """Scroll area that keeps the canvas tall enough to receive drops."""

    def __init__(self, canvas: BuilderCanvas, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setWidget(canvas)
        self._canvas = canvas

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._canvas.setMinimumHeight(self.viewport().height())
