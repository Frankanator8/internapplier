from __future__ import annotations

import json
import logging
from typing import Callable

from PyQt6.QtCore import QObject, QSize, QThread, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QScrollArea, QStackedWidget,
    QTextEdit, QVBoxLayout, QWidget,
)

from .base import _icon_btn, _label, _primary_btn, _secondary_btn

logger = logging.getLogger(__name__)


class _GradeWorker(QObject):
    stream = pyqtSignal(str)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(
        self,
        question: str,
        response: str,
        profile: dict,
        company_name: str | None = None,
        company_research: dict | None = None,
        job_description: str | None = None,
    ):
        super().__init__()
        self._question = question
        self._response = response
        self._profile = profile
        self._company_name = company_name
        self._company_research = company_research
        self._job_description = job_description

    def run(self):
        from api.ai_provider import get_provider
        logger.info(
            "_GradeWorker.run — question=%r response_chars=%d company=%r",
            self._question[:80], len(self._response), self._company_name,
        )
        try:
            for chunk in get_provider().grade_interview_response_stream(
                question=self._question,
                response=self._response,
                profile=self._profile,
                company_name=self._company_name,
                company_research=self._company_research,
                job_description=self._job_description,
            ):
                self.stream.emit(chunk)
            self.finished.emit()
        except Exception as exc:
            logger.exception("_GradeWorker.run — failed")
            self.error.emit(str(exc))


_DEFAULT_QUESTIONS: list[str] = [
    "Tell me about yourself",
    "Greatest strength / a time you took initiative / ownership",
    "Tell me about a time you faced a challenge and pushed through",
    "Tell me about a time you worked well on a team",
    "Walk me through a past project",
    "How did you teach someone something?",
    "Tell me about a conflict you handled",
    "What are your goals for the future?",
    "What gives you motivation?",
    "Tell me about a time you made a mistake",
    "Leadership — tell me about a time you led",
    "Tell me about a time you learned something new (tech)",
    "How would you address a bug in prod?",
    "Why this company / role?",
    "Greatest weakness",
    "Tell me about a time you received tough feedback",
    "A time you disagreed with a manager or teammate",
    "Why should we hire you?",
]


