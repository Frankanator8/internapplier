"""Small widget factories and helpers shared across every page.

Styling is driven by objectName selectors in ``app/style.py`` — these helpers
exist so each page sets the same names and margins the same way.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterator, Literal

from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QDesktopServices, QFont, QGuiApplication, QTextCursor
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLayout, QLineEdit, QListWidget, QMessageBox,
    QPlainTextEdit, QPushButton, QScrollArea, QSplitter, QTextEdit, QVBoxLayout,
    QWidget,
)

ButtonKind = Literal["primary", "secondary", "danger"]
StatusState = Literal["ok", "error", "neutral"]

PAGE_MARGINS = (28, 24, 28, 16)
PAGE_SPACING = 14


# ── Labels ──────────────────────────────────────────────────────
def label(text: str = "", name: str = "field-label", *, wrap: bool = False) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName(name)
    if wrap:
        lbl.setWordWrap(True)
    return lbl


def hint(text: str) -> QLabel:
    """Word-wrapped helper text shown beneath a control."""
    return label(text, "hint", wrap=True)


def status_label(state: StatusState = "neutral") -> QLabel:
    return label("", f"status-{state}", wrap=True)


def make_selectable(lbl: QLabel) -> QLabel:
    lbl.setTextInteractionFlags(
        Qt.TextInteractionFlag.TextSelectableByMouse
        | Qt.TextInteractionFlag.TextSelectableByKeyboard
    )
    lbl.setCursor(Qt.CursorShape.IBeamCursor)
    return lbl


def repolish(widget: QWidget) -> None:
    """Re-apply the stylesheet after an objectName/property change."""
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)


def set_status(lbl: QLabel, state: StatusState, text: str | None = None) -> None:
    """Restyle a status label (and optionally set its text)."""
    lbl.setObjectName(f"status-{state}")
    repolish(lbl)
    if text is not None:
        lbl.setText(text)


def flash_status(lbl: QLabel, text: str = "✓  Saved", ms: int = 3000) -> None:
    """Show a success message that clears itself after ``ms``."""
    set_status(lbl, "ok", text)
    QTimer.singleShot(ms, lambda: lbl.setText(""))


# ── Buttons ─────────────────────────────────────────────────────
def button(text: str, kind: ButtonKind = "primary", width: int | None = None) -> QPushButton:
    btn = QPushButton(text)
    btn.setObjectName(kind)
    if width:
        btn.setFixedWidth(width)
    return btn


class BusyButton(QPushButton):
    """Button that disables itself and shows ``busy_text`` while work runs."""

    def __init__(self, text: str, busy_text: str, kind: ButtonKind = "primary", width: int | None = None):
        super().__init__(text)
        self.setObjectName(kind)
        if width:
            self.setFixedWidth(width)
        self._idle_text = text
        self._busy_text = busy_text

    def set_busy(self, busy: bool) -> None:
        self.setEnabled(not busy)
        self.setText(self._busy_text if busy else self._idle_text)


def icon_button(text: str = "✕", size: int = 24, tooltip: str = "", name: str = "icon-btn") -> QPushButton:
    btn = QPushButton(text)
    btn.setObjectName(name)
    btn.setFixedSize(size, size)
    if tooltip:
        btn.setToolTip(tooltip)
    return btn


# ── Inputs ──────────────────────────────────────────────────────
def line_edit(placeholder: str = "", text: str = "") -> QLineEdit:
    edit = QLineEdit(text)
    edit.setPlaceholderText(placeholder)
    return edit


def field(label_text: str, widget: QWidget) -> QVBoxLayout:
    """Stack a small field label above an input."""
    vbox = QVBoxLayout()
    vbox.setSpacing(3)
    vbox.addWidget(label(label_text))
    vbox.addWidget(widget)
    return vbox


def mono_font() -> QFont:
    font = QFont("Menlo")
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setPointSize(11)
    return font


def append_stream_text(edit: QPlainTextEdit | QTextEdit, text: str) -> None:
    """Append streamed text at the end and keep the view pinned to the bottom."""
    edit.moveCursor(QTextCursor.MoveOperation.End)
    edit.insertPlainText(text)
    sb = edit.verticalScrollBar()
    sb.setValue(sb.maximum())


# ── Containers ──────────────────────────────────────────────────
def card(name: str = "card") -> QFrame:
    frame = QFrame()
    frame.setObjectName(name)
    return frame


def group_card(title: str, *trailing: QWidget) -> tuple[QFrame, QVBoxLayout]:
    """Card with a medium heading (and optional widgets right of it)."""
    frame = card()
    vbox = QVBoxLayout(frame)
    vbox.setContentsMargins(20, 18, 20, 18)
    vbox.setSpacing(12)
    vbox.addLayout(section_header(title, *trailing, name="card-heading"))
    return frame, vbox


def vbox_widget(
    margins: tuple[int, int, int, int] = (0, 0, 0, 0), spacing: int = 6,
) -> tuple[QWidget, QVBoxLayout]:
    """A plain widget with a vertical layout, for splitter panes and columns."""
    w = QWidget()
    layout = QVBoxLayout(w)
    layout.setContentsMargins(*margins)
    layout.setSpacing(spacing)
    return w, layout


def list_pane(
    caption: str,
    *,
    name: str = "company-cache-list",
    margins: tuple[int, int, int, int] = (16, 16, 8, 0),
    width: tuple[int, int] = (200, 320),
) -> tuple[QWidget, QVBoxLayout, QListWidget]:
    """Captioned list column for the left side of a list/detail splitter."""
    pane, layout = vbox_widget(margins)
    pane.setMinimumWidth(width[0])
    pane.setMaximumWidth(width[1])
    layout.addWidget(label(caption))
    lst = QListWidget()
    lst.setObjectName(name)
    layout.addWidget(lst, 1)
    return pane, layout, lst


def hsplitter(*panes: QWidget, sizes: list[int]) -> QSplitter:
    """Horizontal splitter whose panes can't be collapsed away."""
    splitter = QSplitter(Qt.Orientation.Horizontal)
    splitter.setChildrenCollapsible(False)
    for pane in panes:
        splitter.addWidget(pane)
    splitter.setSizes(sizes)
    return splitter


