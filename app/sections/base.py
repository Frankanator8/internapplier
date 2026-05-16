from __future__ import annotations

import logging
from typing import Callable

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QScrollArea, QFrame, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox,
    QCompleter,
)
from PyQt6.QtCore import Qt, QObject, QThread, QStringListModel, pyqtSignal


_REWRITE_HEADERS = ("CRITIQUE:", "REWRITE A:", "REWRITE B:")


def _strip_line_prefix(line: str) -> str:
    """Strip markdown/list prefixes like '**', '1.', '- ', '#', leading spaces."""
    s = line.strip()
    changed = True
    while changed:
        changed = False
        for token in ("**", "__", "*", "#", "-", "•", ">"):
            if s.startswith(token):
                s = s[len(token):].lstrip()
                changed = True
        if s[:2].isdigit() if len(s) >= 2 and s[0].isdigit() and s[1] == "." else False:
            pass
        if len(s) >= 2 and s[0].isdigit() and s[1] in ".):":
            s = s[2:].lstrip()
            changed = True
        elif len(s) >= 3 and s[0].isdigit() and s[1].isdigit() and s[2] in ".):":
            s = s[3:].lstrip()
            changed = True
    return s


def _parse_rewrite_result(text: str) -> tuple[str, str, str]:
    """Split AI response into (critique, rewrite_a, rewrite_b)."""
    buckets: dict[str, list[str]] = {h: [] for h in _REWRITE_HEADERS}
    current: str | None = None
    for raw in text.split("\n"):
        cleaned = _strip_line_prefix(raw)
        upper = cleaned.upper()
        matched_header = None
        for h in _REWRITE_HEADERS:
            if upper.startswith(h):
                matched_header = h
                remainder = cleaned[len(h):].strip().strip("*_").strip()
                if remainder:
                    buckets[h].append(remainder)
                break
        if matched_header is not None:
            current = matched_header
            continue
        if current is not None and cleaned:
            buckets[current].append(cleaned.strip("*_").strip())
    return (
        " ".join(buckets["CRITIQUE:"]).strip(),
        " ".join(buckets["REWRITE A:"]).strip(),
        " ".join(buckets["REWRITE B:"]).strip(),
    )

