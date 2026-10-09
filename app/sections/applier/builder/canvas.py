from __future__ import annotations

import copy

from PyQt6.QtCore import QObject, QPoint, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QFrame, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

from app.ui.widgets import button, iter_widgets, label

from .cards import BuilderItemCard, BuilderSection
from .model import decode_payload, default_section_title

# Drag auto-scroll: how close to the viewport edge starts it, and how fast.
AUTOSCROLL_MARGIN = 48
AUTOSCROLL_STEP = 14
AUTOSCROLL_INTERVAL_MS = 30


class AutoScroller(QObject):
    """Scrolls the enclosing QScrollArea while a drag hovers near its edges."""

    def __init__(self, widget: QWidget):
        super().__init__(widget)
        self._widget = widget
        self.delta = 0
        self.timer = QTimer(self)
        self.timer.setInterval(AUTOSCROLL_INTERVAL_MS)
        self.timer.timeout.connect(self.tick)

    def _scroll_area(self) -> QScrollArea | None:
        parent = self._widget.parentWidget()
        while parent is not None and not isinstance(parent, QScrollArea):
            parent = parent.parentWidget()
        return parent

    def update(self, widget_y: int) -> None:
        """Start, retarget or stop scrolling for a drag at ``widget_y``."""
        area = self._scroll_area()
        bar = area.verticalScrollBar() if area is not None else None
        if bar is None or bar.maximum() <= 0:
            self.stop()
            return
        # The widget sits at -bar.value() inside the viewport.
        view_y = widget_y - bar.value()
        if view_y < AUTOSCROLL_MARGIN:
            self.delta = -AUTOSCROLL_STEP
        elif view_y > area.viewport().height() - AUTOSCROLL_MARGIN:
            self.delta = AUTOSCROLL_STEP
        else:
            self.stop()
            return
        if not self.timer.isActive():
            self.timer.start()

    def tick(self) -> None:
        area = self._scroll_area()
        if area is None or not self.delta:
            self.stop()
            return
        bar = area.verticalScrollBar()
        before = bar.value()
        bar.setValue(before + self.delta)
        if bar.value() == before:  # hit an end
            self.stop()

    def stop(self) -> None:
        self.delta = 0
        self.timer.stop()


