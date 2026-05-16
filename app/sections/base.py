from __future__ import annotations

from typing import Callable

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QScrollArea, QFrame, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox,
)
from PyQt6.QtCore import Qt, QObject, QThread, pyqtSignal


def _label(text: str, obj_name: str = "field-label") -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName(obj_name)
    return lbl


def _primary_btn(text: str, width: int | None = None) -> QPushButton:
    btn = QPushButton(text)
    btn.setObjectName("primary")
    if width:
        btn.setFixedWidth(width)
    return btn


def _secondary_btn(text: str, width: int | None = None) -> QPushButton:
    btn = QPushButton(text)
    btn.setObjectName("secondary")
    if width:
        btn.setFixedWidth(width)
    return btn


def _danger_btn(text: str, width: int | None = None) -> QPushButton:
    btn = QPushButton(text)
    btn.setObjectName("danger")
    if width:
        btn.setFixedWidth(width)
    return btn


def _icon_btn(text: str = "✕") -> QPushButton:
    btn = QPushButton(text)
    btn.setObjectName("icon-btn")
    btn.setFixedSize(24, 24)
    return btn


def _ai_btn() -> QPushButton:
    btn = QPushButton("✦")
    btn.setObjectName("ai-btn")
    btn.setFixedSize(24, 24)
    btn.setToolTip("Analyze this bullet with AI")
    return btn


class _AnalyzeWorker(QObject):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, bullet: str, context: dict):
        super().__init__()
        self._bullet = bullet
        self._context = context

    def run(self):
        from app.ai_provider import get_provider
        try:
            result = get_provider().analyze_bullet(self._bullet, self._context)
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


class BulletsWidget(QWidget):
    def __init__(
        self,
        bullets: list[str] | None = None,
        get_context: Callable[[], dict] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._get_context = get_context
        self._threads: list[QThread] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(4)

        header = QHBoxLayout()
        header.setSpacing(8)
        header.addWidget(_label("Bullets", "bullets-label"))
        header.addStretch()
        add_btn = _secondary_btn("+ Add Bullet", 110)
        header.addWidget(add_btn)
        layout.addLayout(header)

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("bullets-list")
        self.list_widget.setMaximumHeight(130)
        self.list_widget.setSpacing(2)
        layout.addWidget(self.list_widget)

        add_btn.clicked.connect(self._add_bullet)

        for b in (bullets or []):
            self._add_item(b)

    def _add_item(self, text: str = ""):
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(4, 2, 4, 2)
        row_layout.setSpacing(4)

        edit = QLineEdit(text)
        edit.setPlaceholderText("Describe what you did or built…")
        ai_btn = _ai_btn()
        remove_btn = _icon_btn("✕")

        row_layout.addWidget(edit)
        row_layout.addWidget(ai_btn)
        row_layout.addWidget(remove_btn)

        item = QListWidgetItem()
        item.setSizeHint(row.sizeHint())
        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, row)

        remove_btn.clicked.connect(lambda: self._remove_item(item))
        ai_btn.clicked.connect(lambda: self._analyze_item(edit, ai_btn))

    def _add_bullet(self):
        self._add_item("")

    def _remove_item(self, item: QListWidgetItem):
        self.list_widget.takeItem(self.list_widget.row(item))

    def _analyze_item(self, edit: QLineEdit, btn: QPushButton):
        bullet = edit.text().strip()
        if not bullet:
            QMessageBox.information(self, "Empty Bullet", "Please enter a bullet point before analyzing.")
            return

        context = self._get_context() if self._get_context else {}

        btn.setEnabled(False)
        btn.setText("…")

        worker = _AnalyzeWorker(bullet, context)
        thread = QThread(self)
        worker.moveToThread(thread)

        def on_finished(result: str):
            from app.analyze_dialog import AnalyzeDialog
            btn.setText("✦")
            btn.setEnabled(True)
            dlg = AnalyzeDialog(bullet, result, parent=self)
            dlg.exec()
            thread.quit()

        def on_error(msg: str):
            btn.setText("✦")
            btn.setEnabled(True)
            QMessageBox.warning(self, "AI Analysis Failed", msg)
            thread.quit()

        worker.finished.connect(on_finished)
        worker.error.connect(on_error)
        thread.started.connect(worker.run)
        thread.finished.connect(thread.deleteLater)

        self._threads.append(thread)
        thread.start()

    def get_bullets(self) -> list[str]:
        result = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            widget = self.list_widget.itemWidget(item)
            edit = widget.findChild(QLineEdit)
            if edit and edit.text().strip():
                result.append(edit.text().strip())
        return result


class CardPage(QWidget):
    section_title: str = "Section"
    add_label: str = ""

    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 16)
        outer.setSpacing(14)

        # Header row: title + add button
        header_row = QHBoxLayout()
        title = _label(self.section_title, "section-title")
        header_row.addWidget(title)
        header_row.addStretch()
        label = self.add_label or f"+ Add {self.section_title.rstrip('s')} Entry"
        add_btn = _primary_btn(label)
        add_btn.clicked.connect(self.add_entry)
        header_row.addWidget(add_btn)
        outer.addLayout(header_row)

        # Scroll area for cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)

        self._container = QWidget()
        self._container.setStyleSheet("background: transparent;")
        self._cards_layout = QVBoxLayout(self._container)
        self._cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._cards_layout.setSpacing(14)
        self._cards_layout.setContentsMargins(0, 0, 0, 16)
        scroll.setWidget(self._container)

    def _make_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        return card

    def _make_remove_btn(self, card: QFrame) -> QPushButton:
        btn = _danger_btn("Remove Entry")
        btn.clicked.connect(lambda: self._remove_card(card))
        return btn

    def _remove_card(self, card: QFrame):
        self._cards_layout.removeWidget(card)
        card.deleteLater()

    def clear(self):
        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def add_entry(self, data: dict | None = None):
        raise NotImplementedError

    def get_data(self) -> list[dict]:
        raise NotImplementedError


def make_field(label_text: str, line_edit: QLineEdit) -> QVBoxLayout:
    """Stack a small uppercase label above a QLineEdit."""
    vbox = QVBoxLayout()
    vbox.setSpacing(3)
    vbox.addWidget(_label(label_text))
    vbox.addWidget(line_edit)
    return vbox


def make_line_edit(placeholder: str = "") -> QLineEdit:
    edit = QLineEdit()
    edit.setPlaceholderText(placeholder)
    return edit