logger = logging.getLogger(__name__)


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
        logger.info("_AnalyzeWorker.run — bullet=%r", self._bullet[:80])
        try:
            result = get_provider(tier="fast").analyze_bullet(self._bullet, self._context)
            logger.info("_AnalyzeWorker.run — success, result length=%d", len(result))
            self.finished.emit(result)
        except Exception as exc:
            logger.exception("_AnalyzeWorker.run — failed")
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
        self._workers: list[QObject] = []

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
        self.list_widget.setSpacing(4)
        self.list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_widget.setSizeAdjustPolicy(QListWidget.SizeAdjustPolicy.AdjustToContents)
        layout.addWidget(self.list_widget)

        add_btn.clicked.connect(self._add_bullet)

        for b in (bullets or []):
            self._add_item(b)

    def _add_item(self, text: str = ""):
        row = QWidget()
        row_v = QVBoxLayout(row)
        row_v.setContentsMargins(6, 4, 6, 4)
        row_v.setSpacing(4)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(4)

        edit = QLineEdit(text)
        edit.setPlaceholderText("Describe what you did or built…")
        ai_btn = _ai_btn()
        remove_btn = _icon_btn("✕")

        top.addWidget(edit)
        top.addWidget(ai_btn)
        top.addWidget(remove_btn)
        row_v.addLayout(top)

        suggestion_panel = QFrame()
        suggestion_panel.setObjectName("analyze-quote")
        suggestion_panel.setVisible(False)
        sp_layout = QVBoxLayout(suggestion_panel)
        sp_layout.setContentsMargins(10, 8, 10, 8)
        sp_layout.setSpacing(6)
        row_v.addWidget(suggestion_panel)

        row.setProperty("_edit", edit)
        row.setProperty("_panel", suggestion_panel)
        row.setProperty("_panel_layout", sp_layout)

        item = QListWidgetItem()
        item.setSizeHint(row.sizeHint())
        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, row)

        remove_btn.clicked.connect(lambda: self._remove_item(item))
        ai_btn.clicked.connect(lambda: self._analyze_item(item, row, edit, ai_btn))
        self._resize_to_contents()

    def _resize_to_contents(self):
        total = 2 * self.list_widget.frameWidth()
        spacing = self.list_widget.spacing()
        count = self.list_widget.count()
        for i in range(count):
            total += self.list_widget.sizeHintForRow(i) + 2 * spacing
        self.list_widget.setFixedHeight(max(total, 2 * self.list_widget.frameWidth()))

    def _add_bullet(self):
        self._add_item("")

    def _remove_item(self, item: QListWidgetItem):
        self.list_widget.takeItem(self.list_widget.row(item))
        self._resize_to_contents()

    def _analyze_item(self, item: QListWidgetItem, row: QWidget, edit: QLineEdit, btn: QPushButton):
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
            btn.setText("✦")
            btn.setEnabled(True)
            self._show_suggestions(item, row, result)
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
        self._workers.append(worker)
        thread.finished.connect(lambda: self._workers.remove(worker) if worker in self._workers else None)
        thread.start()

    def _clear_panel(self, layout: QVBoxLayout):
        while layout.count():
            child = layout.takeAt(0)
            w = child.widget()
            if w is not None:
                w.deleteLater()
            else:
                sub = child.layout()
                if sub is not None:
                    self._clear_panel(sub)

    def _hide_suggestions(self, item: QListWidgetItem, row: QWidget):
        panel: QFrame = row.property("_panel")
        layout: QVBoxLayout = row.property("_panel_layout")
        if panel is None:
            return
        self._clear_panel(layout)
        panel.setVisible(False)
        item.setSizeHint(row.sizeHint())
        self._resize_to_contents()

    def _show_suggestions(self, item: QListWidgetItem, row: QWidget, result: str):
        panel: QFrame = row.property("_panel")
        layout: QVBoxLayout = row.property("_panel_layout")
        if panel is None or layout is None:
            return

        self._clear_panel(layout)

        critique, rewrite_a, rewrite_b = _parse_rewrite_result(result)
        if not (critique or rewrite_a or rewrite_b):
            critique = result.strip()

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(4)
        title = QLabel("AI Suggestions")
        title.setObjectName("analyze-quote-title")
        header_row.addWidget(title)
        header_row.addStretch()
        dismiss_btn = _icon_btn("✕")
        dismiss_btn.setToolTip("Dismiss suggestions")
        dismiss_btn.clicked.connect(lambda: self._hide_suggestions(item, row))
        header_row.addWidget(dismiss_btn)
        layout.addLayout(header_row)

        if critique:
            crit_label = QLabel("Critique")
            crit_label.setObjectName("analyze-quote-title")
            layout.addWidget(crit_label)
            crit_body = QLabel(critique)
            crit_body.setObjectName("analyze-bullet-text")
            crit_body.setWordWrap(True)
            layout.addWidget(crit_body)

        for letter, rewrite in (("A", rewrite_a), ("B", rewrite_b)):
            if not rewrite:
                continue
            r_label = QLabel(f"Rewrite {letter}")
            r_label.setObjectName("analyze-quote-title")
            layout.addWidget(r_label)
            r_text = QLabel(rewrite)
            r_text.setObjectName("analyze-bullet-text")
            r_text.setWordWrap(True)
            layout.addWidget(r_text)

        panel.setVisible(True)
        width = self.list_widget.viewport().width()
        if width > 0:
            row.setFixedWidth(width)
        row.layout().activate()
        row.adjustSize()
        hint = row.sizeHint()
        if width > 0:
            hint.setWidth(width)
        item.setSizeHint(hint)
        self.list_widget.doItemsLayout()
        self._resize_to_contents()

    def get_bullets(self) -> list[str]:
        result = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            widget = self.list_widget.itemWidget(item)
            edit = widget.findChild(QLineEdit)
            if edit and edit.text().strip():
                result.append(edit.text().strip())
        return result


class CoursesWidget(QWidget):
    def __init__(
        self,
        courses: list[dict] | None = None,
        get_common_skills: Callable[[], list[str]] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._get_common_skills = get_common_skills

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(4)

        header = QHBoxLayout()
        header.setSpacing(8)
        header.addWidget(_label("Coursework", "bullets-label"))
        header.addStretch()
        add_btn = _secondary_btn("+ Add Course", 120)
        header.addWidget(add_btn)
        layout.addLayout(header)

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("courses-list")
        self.list_widget.setMaximumHeight(260)
        self.list_widget.setSpacing(2)
        layout.addWidget(self.list_widget)

        add_btn.clicked.connect(lambda: self._add_item())

        for c in (courses or []):
            self._add_item(
                c.get("name", ""),
                c.get("grade", ""),
                c.get("skills", []),
            )

    def _add_item(self, name: str = "", grade: str = "", skills: list[str] | None = None):
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(4, 2, 4, 2)
        row_layout.setSpacing(6)

        name_edit = QLineEdit(name)
        name_edit.setPlaceholderText("CS 189: Machine Learning")
        grade_edit = QLineEdit(grade)
        grade_edit.setPlaceholderText("A")
        grade_edit.setFixedWidth(60)
        chips = ChipsWidget(
            items=skills or [],
            label="Skills",
            get_common_skills=self._get_common_skills,
        )
        remove_btn = _icon_btn("✕")

        row_layout.addWidget(name_edit, 3)
        row_layout.addWidget(grade_edit, 0)
        row_layout.addWidget(chips, 2)
        row_layout.addWidget(remove_btn, 0)

        item = QListWidgetItem()
        item.setSizeHint(row.sizeHint())
        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, row)

        row.setProperty("_name", name_edit)
        row.setProperty("_grade", grade_edit)
        row.setProperty("_skills", chips)

        remove_btn.clicked.connect(lambda: self._remove_item(item))

    def _remove_item(self, item: QListWidgetItem):
        self.list_widget.takeItem(self.list_widget.row(item))

    def get_courses(self) -> list[dict]:
        result = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            row = self.list_widget.itemWidget(item)
            if row is None:
                continue
            name_edit: QLineEdit = row.property("_name")
            grade_edit: QLineEdit = row.property("_grade")
            chips: ChipsWidget = row.property("_skills")
            name = name_edit.text().strip()
            if not name:
                continue
            result.append({
                "name": name,
                "grade": grade_edit.text().strip(),
                "skills": chips.get_items(),
            })
        return result


