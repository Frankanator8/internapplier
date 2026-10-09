from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout

from .widgets import icon_button, label, make_selectable


class FeedbackPanel(QFrame):
    """Dismissable quote box that accumulates streamed AI text.

    Without a title the body sits beside the ✕; with one, the title row holds
    the ✕ and the body spans the full width beneath it. ``changed`` fires
    whenever the content (and so the size) changes, for hosts that must
    re-measure — e.g. a ``QListWidget`` row.
    """

    changed = pyqtSignal()

    def __init__(self, *, with_title: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("analyze-quote")
        self.setVisible(False)
        self._text = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        self._title = label("", "analyze-quote-title") if with_title else None
        self._body = make_selectable(label("", "analyze-bullet-text", wrap=True))
        self._body.setAlignment(Qt.AlignmentFlag.AlignTop)
        dismiss = icon_button(tooltip="Dismiss")
        dismiss.clicked.connect(self.dismiss)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(6)
        top.addWidget(self._title or self._body, 1)
        top.addWidget(dismiss, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(top)
        if self._title is not None:
            layout.addWidget(self._body)

    def text(self) -> str:
        return self._text

    def begin(self, title: str = "") -> None:
        """Clear and show the panel, ready for ``append``."""
        if self._title is not None:
            self._title.setText(title)
        self.set_text("")
        self.setVisible(True)
        self.changed.emit()

    def set_title(self, title: str) -> None:
        if self._title is not None:
            self._title.setText(title)

    def append(self, delta: str) -> None:
        self.set_text(self._text + delta)

    def set_text(self, text: str) -> None:
        self._text = text
        self._body.setText(text.lstrip())
        self.changed.emit()

    def dismiss(self) -> None:
        self._text = ""
        self._body.setText("")
        self.setVisible(False)
        self.changed.emit()