def hline() -> QFrame:
    line = QFrame()
    line.setObjectName("hline")
    line.setFrameShape(QFrame.Shape.HLine)
    return line


def page_layout(widget: QWidget) -> QVBoxLayout:
    """Standard outer layout for a top-level section page."""
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(*PAGE_MARGINS)
    layout.setSpacing(PAGE_SPACING)
    return layout


def set_titled_content(page: QWidget, title: str, content: QWidget) -> None:
    """Lay ``page`` out as a section title above ``content``."""
    layout = page_layout(page)
    layout.addWidget(label(title, "section-title"))
    layout.addWidget(content, 1)


def section_header(title: str, *trailing: QWidget, name: str = "section-title") -> QHBoxLayout:
    """Title on the left, stretch, then ``trailing`` widgets on the right."""
    row = QHBoxLayout()
    row.addWidget(label(title, name))
    row.addStretch()
    for w in trailing:
        row.addWidget(w)
    return row


def scroll_area(
    margins: tuple[int, int, int, int] = (0, 0, 0, 16),
    spacing: int = PAGE_SPACING,
) -> tuple[QScrollArea, QVBoxLayout]:
    """Frameless scroll area whose transparent inner widget stacks top-aligned."""
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    inner = QWidget()
    inner.setObjectName("scroll-inner")
    layout = QVBoxLayout(inner)
    layout.setAlignment(Qt.AlignmentFlag.AlignTop)
    layout.setContentsMargins(*margins)
    layout.setSpacing(spacing)
    scroll.setWidget(inner)
    return scroll, layout


# ── Layout utilities ────────────────────────────────────────────
def clear_layout(layout: QLayout) -> None:
    """Remove and delete every widget (recursing into nested layouts)."""
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w is not None:
            w.deleteLater()
        elif item.layout() is not None:
            clear_layout(item.layout())


def iter_widgets(layout: QLayout) -> Iterator[QWidget]:
    for i in range(layout.count()):
        w = layout.itemAt(i).widget()
        if w is not None:
            yield w


# ── Desktop integration ─────────────────────────────────────────
def confirm(parent: QWidget, title: str, text: str) -> bool:
    """Yes/Cancel question defaulting to Cancel."""
    reply = QMessageBox.question(
        parent, title, text,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        QMessageBox.StandardButton.Cancel,
    )
    return reply == QMessageBox.StandardButton.Yes


def open_path(path: str | Path) -> None:
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


def copy_text(text: str) -> None:
    QGuiApplication.clipboard().setText(text)


class SecretEdit(QWidget):
    """Password-style line edit with a Show/Hide toggle beside it."""

    def __init__(self, text: str = "", placeholder: str = "", parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self.edit = line_edit(placeholder, text)
        self.edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._toggle = button("Show", width=70)
        self._toggle.clicked.connect(self._toggle_visible)
        row.addWidget(self.edit)
        row.addWidget(self._toggle)

    def text(self) -> str:
        return self.edit.text()

    def _toggle_visible(self) -> None:
        hidden = self.edit.echoMode() == QLineEdit.EchoMode.Password
        self.edit.setEchoMode(QLineEdit.EchoMode.Normal if hidden else QLineEdit.EchoMode.Password)
        self._toggle.setText("Hide" if hidden else "Show")