class ChipsWidget(QWidget):
    def __init__(
        self,
        items: list[str] | None = None,
        on_add: Callable[[str], None] | None = None,
        label: str = "Skills",
        get_common_skills: Callable[[], list[str]] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._on_add = on_add
        self._get_common_skills = get_common_skills
        self._items: list[str] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(4)

        header = QHBoxLayout()
        header.setSpacing(8)
        header.addWidget(_label(label, "bullets-label"))
        header.addStretch()
        layout.addLayout(header)

        input_row = QHBoxLayout()
        input_row.setSpacing(6)
        self._input = QLineEdit()
        self._input.setPlaceholderText("Add a skill and press Enter…")
        self._input.returnPressed.connect(self._add_from_input)

        self._completer_model = QStringListModel([], self)
        completer = QCompleter(self._completer_model, self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.activated.connect(self._on_completer_activated)
        self._input.setCompleter(completer)
        self._input.textEdited.connect(lambda _t: self._refresh_completer())
        add_btn = _secondary_btn("+", 32)
        add_btn.clicked.connect(self._add_from_input)
        input_row.addWidget(self._input)
        input_row.addWidget(add_btn)
        layout.addLayout(input_row)

        self._chips_host = QWidget()
        self._chips_layout = QHBoxLayout(self._chips_host)
        self._chips_layout.setContentsMargins(0, 2, 0, 2)
        self._chips_layout.setSpacing(6)
        self._chips_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setFixedHeight(44)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(self._chips_host)
        layout.addWidget(scroll)

        for s in (items or []):
            self._add_chip(s, fire_callback=False)

    def _add_from_input(self):
        text = self._input.text().strip()
        if not text:
            return
        self._add_chip(text, fire_callback=True)
        self._input.clear()

    def _on_completer_activated(self, text: str):
        text = text.strip()
        if not text:
            return
        self._add_chip(text, fire_callback=True)
        self._input.clear()

    def _refresh_completer(self):
        if not self._get_common_skills:
            return
        existing = {t.lower() for t in self._items}
        suggestions = [s for s in self._get_common_skills() if s.lower() not in existing]
        if suggestions != self._completer_model.stringList():
            self._completer_model.setStringList(suggestions)

    def _add_chip(self, text: str, fire_callback: bool):
        if any(t.lower() == text.lower() for t in self._items):
            return
        self._items.append(text)

        chip = QFrame()
        chip.setObjectName("chip")
        chip.setStyleSheet(
            "QFrame#chip { background: #eef3fb; border: 1px solid #cfd8e3;"
            " border-radius: 11px; }"
            "QLabel { color: #1d1d1d; font-size: 12px; }"
        )
        chip_layout = QHBoxLayout(chip)
        chip_layout.setContentsMargins(8, 2, 4, 2)
        chip_layout.setSpacing(4)
        lbl = QLabel(text)
        remove = QPushButton("✕")
        remove.setObjectName("icon-btn")
        remove.setFixedSize(18, 18)
        remove.setStyleSheet("border: none; background: transparent; color: #6b7280;")
        chip_layout.addWidget(lbl)
        chip_layout.addWidget(remove)

        insert_at = self._chips_layout.count() - 1
        self._chips_layout.insertWidget(insert_at, chip)

        remove.clicked.connect(lambda: self._remove_chip(chip, text))

        if fire_callback and self._on_add:
            self._on_add(text)
        self._refresh_completer()

    def _remove_chip(self, chip: QFrame, text: str):
        self._items = [t for t in self._items if t != text]
        self._chips_layout.removeWidget(chip)
        chip.deleteLater()
        self._refresh_completer()

    def get_items(self) -> list[str]:
        return list(self._items)


class CardPage(QWidget):
    section_title: str = "Section"
    add_label: str = ""
    on_skill_added: Callable[[str], None] | None = None
    get_common_skills: Callable[[], list[str]] | None = None

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
