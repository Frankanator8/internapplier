from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout, QListWidget, QListWidgetItem, QStackedWidget, QWidget,
)

SIDEBAR_WIDTH = 200


class SidebarStack(QWidget):
    """Left navigation list switching between stacked sub-pages.

    A page that defines ``on_shown()`` gets it called whenever it becomes the
    visible page. With ``refresh_on_show`` it is also called each time this
    container itself is shown (e.g. its tab is re-selected), for pages whose
    data can change from elsewhere in the app.
    """

    def __init__(self, parent: QWidget | None = None, *, refresh_on_show: bool = False):
        super().__init__(parent)
        self._refresh_on_show = refresh_on_show

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._sidebar = QListWidget()
        self._sidebar.setObjectName("sidebar")
        self._sidebar.setFixedWidth(SIDEBAR_WIDTH)
        self._stack = QStackedWidget()
        self._sidebar.currentRowChanged.connect(self._on_row_changed)

        outer.addWidget(self._sidebar)
        outer.addWidget(self._stack, 1)

    def add_page(self, label: str, page: QWidget) -> QWidget:
        item = QListWidgetItem(label)
        item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._sidebar.addItem(item)
        self._stack.addWidget(page)
        if self._sidebar.count() == 1:
            # Select the first page silently: pages load their own data on
            # construction, so there's nothing to refresh yet.
            self._sidebar.blockSignals(True)
            self._sidebar.setCurrentRow(0)
            self._sidebar.blockSignals(False)
            self._stack.setCurrentIndex(0)
        return page

    def current_page(self) -> QWidget | None:
        return self._stack.currentWidget()

    def set_current(self, page: QWidget) -> None:
        self._sidebar.setCurrentRow(self._stack.indexOf(page))

    def _on_row_changed(self, row: int) -> None:
        self._stack.setCurrentIndex(row)
        self._notify_shown()

    def _notify_shown(self) -> None:
        on_shown = getattr(self.current_page(), "on_shown", None)
        if callable(on_shown):
            on_shown()

    def showEvent(self, event):  # noqa: N802 (Qt API)
        super().showEvent(event)
        if self._refresh_on_show:
            self._notify_shown()
