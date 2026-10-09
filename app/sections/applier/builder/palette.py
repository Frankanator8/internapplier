from __future__ import annotations

from PyQt6.QtCore import QMimeData, Qt, pyqtSignal
from PyQt6.QtWidgets import QAbstractItemView, QTreeWidget, QTreeWidgetItem

from .model import MIME_TYPE, encode_payload, palette_groups


class BuilderPalette(QTreeWidget):
    """Profile entries grouped by section, dragged (or double-clicked) onto the canvas."""

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
            if not items:
                empty = QTreeWidgetItem(["(none in profile)"])
                empty.setFlags(Qt.ItemFlag.ItemIsEnabled)
                empty.setDisabled(True)
                group.addChild(empty)
            group.setExpanded(True)

    @staticmethod
    def _payload(item: QTreeWidgetItem) -> dict | None:
        payload = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(payload, dict) and payload.get("kind"):
            return {**payload, "origin": "palette"}
        return None

    def mimeTypes(self):  # noqa: N802 (Qt API)
        return [MIME_TYPE]

    def mimeData(self, items):  # noqa: N802 (Qt API)
        for item in items:
            payload = self._payload(item)
            if payload is not None:
                mime = encode_payload(payload)
                mime.setText(item.text(0))
                return mime
        return QMimeData()

    def startDrag(self, supportedActions):  # noqa: N802 (Qt API)
        item = self.currentItem()
        if item is not None and self._payload(item) is not None:
            super().startDrag(supportedActions)

    def _on_double_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        payload = self._payload(item)
        if payload is not None:
            self.item_activated.emit(payload)