class BuilderCanvas(QWidget):
    """The resume being built: an ordered list of sections, each with items.

    Accepts palette drops (new items/sections) and canvas drags (moves).
    """

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

        self._placeholder = label(
            "Drag items from the palette, or double-click to add.\n"
            "Drop a section header to start a new group.",
            "muted", wrap=True,
        )
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._placeholder)

        add_btn = button("+ Add section", "secondary", 130)
        add_btn.clicked.connect(lambda: self._append_section("New Section"))
        layout.addWidget(add_btn, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addStretch(1)

        self._indicator = QFrame(self)
        self._indicator.setObjectName("builder-drop-indicator")
        self._indicator.setFixedHeight(3)
        self._indicator.hide()
        self._indicator.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self._autoscroll = AutoScroller(self)

    # ── Model ───────────────────────────────────────────────────
    def _section_widgets(self) -> list[BuilderSection]:
        return [w for w in iter_widgets(self._sections_layout) if isinstance(w, BuilderSection)]

    def _sync_placeholder(self) -> None:
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
        for sec in self._section_widgets():
            self._sections_layout.removeWidget(sec)
            sec.deleteLater()
        for section in sections or []:
            if isinstance(section, dict):
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
        sec.remove_requested.connect(self._remove_section)
        self._sections_layout.insertWidget(max(0, min(index, self._sections_layout.count())), sec)
        for item in items or []:
            if isinstance(item, dict):
                card = self._new_card(item.get("kind") or "text", item.get("data") or {}, item.get("id"))
                sec.insert_item(sec.item_count(), card)
        self._sync_placeholder()
        return sec

    def _append_section(self, title: str) -> None:
        self.insert_section(len(self._section_widgets()), title)
        self.changed.emit()

    def add_from_palette(self, payload: dict) -> None:
        """Double-click add: sections go last, items into the last section."""
        kind = payload.get("kind") or ""
        if kind == "section":
            self._append_section((payload.get("data") or {}).get("title") or "New Section")
            return
        self._place_card(self._new_card(kind, copy.deepcopy(payload.get("data") or {})))
        self.changed.emit()

    def _place_card(self, card: BuilderItemCard, si: int | None = None, ii: int | None = None) -> None:
        """Insert ``card`` at (section, index) — by default the end of the last
        section — creating a fitting first section if the canvas is empty."""
        sections = self._section_widgets()
        if not sections:
            title = default_section_title(card.kind, card.current_data())
            self.insert_section(0, title).insert_item(0, card)
            return
        sec = sections[len(sections) - 1 if si is None else max(0, min(si, len(sections) - 1))]
        sec.insert_item(sec.item_count() if ii is None else ii, card)

    def _new_card(self, kind: str, data: dict, item_id: str | None = None) -> BuilderItemCard:
        card = BuilderItemCard(kind, data, item_id=item_id)
        card.changed.connect(self.changed.emit)
        card.remove_requested.connect(self._remove_card)
        return card

    def _remove_card(self, card: BuilderItemCard) -> None:
        for sec in self._section_widgets():
            if sec.item_index(card) >= 0:
                sec.take_item(card)
                card.deleteLater()
                self.changed.emit()
                return

    def _remove_section(self, section: BuilderSection) -> None:
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

    # ── Drag and drop ───────────────────────────────────────────
    def dragEnterEvent(self, event):  # noqa: N802 (Qt API)
        if decode_payload(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):  # noqa: N802 (Qt API)
        payload = decode_payload(event.mimeData())
        if not payload:
            event.ignore()
            return
        event.acceptProposedAction()
        pos = event.position().toPoint()
        self._autoscroll.update(pos.y())
        if payload.get("kind") == "section":
            self._show_indicator(self._indicator_y_section(self._section_drop_index(pos.y())))
        else:
            self._show_indicator(self._indicator_y_item(*self._item_drop_index(pos.y())))

    def dragLeaveEvent(self, event):  # noqa: N802 (Qt API)
        self._autoscroll.stop()
        self._indicator.hide()
        super().dragLeaveEvent(event)

    def dropEvent(self, event):  # noqa: N802 (Qt API)
        payload = decode_payload(event.mimeData())
        self._autoscroll.stop()
        self._indicator.hide()
        if not payload:
            event.ignore()
            return
        event.acceptProposedAction()
        self._drop_payload(payload, event.position().toPoint())

    def _drop_payload(self, payload: dict, pos: QPoint) -> None:
        kind = payload.get("kind") or ""
        from_canvas = (payload.get("origin") or "palette") == "canvas"
        if kind == "section":
            idx = self._section_drop_index(pos.y())
            if from_canvas:
                self._move_section(payload.get("id") or "", idx)
            else:
                self.insert_section(idx, (payload.get("data") or {}).get("title") or "New Section")
        elif from_canvas:
            self._move_item(payload.get("id") or "", *self._item_drop_index(pos.y()))
        else:
            card = self._new_card(kind, copy.deepcopy(payload.get("data") or {}))
            self._place_card(card, *self._item_drop_index(pos.y()))
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
        self._sections_layout.insertWidget(max(0, min(dest_idx, self._sections_layout.count())), sec)

    def _move_item(self, item_id: str, dest_si: int, dest_ii: int) -> None:
        card, src_sec = self._find_card(item_id)
        if card is None or src_sec is None:
            return
        src_ii = src_sec.item_index(card)
        src_si = next((i for i, s in enumerate(self._section_widgets()) if s is src_sec), dest_si)
        if src_si == dest_si and dest_ii in (src_ii, src_ii + 1):
            return
        src_sec.take_item(card)
        if src_si == dest_si and dest_ii > src_ii:
            dest_ii -= 1
        self._place_card(card, dest_si, dest_ii)

    # ── Drop geometry ───────────────────────────────────────────
    def _top(self, w: QWidget) -> int:
        return w.mapTo(self, QPoint(0, 0)).y()

    def _section_drop_index(self, y: int) -> int:
        sections = self._section_widgets()
        for i, sec in enumerate(sections):
            if y < self._top(sec) + sec.height() / 2:
                return i
        return len(sections)

    def _item_drop_index(self, y: int) -> tuple[int, int]:
        sections = self._section_widgets()
        if not sections:
            return 0, 0
        for si, sec in enumerate(sections):
            top = self._top(sec)
            if y < top:
                return si, 0
            if y > top + sec.height():
                continue
            items = sec.item_widgets()
            if y <= top + sec.header_height() or not items:
                return si, 0
            for ii, item in enumerate(items):
                if y < self._top(item) + item.height() / 2:
                    return si, ii
            return si, len(items)
        return len(sections) - 1, sections[-1].item_count()

    def _indicator_y_section(self, idx: int) -> int:
        sections = self._section_widgets()
        if not sections:
            return 16
        if idx >= len(sections):
            return self._top(sections[-1]) + sections[-1].height()
        return self._top(sections[idx])

    def _indicator_y_item(self, si: int, ii: int) -> int:
        sections = self._section_widgets()
        if not sections:
            return 24
        sec = sections[max(0, min(si, len(sections) - 1))]
        items = sec.item_widgets()
        if not items:
            return self._top(sec) + sec.header_height()
        if ii >= len(items):
            return self._top(items[-1]) + items[-1].height()
        return self._top(items[ii])

    def _show_indicator(self, y: int) -> None:
        y = max(0, min(y, max(0, self.height() - 3)))
        self._indicator.setGeometry(8, y, max(40, self.width() - 16), 3)
        self._indicator.show()
        self._indicator.raise_()


class BuilderScroll(QScrollArea):
    """Scroll area for the canvas.

    ``setWidgetResizable`` already grows the canvas to at least the viewport,
    so the canvas must *not* be given an explicit minimum height: Qt treats an
    explicit minimum as an override of the layout's own minimum, which pins the
    canvas to the viewport and stops it scrolling once the resume is long.
    """

    def __init__(self, canvas: BuilderCanvas, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.verticalScrollBar().setSingleStep(24)
        self.setWidget(canvas)
