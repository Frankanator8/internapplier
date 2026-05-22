from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QStackedWidget,
    QVBoxLayout, QWidget,
)

from ..base import _label
from .chat_page import InterviewChatPage
from .job_page import JobInterviewPage
from .past_feedback_page import PastFeedbackPage
from .questions_page import InterviewQuestionsPage


class InterviewsPage(QWidget):
    def __init__(
        self,
        get_profile: Callable[[], dict] | None = None,
        get_applications: Callable[[], list[dict]] | None = None,
        get_research_cache: Callable[[], dict] | None = None,
        set_application_interviews: Callable[[int, list[dict]], None] | None = None,
        parent=None,
    ):
        super().__init__(parent)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._sidebar = QListWidget()
        self._sidebar.setObjectName("sidebar")
        self._sidebar.setFixedWidth(200)

        for label in (
            "❓  Interview Questions",
            "🎯  Job-specific Interview",
            "💬  Interview Practice",
            "📋  Past Feedback",
        ):
            item = QListWidgetItem(label)
            item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            self._sidebar.addItem(item)

        self._chat_page = InterviewChatPage(
            get_profile=get_profile,
            get_applications=get_applications,
            get_research_cache=get_research_cache,
        )

        self._questions_page = InterviewQuestionsPage(get_profile=get_profile)

        self._job_page: JobInterviewPage | None = None
        if get_applications is not None and set_application_interviews is not None:
            self._job_page = JobInterviewPage(
                get_profile=get_profile or (lambda: {}),
                get_applications=get_applications,
                get_research_cache=get_research_cache or (lambda: {}),
                set_application_interviews=set_application_interviews,
            )

        self._past_feedback_page = PastFeedbackPage()

        self._stack = QStackedWidget()
        self._stack.addWidget(self._questions_page)
        if self._job_page is not None:
            self._stack.addWidget(self._job_page)
        else:
            self._stack.addWidget(self._build_blank_page("Job-specific Interview"))
        self._stack.addWidget(self._chat_page)
        self._stack.addWidget(self._past_feedback_page)

        self._sidebar.currentRowChanged.connect(self._stack.setCurrentIndex)
        self._sidebar.setCurrentRow(0)

        outer.addWidget(self._sidebar)
        outer.addWidget(self._stack, 1)

    def _build_blank_page(self, title: str) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 16)
        layout.setSpacing(14)
        layout.addWidget(_label(title, "section-title"))
        coming = QLabel("Coming soon.")
        coming.setObjectName("hint")
        layout.addWidget(coming)
        layout.addStretch()
        return page

    def get_questions_data(self) -> list[dict]:
        return self._questions_page.get_data()

    def load_questions(self, value: list[dict] | None):
        self._questions_page.load(value)

    def load_template(self, value: list[dict] | None) -> None:
        if self._job_page is not None:
            self._job_page.load_template(value)

    def get_template_data(self) -> list[dict]:
        if self._job_page is None:
            return []
        return self._job_page.get_template_data()

    def commit_pending(self) -> None:
        if self._job_page is not None:
            self._job_page.commit_current()

    def flush_active_chat(self) -> None:
        if self._chat_page is not None:
            self._chat_page.flush_active_chat()

    def cleanup_threads(self) -> None:
        if self._chat_page is not None:
            self._chat_page.cleanup_threads()
        if self._questions_page is not None:
            self._questions_page.cleanup_threads()
