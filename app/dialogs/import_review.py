"""Checkable review of imported profile data before it reaches the profile.

AI extraction from a resume PDF is good but not perfect, so nothing is applied
until the user has seen it. Every entry starts ticked; unticking one drops it.
The dialog is a pure filter — :meth:`ImportReviewDialog.accepted_data` returns
the same dict shape it was handed, so both callers (the main window's live
widgets and onboarding's direct-to-disk write) consume it unchanged.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QHBoxLayout,
    QListWidget, QListWidgetItem, QVBoxLayout, QWidget,
)

from app.ui.widgets import button, group_card, hint, label, scroll_area

# (data key, heading) in the order the profile itself presents them.
_ENTRY_GROUPS = [
    ("experience", "Experience"),
    ("projects", "Projects"),
    ("education", "Education"),
    ("awards", "Awards"),
]
_FLAT_GROUPS = [
    ("skills", "Skills"),
    ("hobbies", "Hobbies"),
]

_CATEGORY_LABELS = ["Relevant Experience", "Leadership / Other"]
_CATEGORY_VALUES = ["relevant", "other"]

_MAX_PREVIEW_BULLETS = 4


def _pretty_field(key: str) -> str:
    return key.replace("_", " ").title()


def _entry_summary(group: str, entry: dict) -> str:
    if group == "experience":
        parts = [entry.get("title", ""), entry.get("company", "")]
    elif group == "projects":
        parts = [entry.get("name", "")]
    elif group == "education":
        parts = [entry.get("degree", ""), entry.get("school", "")]
    else:
        parts = [entry.get("title", ""), entry.get("issuer", "")]
    return " — ".join(p for p in parts if p) or "(untitled)"


def _entry_detail(group: str, entry: dict) -> str:
    lines: list[str] = []

    meta: list[str] = []
    start, end = entry.get("start", ""), entry.get("end", "")
    if start or end:
        meta.append(" – ".join(p for p in (start, end) if p))
    if group == "education" and entry.get("gpa"):
        meta.append(f"GPA {entry['gpa']}")
    if group == "projects" and entry.get("url"):
        meta.append(entry["url"])
    if group == "awards" and entry.get("date"):
        meta.append(entry["date"])
    if meta:
        lines.append(" · ".join(meta))

    if group == "education":
        courses = [c.get("name", "") for c in entry.get("courses") or []]
        courses = [c for c in courses if c]
        if courses:
            lines.append("Courses: " + ", ".join(courses))
    else:
        bullets = [b for b in (entry.get("bullets") or []) if b]
        for bullet in bullets[:_MAX_PREVIEW_BULLETS]:
            lines.append(f"• {bullet}")
        if len(bullets) > _MAX_PREVIEW_BULLETS:
            lines.append(f"…and {len(bullets) - _MAX_PREVIEW_BULLETS} more")

    return "\n".join(lines)


class ImportReviewDialog(QDialog):
    """Modal review of an imported profile dict. Ticked entries are kept."""

    def __init__(self, data: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Review imported resume")
        self.setModal(True)
        self.resize(780, 640)

        # (group key, checkbox, payload) for the card-style groups.
        self._rows: list[tuple[str, QCheckBox, dict | tuple[str, str]]] = []
        # Group-level "All" boxes, keyed by group, kept for two-way syncing.
        self._group_boxes: dict[str, QCheckBox] = {}
        # Flat string sections render as one checkable list each.
        self._lists: dict[str, QListWidget] = {}
        # Per-experience-entry category pickers, aligned with self._rows order.
        self._categories: dict[int, QComboBox] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)

        outer.addWidget(label("Review what we found", "card-title"))
        outer.addWidget(hint(
            "Untick anything the AI got wrong — only ticked entries are imported. "
            "Nothing is saved until you confirm."
        ))

        toolbar = QHBoxLayout()
        select_all = button("Select all", "secondary", 110)
        select_none = button("Select none", "secondary", 110)
        select_all.clicked.connect(lambda: self._set_all(True))
        select_none.clicked.connect(lambda: self._set_all(False))
        toolbar.addWidget(select_all)
        toolbar.addWidget(select_none)
        toolbar.addStretch()
        self._count_label = label("", "hint")
        toolbar.addWidget(self._count_label)
        outer.addLayout(toolbar)

        scroll, self._body = scroll_area(margins=(0, 0, 0, 8))
        outer.addWidget(scroll, stretch=1)

        self._build_identity(data.get("general_info") or {})
        for key, heading in _ENTRY_GROUPS:
            self._build_entry_group(key, heading, data.get(key) or [])
        for key, heading in _FLAT_GROUPS:
            self._build_flat_group(key, heading, data.get(key) or [])

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self._ok_btn.setText("Import selected")
        self._ok_btn.setObjectName("primary")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

        self._refresh_count()

    # ── Construction helpers ────────────────────────────────────────────────

    def _card(self, group: str, heading: str) -> QVBoxLayout:
        all_box = QCheckBox("All")
        all_box.setChecked(True)
        all_box.toggled.connect(lambda on, g=group: self._toggle_group(g, on))
        self._group_boxes[group] = all_box
        frame, vbox = group_card(heading, all_box)
        self._body.addWidget(frame)
        return vbox

    def _build_identity(self, general_info: dict) -> None:
        fields = [(k, v) for k, v in general_info.items() if v]
        if not fields:
            return
        vbox = self._card("general_info", "Identity")
        for key, value in fields:
            box = QCheckBox(f"{_pretty_field(key)}: {value}")
            box.setChecked(True)
            box.toggled.connect(self._on_row_toggled)
            vbox.addWidget(box)
            self._rows.append(("general_info", box, (key, value)))

    def _build_entry_group(self, group: str, heading: str, entries: list) -> None:
        entries = [e for e in entries if isinstance(e, dict)]
        if not entries:
            return
        vbox = self._card(group, heading)
        for entry in entries:
            row = QWidget()
            row_layout = QVBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(4)

            top = QHBoxLayout()
            top.setSpacing(10)
            box = QCheckBox(_entry_summary(group, entry))
            box.setChecked(True)
            box.toggled.connect(self._on_row_toggled)
            top.addWidget(box, stretch=1)

            if group == "experience":
                combo = QComboBox()
                combo.addItems(_CATEGORY_LABELS)
                current = entry.get("category", "relevant")
                combo.setCurrentIndex(
                    _CATEGORY_VALUES.index(current) if current in _CATEGORY_VALUES else 0
                )
                combo.setFixedWidth(180)
                top.addWidget(combo)
                self._categories[len(self._rows)] = combo

            row_layout.addLayout(top)

            detail_text = _entry_detail(group, entry)
            if detail_text:
                detail = hint(detail_text)
                detail.setContentsMargins(24, 0, 0, 0)
                row_layout.addWidget(detail)

            vbox.addWidget(row)
            self._rows.append((group, box, entry))

    def _build_flat_group(self, group: str, heading: str, items: list) -> None:
        items = [str(x) for x in items if str(x).strip()]
        if not items:
            return
        vbox = self._card(group, heading)
        # One checkable list rather than N checkboxes — a skills section can
        # run to 60 entries and would otherwise dominate the dialog.
        listw = QListWidget()
        listw.setObjectName("skills-list")
        listw.setMaximumHeight(180)
        for value in items:
            item = QListWidgetItem(value)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            listw.addItem(item)
        listw.itemChanged.connect(self._on_row_toggled)
        vbox.addWidget(listw)
        self._lists[group] = listw

    # ── Selection state ─────────────────────────────────────────────────────

    def _set_all(self, checked: bool) -> None:
        for box in self._group_boxes.values():
            box.setChecked(checked)
        # A group whose "All" box was already in this state emits nothing, so
        # drive the rows directly too.
        self._apply_checked(checked)
        self._refresh_count()

    def _apply_checked(self, checked: bool, group: str | None = None) -> None:
        for row_group, box, _ in self._rows:
            if group is None or row_group == group:
                box.blockSignals(True)
                box.setChecked(checked)
                box.blockSignals(False)
        for list_group, listw in self._lists.items():
            if group is not None and list_group != group:
                continue
            listw.blockSignals(True)
            state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
            for i in range(listw.count()):
                listw.item(i).setCheckState(state)
            listw.blockSignals(False)

    def _toggle_group(self, group: str, checked: bool) -> None:
        self._apply_checked(checked, group)
        self._refresh_count()

    def _on_row_toggled(self, *_args) -> None:
        self._refresh_count()

    def _selected_count(self) -> int:
        count = sum(1 for _, box, _ in self._rows if box.isChecked())
        for listw in self._lists.values():
            count += sum(
                1 for i in range(listw.count())
                if listw.item(i).checkState() == Qt.CheckState.Checked
            )
        return count

    def _refresh_count(self) -> None:
        selected = self._selected_count()
        total = len(self._rows) + sum(lw.count() for lw in self._lists.values())
        self._count_label.setText(f"{selected} of {total} selected")
        self._ok_btn.setEnabled(selected > 0)

    # ── Result ──────────────────────────────────────────────────────────────

    def accepted_data(self) -> dict:
        """The ticked subset, in the same shape the dialog was given."""
        result: dict = {
            "general_info": {},
            "experience": [], "projects": [], "education": [], "awards": [],
            "skills": [], "hobbies": [],
        }
        for index, (group, box, payload) in enumerate(self._rows):
            if not box.isChecked():
                continue
            if group == "general_info":
                key, value = payload
                result["general_info"][key] = value
            elif group == "experience":
                combo = self._categories.get(index)
                category = (
                    _CATEGORY_VALUES[combo.currentIndex()] if combo else
                    payload.get("category", "relevant")
                )
                result["experience"].append({**payload, "category": category})
            else:
                result[group].append(dict(payload))

        for group, listw in self._lists.items():
            result[group] = [
                listw.item(i).text()
                for i in range(listw.count())
                if listw.item(i).checkState() == Qt.CheckState.Checked
            ]

        return result