class InterviewQuestionsPage(QWidget):
    def __init__(
        self,
        get_profile: Callable[[], dict] | None = None,
        get_job_context: Callable[[], dict | None] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._get_profile = get_profile or (lambda: {})
        self._get_job_context = get_job_context
        self._threads: list[QThread] = []
        self._workers: list[QObject] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 16)
        outer.setSpacing(14)

        header_row = QHBoxLayout()
        header_row.addWidget(_label("Interview Questions", "section-title"))
        header_row.addStretch()
        top_add_btn = _primary_btn("+ Add Question")
        top_add_btn.clicked.connect(self._add_blank)
        header_row.addWidget(top_add_btn)
        outer.addLayout(header_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll, 1)

        self._container = QWidget()
        self._container.setStyleSheet("background: transparent;")
        self._cards_layout = QVBoxLayout(self._container)
        self._cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._cards_layout.setSpacing(14)
        self._cards_layout.setContentsMargins(0, 0, 0, 16)
        scroll.setWidget(self._container)

        bottom_row = QHBoxLayout()
        bottom_row.addStretch()
        bottom_add_btn = _primary_btn("+ Add Question")
        bottom_add_btn.clicked.connect(self._add_blank)
        bottom_row.addWidget(bottom_add_btn)
        bottom_row.addStretch()
        outer.addLayout(bottom_row)

    def _add_blank(self):
        self.add_entry({"question": "", "answer": ""})

    def add_entry(self, data: dict | None = None):
        data = data or {}
        card = QFrame()
        card.setObjectName("card")
        vbox = QVBoxLayout(card)
        vbox.setContentsMargins(20, 18, 20, 16)
        vbox.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(8)
        question_edit = QLineEdit(data.get("question", ""))
        question_edit.setPlaceholderText("Question…")
        question_edit.setStyleSheet(
            "QLineEdit { font-size: 15px; font-weight: 600; border: none;"
            " background: transparent; padding: 2px 0; }"
        )
        remove_btn = _icon_btn("✕")
        remove_btn.setToolTip("Remove question")
        top.addWidget(question_edit, 1)
        top.addWidget(remove_btn, 0, Qt.AlignmentFlag.AlignTop)
        vbox.addLayout(top)

        answer_row = QHBoxLayout()
        answer_row.setSpacing(8)
        answer_edit = QTextEdit()
        answer_edit.setPlaceholderText("Draft your answer here…")
        answer_edit.setPlainText(data.get("answer", ""))
        answer_edit.setMinimumHeight(160)
        answer_edit.setStyleSheet("QTextEdit { font-size: 15px; }")
        answer_row.addWidget(answer_edit, 1)

        grade_btn = _secondary_btn("✦ AI Feedback", 110)
        grade_btn.setToolTip("Get AI feedback on your answer")
        answer_row.addWidget(grade_btn, 0, Qt.AlignmentFlag.AlignTop)
        vbox.addLayout(answer_row)

        fb_panel = QFrame()
        fb_panel.setObjectName("analyze-quote")
        fb_panel.setVisible(False)
        fb_layout = QVBoxLayout(fb_panel)
        fb_layout.setContentsMargins(10, 8, 10, 8)
        fb_layout.setSpacing(6)

        fb_header = QHBoxLayout()
        fb_header.setContentsMargins(0, 0, 0, 0)
        fb_header.setSpacing(6)
        fb_title = QLabel("")
        fb_title.setObjectName("analyze-quote-title")
        fb_header.addWidget(fb_title, 1)
        fb_dismiss = _icon_btn("✕")
        fb_dismiss.setToolTip("Dismiss")
        fb_header.addWidget(fb_dismiss, 0, Qt.AlignmentFlag.AlignTop)
        fb_layout.addLayout(fb_header)

        fb_body = QLabel("")
        fb_body.setObjectName("analyze-bullet-text")
        fb_body.setWordWrap(True)
        fb_body.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        fb_body.setCursor(Qt.CursorShape.IBeamCursor)
        fb_body.setAlignment(Qt.AlignmentFlag.AlignTop)
        fb_layout.addWidget(fb_body)

        vbox.addWidget(fb_panel)

        card.setProperty("_question", question_edit)
        card.setProperty("_answer", answer_edit)
        card.setProperty("_fb_panel", fb_panel)
        card.setProperty("_fb_title", fb_title)
        card.setProperty("_fb_body", fb_body)
        card.setProperty("_fb_buffer", "")

        fb_dismiss.clicked.connect(lambda: self._hide_feedback(card))
        grade_btn.clicked.connect(
            lambda _checked=False, c=card, b=grade_btn: self._grade(c, b)
        )
        remove_btn.clicked.connect(lambda: self._remove_card(card))

        self._cards_layout.addWidget(card)

    def _grade(self, card: QFrame, grade_btn: QPushButton):
        question_edit: QLineEdit = card.property("_question")
        answer_edit: QTextEdit = card.property("_answer")
        question = question_edit.text().strip()
        answer = answer_edit.toPlainText().strip()
        if not question or not answer:
            return

        fb_panel: QFrame = card.property("_fb_panel")
        fb_title: QLabel = card.property("_fb_title")
        fb_body: QLabel = card.property("_fb_body")

        card.setProperty("_fb_buffer", "")
        fb_title.setText("GENERATING…")
        fb_body.setText("")
        fb_panel.setVisible(True)

        grade_btn.setEnabled(False)
        grade_btn.setText("…")

        profile = self._get_profile()
        ctx = self._get_job_context() if self._get_job_context else None
        worker = _GradeWorker(
            question,
            answer,
            profile,
            company_name=(ctx or {}).get("company_name"),
            company_research=(ctx or {}).get("company_research"),
            job_description=(ctx or {}).get("job_description"),
        )
        thread = QThread(self)
        worker.moveToThread(thread)

        def on_chunk(delta: str):
            buf = (card.property("_fb_buffer") or "") + delta
            card.setProperty("_fb_buffer", buf)

        def on_finished():
            grade_btn.setText("✦ AI Feedback")
            grade_btn.setEnabled(True)
            buf = card.property("_fb_buffer") or ""
            try:
                parsed = json.loads(buf)
                score = parsed.get("score")
                feedback = parsed.get("feedback", "") or ""
                score_str = (
                    f"{score:g}" if isinstance(score, (int, float)) else str(score)
                )
                fb_title.setText(f"AI FEEDBACK · SCORE {score_str}/10")
                fb_body.setText(feedback if feedback else "No feedback — answer looks strong.")
            except (ValueError, TypeError):
                fb_title.setText("AI FEEDBACK")
                fb_body.setText(buf)
            thread.quit()

        def on_error(msg: str):
            grade_btn.setText("✦ AI Feedback")
            grade_btn.setEnabled(True)
            fb_title.setText("AI FEEDBACK · ERROR")
            fb_body.setText(msg)
            thread.quit()

        worker.stream.connect(on_chunk)
        worker.finished.connect(on_finished)
        worker.error.connect(on_error)
        thread.started.connect(worker.run)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(
            lambda: self._workers.remove(worker) if worker in self._workers else None
        )
        self._threads.append(thread)
        self._workers.append(worker)
        thread.start()

    def _hide_feedback(self, card: QFrame):
        fb_panel: QFrame = card.property("_fb_panel")
        if fb_panel is not None:
            fb_panel.setVisible(False)
        card.setProperty("_fb_buffer", "")

    def _remove_card(self, card: QFrame):
        self._cards_layout.removeWidget(card)
        card.deleteLater()

    def _clear(self):
        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def get_data(self) -> list[dict]:
        result = []
        for i in range(self._cards_layout.count()):
            card = self._cards_layout.itemAt(i).widget()
            if card is None:
                continue
            question_edit: QLineEdit = card.property("_question")
            answer_edit: QTextEdit = card.property("_answer")
            question = question_edit.text().strip()
            answer = answer_edit.toPlainText().strip()
            if not question and not answer:
                continue
            result.append({"question": question, "answer": answer})
        return result

    def load(self, value: list[dict] | None):
        self._clear()
        if value is None:
            for q in _DEFAULT_QUESTIONS:
                self.add_entry({"question": q, "answer": ""})
            return
        for entry in value:
            self.add_entry(entry)


