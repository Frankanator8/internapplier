from __future__ import annotations

from app.context import AppContext
from app.ui.sidebar_stack import SidebarStack

from .answer_question_page import AnswerQuestionPage
from .generate_resume_page import GenerateResumePage
from .library_page import LibraryPage
from .research_page import ResearchPage
from .resume_builder_page import ResumeBuilderPage


class ApplierPage(SidebarStack):
    """The Applier tab. Sub-pages refresh themselves whenever they're shown,
    since applications, the profile and saved resumes change elsewhere."""

    def __init__(self, ctx: AppContext, parent=None):
        super().__init__(parent, refresh_on_show=True)
        self.add_page("📄  Generate Resume", GenerateResumePage(ctx))
        self.add_page("🧩  Resume Builder", ResumeBuilderPage(ctx))
        self.add_page("🔍  Research Company", ResearchPage(ctx))
        self.add_page("📚  Library", LibraryPage())
        self.add_page("❓  Answer Question", AnswerQuestionPage(ctx))
