from __future__ import annotations

from app.context import AppContext
from app.ui.sidebar_stack import SidebarStack

from .chat import InterviewChatPage
from .job_page import JobInterviewPage
from .past_feedback_page import PastFeedbackPage
from .questions_page import InterviewQuestionsPage


class InterviewsPage(SidebarStack):
    def __init__(self, ctx: AppContext, parent=None):
        super().__init__(parent)
        self._questions_page = self.add_page("❓  Interview Questions", InterviewQuestionsPage(ctx.get_profile))
        self._job_page = self.add_page("🎯  Job-specific Interview", JobInterviewPage(ctx))
        self._chat_page = self.add_page("💬  Interview Practice", InterviewChatPage(ctx))
        self.add_page("📋  Past Feedback", PastFeedbackPage())

    def load(self, questions: list[dict] | None, template: list[dict] | None) -> None:
        """``questions`` None means "never saved" — seed the default question bank."""
        self._questions_page.load(questions)
        self._job_page.load_template(template)

    def get_questions_data(self) -> list[dict]:
        return self._questions_page.get_data()

    def get_template_data(self) -> list[dict]:
        return self._job_page.get_template_data()

    def commit_pending(self) -> None:
        self._job_page.commit_current()

    def flush_active_chat(self) -> None:
        self._chat_page.flush_active_chat()