class JobInterviewPage(QWidget):
    """Per-job interview prep: Template + jobs sidebar, shared card editor."""

    def __init__(
        self,
        get_profile: Callable[[], dict],
        get_applications: Callable[[], list[dict]],
        get_research_cache: Callable[[], dict],
        set_application_interviews: Callable[[int, list[dict]], None],
        parent=None,
    ):
        super().__init__(parent)
        self._get_profile = get_profile
        self._get_applications = get_applications
        self._get_research_cache = get_research_cache
        self._set_application_interviews = set_application_interviews

        self._template: list[dict] = []
        self._current_kind: str = "template"   # "template" or "job"
        self._current_job_index: int | None = None
        self._suppress_selection = False

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._sidebar = QListWidget()
        self._sidebar.setObjectName("sidebar")
        self._sidebar.setFixedWidth(220)
        outer.addWidget(self._sidebar)

        self._editor = InterviewQuestionsPage(
            get_profile=get_profile,
            get_job_context=self._current_job_context,
        )
        outer.addWidget(self._editor, 1)

        self._sidebar.currentRowChanged.connect(self._on_row_changed)

    # ── public API ────────────────────────────────────────────────
    def load_template(self, value: list[dict] | None):
        self._template = list(value or [])
        # Initial display: rebuild sidebar and show Template at row 0.
        self._rebuild_sidebar(initial=True)

    def get_template_data(self) -> list[dict]:
        # Make sure any in-flight edits to Template are flushed first.
        self.commit_current()
        return list(self._template)

    def commit_current(self) -> None:
        """Flush the editor's current contents back to its source."""
        data = self._editor.get_data()
        if self._current_kind == "template":
            self._template = data
        elif self._current_kind == "job" and self._current_job_index is not None:
            self._set_application_interviews(self._current_job_index, data)

    def showEvent(self, event):  # noqa: N802 (Qt API)
        super().showEvent(event)
        # Applications may have changed elsewhere; refresh the sidebar.
        self._rebuild_sidebar(initial=False)

    # ── internals ─────────────────────────────────────────────────
    def _current_job_context(self) -> dict | None:
        if self._current_kind != "job" or self._current_job_index is None:
            return None
        apps = self._get_applications()
        if not (0 <= self._current_job_index < len(apps)):
            return None
        entry = apps[self._current_job_index]
        from .applier import _research_from_cache
        research = _research_from_cache(self._get_research_cache() or {}, entry.get("company", ""))
        return {
            "company_name": entry.get("company") or None,
            "company_research": research,
            "job_description": entry.get("description") or None,
        }

    def _rebuild_sidebar(self, initial: bool) -> None:
        # Remember selection (kind + job index) so we restore it after rebuild.
        prev_kind = self._current_kind
        prev_index = self._current_job_index

        self._suppress_selection = True
        try:
            self._sidebar.clear()

            # Row 0: Template (always present).
            tmpl_item = QListWidgetItem("📌  Template")
            tmpl_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            self._sidebar.addItem(tmpl_item)

            apps = self._get_applications()
            if apps:
                # Row 1: visual divider (non-selectable, non-interactive).
                divider = QListWidgetItem("")
                divider.setFlags(Qt.ItemFlag.NoItemFlags)
                divider.setSizeHint(QSize(0, 8))
                self._sidebar.addItem(divider)

                for entry in apps:
                    company = (entry.get("company") or "").strip()
                    role = (entry.get("role") or "").strip()
                    if company and role:
                        label = f"{company} — {role}"
                    elif company or role:
                        label = company or role
                    else:
                        label = "(untitled job)"
                    item = QListWidgetItem(label)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                    self._sidebar.addItem(item)

            # Restore selection.
            target_row = 0
            if not initial and prev_kind == "job" and prev_index is not None and prev_index < len(apps):
                target_row = 2 + prev_index  # 0 = template, 1 = divider
            self._sidebar.setCurrentRow(target_row)
        finally:
            self._suppress_selection = False

        # Manually trigger a load for the current row, since signals were suppressed.
        self._load_for_row(self._sidebar.currentRow())

    def _on_row_changed(self, row: int) -> None:
        if self._suppress_selection or row < 0:
            return
        # Skip divider — bump to next selectable.
        item = self._sidebar.item(row)
        if item is not None and not (item.flags() & Qt.ItemFlag.ItemIsSelectable):
            self._sidebar.setCurrentRow(row + 1 if row + 1 < self._sidebar.count() else 0)
            return
        # Commit edits on the page we are leaving before swapping content.
        self.commit_current()
        self._load_for_row(row)

    def _load_for_row(self, row: int) -> None:
        if row <= 0:
            self._current_kind = "template"
            self._current_job_index = None
            self._editor.load(self._template)
            return
        # Row 1 is the divider, rows 2..N are jobs (when divider present).
        job_index = row - 2 if self._sidebar.count() > 1 else None
        apps = self._get_applications()
        if job_index is None or not (0 <= job_index < len(apps)):
            self._current_kind = "template"
            self._current_job_index = None
            self._editor.load(self._template)
            return
        self._current_kind = "job"
        self._current_job_index = job_index
        existing = apps[job_index].get("interview_questions") or []
        self._editor.load(existing if existing else list(self._template))


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
            "🎤  Interview Practice",
            "❓  Interview Questions",
            "🎯  Job-specific Interview",
        ):
            item = QListWidgetItem(label)
            item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            self._sidebar.addItem(item)

        self._questions_page = InterviewQuestionsPage(get_profile=get_profile)

        self._job_page: JobInterviewPage | None = None
        if get_applications is not None and set_application_interviews is not None:
            self._job_page = JobInterviewPage(
                get_profile=get_profile or (lambda: {}),
                get_applications=get_applications,
                get_research_cache=get_research_cache or (lambda: {}),
                set_application_interviews=set_application_interviews,
            )

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_blank_page("Interview Practice"))
        self._stack.addWidget(self._questions_page)
        if self._job_page is not None:
            self._stack.addWidget(self._job_page)
        else:
            self._stack.addWidget(self._build_blank_page("Job-specific Interview"))

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
        coming.setStyleSheet("color: #666;")
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
