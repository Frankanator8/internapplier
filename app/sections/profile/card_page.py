from __future__ import annotations

from typing import Callable, Union

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLineEdit, QVBoxLayout, QWidget

from app.ui.widgets import (
    button, clear_layout, field, iter_widgets, label, line_edit, page_layout,
    scroll_area, section_header,
)

from .widgets import BulletsWidget

# A row of text fields: (key, label, placeholder, stretch) tuples, or a bare
# int for a trailing stretch.
FieldSpec = tuple[str, str, str, int]
RowSpec = tuple[Union[FieldSpec, int], ...]


class EntryCard(QFrame):
    """One profile entry: a card of named inputs read back via ``value()``."""

    def __init__(self, data: dict):
        super().__init__()
        self.setObjectName("card")
        self.data = data
        self.group: str | None = None
        self._fields: dict[str, QWidget] = {}
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(20, 18, 20, 16)
        self.body.setSpacing(12)

    def add_row(self, specs: RowSpec) -> None:
        row = QHBoxLayout()
        row.setSpacing(16)
        for spec in specs:
            if isinstance(spec, int):
                row.addStretch(spec)
                continue
            key, label_text, placeholder, stretch = spec
            edit = line_edit(placeholder, self.data.get(key, ""))
            self._fields[key] = edit
            row.addLayout(field(label_text, edit), stretch)
        self.body.addLayout(row)

    def add_widget(self, key: str, widget: QWidget) -> None:
        self._fields[key] = widget
        self.body.addWidget(widget)

    def text(self, key: str) -> str:
        return self._fields[key].text()

    def add_remove_footer(self, on_remove: Callable[[], None]) -> None:
        footer = QHBoxLayout()
        footer.addStretch()
        remove = button("Remove Entry", "danger")
        remove.clicked.connect(on_remove)
        footer.addWidget(remove)
        self.body.addLayout(footer)

    def value(self) -> dict:
        return {
            key: w.text() if isinstance(w, QLineEdit) else w.value()
            for key, w in self._fields.items()
        }


class CardPage(QWidget):
    """Section editor holding a list of ``EntryCard``s.

    Subclasses declare ``rows`` (the text-field layout) and may override
    ``add_extras`` for richer inputs. With ``groups`` set, cards are split
    under subtitled groups and each entry records its group as ``category``.
    """

    section_title = "Section"
    add_label = ""
    rows: tuple[RowSpec, ...] = ()
    # (key, subtitle, add-button label); empty → a single ungrouped list.
    groups: tuple[tuple[str, str, str], ...] = ()

    def __init__(self, parent=None):
        super().__init__(parent)
        outer = page_layout(self)

        if self.groups:
            outer.addWidget(label(self.section_title, "section-title"))
            scroll, container = scroll_area(spacing=20)
            self._group_layouts: dict[str | None, QVBoxLayout] = {}
            for key, subtitle, add_text in self.groups:
                add_btn = button(add_text)
                add_btn.clicked.connect(lambda _checked=False, k=key: self.add_entry(group=k))
                container.addLayout(section_header(subtitle, add_btn, name="group-subtitle"))
                cards = QVBoxLayout()
                cards.setAlignment(Qt.AlignmentFlag.AlignTop)
                cards.setSpacing(14)
                container.addLayout(cards)
                self._group_layouts[key] = cards
        else:
            add_btn = button(self.add_label or f"+ Add {self.section_title.rstrip('s')} Entry")
            add_btn.clicked.connect(lambda: self.add_entry())
            outer.addLayout(section_header(self.section_title, add_btn))
            scroll, cards = scroll_area()
            self._group_layouts = {None: cards}
        outer.addWidget(scroll)

    # ── Card construction ───────────────────────────────────────
    def add_extras(self, card: EntryCard) -> None:
        """Hook for inputs beyond the text rows (bullets, courses…)."""

    def add_bullets(self, card: EntryCard, context: Callable[[], dict]) -> None:
        card.add_widget("bullets", BulletsWidget(card.data.get("bullets", []), get_context=context))

    def add_entry(self, data: dict | None = None, group: str | None = None) -> EntryCard:
        data = data or {}
        if self.groups:
            group = data.get("category", group)
            if group not in self._group_layouts:
                group = self.groups[0][0]
        card = EntryCard(data)
        card.group = group
        for row in self.rows:
            card.add_row(row)
        self.add_extras(card)
        card.add_remove_footer(lambda: self._remove_card(card))
        self._group_layouts[group].addWidget(card)
        return card

    def _remove_card(self, card: EntryCard) -> None:
        self._group_layouts[card.group].removeWidget(card)
        card.deleteLater()

    # ── Profile section interface ───────────────────────────────
    def load(self, entries: list[dict] | None) -> None:
        self.clear()
        self.merge(entries, "append")

    def merge(self, entries: list[dict] | None, mode: str) -> None:
        if mode == "replace":
            self.clear()
        for entry in entries or []:
            self.add_entry(entry)

    def clear(self) -> None:
        for layout in self._group_layouts.values():
            clear_layout(layout)

    def has_data(self) -> bool:
        return any(layout.count() for layout in self._group_layouts.values())

    def get_data(self) -> list[dict]:
        result = []
        for key, layout in self._group_layouts.items():
            for card in iter_widgets(layout):
                entry = card.value()
                if key is not None:
                    entry["category"] = key
                result.append(entry)
        return result
