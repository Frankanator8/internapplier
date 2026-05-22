from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
    QScrollArea, QStackedWidget, QStatusBar, QVBoxLayout, QWidget,
)

from .ai_model_page import AiModelMixin
from .general_page import GeneralMixin
from .prompts_page import PromptsMixin
from .resume_page import ResumeMixin


class SettingsPage(
    AiModelMixin,
    ResumeMixin,
    PromptsMixin,
    GeneralMixin,
    QWidget,
):
    def __init__(self, status_bar: QStatusBar | None = None):
        super().__init__()
        self._status_bar = status_bar

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._sidebar = QListWidget()
        self._sidebar.setObjectName("sidebar")
        self._sidebar.setFixedWidth(200)

        for label in ("⚙️  General", "🤖  AI Model", "📄  Resume", "📝  System Prompts"):
            item = QListWidgetItem(label)
            item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            self._sidebar.addItem(item)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_general_page())
        self._stack.addWidget(self._build_ai_model_page())
        self._stack.addWidget(self._build_resume_page())
        self._stack.addWidget(self._build_prompts_page())

        self._sidebar.currentRowChanged.connect(self._stack.setCurrentIndex)
        self._sidebar.setCurrentRow(0)

        outer.addWidget(self._sidebar)
        outer.addWidget(self._stack, 1)

    def _wrap_scroll(self, card: QWidget) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        layout.addWidget(scroll)

        inner = QWidget()
        scroll.setWidget(inner)

        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(40, 40, 40, 40)
        inner_layout.setSpacing(0)
        inner_layout.addWidget(card)
        inner_layout.addStretch()
        return page

    def _resize_edit(self, edit: QLineEdit, text: str) -> None:
        fm = edit.fontMetrics()
        text_px = fm.horizontalAdvance(text or edit.placeholderText())
        edit.setFixedWidth(max(120, min(text_px + 24, 400)))
