from __future__ import annotations

import datetime
import json
import logging
import uuid
from typing import Callable

from PyQt6.QtCore import QObject, QSize, QThread, QTimer, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QScrollArea, QSizePolicy,
    QStackedWidget, QTabWidget, QTextBrowser, QTextEdit, QVBoxLayout, QWidget,
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
            for chunk in get_provider(tier="fast").grade_interview_response_stream(
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


class _ChatReplyWorker(QObject):
    stream = pyqtSignal(str)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(
        self,
        history: list[dict],
        profile: dict,
        company_name: str | None = None,
        company_research: dict | None = None,
        job_description: str | None = None,
    ):
        super().__init__()
        self._history = history
        self._profile = profile
        self._company_name = company_name
        self._company_research = company_research
        self._job_description = job_description

    def run(self):
        from api.ai_provider import get_provider
        logger.info(
            "_ChatReplyWorker.run — turns=%d company=%r",
            len(self._history), self._company_name,
        )
        try:
            for chunk in get_provider(tier="fast").chat_interview_stream(
                history=self._history,
                profile=self._profile,
                company_name=self._company_name,
                company_research=self._company_research,
                job_description=self._job_description,
            ):
                self.stream.emit(chunk)
            self.finished.emit()
        except Exception as exc:
            logger.exception("_ChatReplyWorker.run — failed")
            self.error.emit(str(exc))


class _FeedbackWorker(QObject):
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
            "_FeedbackWorker.run — question=%r response_chars=%d",
            self._question[:80], len(self._response),
        )
        try:
            for chunk in get_provider(tier="fast").grade_interview_response_stream(
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
            logger.exception("_FeedbackWorker.run — failed")
            self.error.emit(str(exc))


class _NotesWorker(QObject):
    stream = pyqtSignal(str)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(
        self,
        history: list[dict],
        prior_notes: str,
        profile: dict,
        company_name: str | None = None,
        company_research: dict | None = None,
        job_description: str | None = None,
    ):
        super().__init__()
        self._history = history
        self._prior_notes = prior_notes
        self._profile = profile
        self._company_name = company_name
        self._company_research = company_research
        self._job_description = job_description

    def run(self):
        from api.ai_provider import get_provider
        logger.info(
            "_NotesWorker.run — turns=%d prior_chars=%d",
            len(self._history), len(self._prior_notes or ""),
        )
        try:
            for chunk in get_provider(tier="fast").summarize_interview_notes_stream(
                history=self._history,
                prior_notes=self._prior_notes,
                profile=self._profile,
                company_name=self._company_name,
                company_research=self._company_research,
                job_description=self._job_description,
            ):
                self.stream.emit(chunk)
            self.finished.emit()
        except Exception as exc:
            logger.exception("_NotesWorker.run — failed")
            self.error.emit(str(exc))


def _extract_partial_feedback(buf: str) -> str:
    """Pull the `feedback` string out of a possibly-incomplete JSON buffer.

    Lets us stream the body text as it arrives instead of waiting for the
    whole JSON object to close.
    """
    idx = buf.find('"feedback"')
    if idx < 0:
        return ""
    colon = buf.find(':', idx)
    if colon < 0:
        return ""
    start = buf.find('"', colon + 1)
    if start < 0:
        return ""
    out: list[str] = []
    i = start + 1
    n = len(buf)
    while i < n:
        c = buf[i]
        if c == '\\' and i + 1 < n:
            nxt = buf[i + 1]
            out.append(
                {'n': '\n', 't': '\t', '"': '"', '\\': '\\', '/': '/'}.get(nxt, nxt)
            )
            i += 2
        elif c == '"':
            break
        else:
            out.append(c)
            i += 1
    return ''.join(out)


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


class InterviewChatPage(QWidget):
    def __init__(
        self,
        get_profile: Callable[[], dict] | None = None,
        get_applications: Callable[[], list[dict]] | None = None,
        get_research_cache: Callable[[], dict] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._get_profile = get_profile or (lambda: {})
        self._get_applications = get_applications or (lambda: [])
        self._get_research_cache = get_research_cache or (lambda: {})

        self._threads: list[QThread] = []
        self._workers: list[QObject] = []

        self._history: list[dict] = []
        self._cards: list[dict] = []
        self._notes_md: str = ""
        self._session_id: str = uuid.uuid4().hex
        self._started_at: datetime.datetime = datetime.datetime.now()
        self._current_job: dict | None = None
        self._current_job_app_idx: int | None = None
        self._reply_in_flight: bool = False
        self._notes_buffer: str = ""

        self._stt = None
        self._stt_active: bool = False
        self._tts = None
        self._pending_auto_listen: bool = False

        self._camera = None
        self._capture_session = None
        self._video_widget = None

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        main_col = QWidget()
        main_layout = QVBoxLayout(main_col)
        main_layout.setContentsMargins(20, 18, 12, 14)
        main_layout.setSpacing(10)

        header_row = QHBoxLayout()
        header_row.setSpacing(8)
        header_row.addWidget(_label("Interview Practice", "section-title"))
        header_row.addStretch()
        header_row.addWidget(QLabel("Job:"))
        self._job_picker = QComboBox()
        self._job_picker.setMinimumWidth(220)
        self._job_picker.currentIndexChanged.connect(self._on_job_changed)
        header_row.addWidget(self._job_picker)
        self._new_chat_btn = _secondary_btn("🆕 New Chat", 110)
        self._new_chat_btn.clicked.connect(self._on_new_chat)
        header_row.addWidget(self._new_chat_btn)
        main_layout.addLayout(header_row)

        self._transcript_scroll = QScrollArea()
        self._transcript_scroll.setWidgetResizable(True)
        self._transcript_scroll.setFrameShape(QFrame.Shape.NoFrame)
        transcript_host = QWidget()
        transcript_host.setStyleSheet("background: transparent;")
        self._transcript_layout = QVBoxLayout(transcript_host)
        self._transcript_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._transcript_layout.setSpacing(10)
        self._transcript_layout.setContentsMargins(0, 0, 8, 8)
        self._transcript_scroll.setWidget(transcript_host)
        main_layout.addWidget(self._transcript_scroll, 1)

        input_row = QHBoxLayout()
        input_row.setSpacing(8)
        self._input = QTextEdit()
        self._input.setPlaceholderText("Type your answer, or click 🎤 to speak…")
        self._input.setFixedHeight(80)
        self._input.textChanged.connect(self._refresh_send_enabled)
        input_row.addWidget(self._input, 1)

        btn_col = QVBoxLayout()
        btn_col.setSpacing(6)
        self._mic_btn = _icon_btn("🎤")
        self._mic_btn.setToolTip("Speak your answer")
        self._mic_btn.setCheckable(True)
        self._mic_btn.clicked.connect(self._on_mic_toggled)
        self._send_btn = _primary_btn("Send", 90)
        self._send_btn.clicked.connect(self._on_send)
        self._send_btn.setEnabled(False)
        btn_col.addWidget(self._mic_btn, 0, Qt.AlignmentFlag.AlignRight)
        btn_col.addWidget(self._send_btn, 0, Qt.AlignmentFlag.AlignRight)
        input_row.addLayout(btn_col)
        main_layout.addLayout(input_row)

        outer.addWidget(main_col, 1)

        # ── Side panel ────────────────────────────────────────────
        side = QWidget()
        side.setFixedWidth(340)
        side.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(8, 18, 20, 14)
        side_layout.setSpacing(8)

        # Local-only camera preview. Frames are rendered straight to the
        # QVideoWidget by Qt's pipeline — no capture path feeds AI workers.
        self._camera_frame = self._build_camera_preview()
        side_layout.addWidget(self._camera_frame)

        side_layout.addWidget(_label("Feedback", "section-title"))

        self._side_tabs = QTabWidget()
        self._side_tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._cards_scroll = QScrollArea()
        self._cards_scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._cards_scroll.setWidgetResizable(True)
        self._cards_scroll.setFrameShape(QFrame.Shape.NoFrame)
        cards_host = QWidget()
        cards_host.setStyleSheet("background: transparent;")
        self._cards_layout_v = QVBoxLayout(cards_host)
        self._cards_layout_v.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._cards_layout_v.setSpacing(10)
        self._cards_layout_v.setContentsMargins(0, 4, 4, 4)
        self._cards_empty_label = QLabel(
            "Per-answer feedback will appear here after you send a reply."
        )
        self._cards_empty_label.setWordWrap(True)
        self._cards_empty_label.setStyleSheet("color: #888; padding: 8px 4px;")
        self._cards_layout_v.addWidget(self._cards_empty_label)
        self._cards_scroll.setWidget(cards_host)
        self._side_tabs.addTab(self._cards_scroll, "Per-Answer")

        self._notes_view = QTextBrowser()
        self._notes_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._notes_view.setPlaceholderText(
            "Overall coaching notes will populate as the conversation progresses."
        )
        self._side_tabs.addTab(self._notes_view, "Overall Notes")

        side_layout.addWidget(self._side_tabs, 1)

        outer.addWidget(side)

        # Ctrl+Enter sends
        self._input.installEventFilter(self)

        self._populate_job_picker()
        self._maybe_setup_speech()

        # Kick off opening turn from AI.
        QTimer.singleShot(0, self._kick_off_opening_turn)

    # ── Camera preview (local display only — never sent to AI) ───
    def _build_camera_preview(self) -> QWidget:
        container = QFrame()
        container.setObjectName("card")
        container.setStyleSheet(
            "QFrame#card { background: #111; border: 1px solid #e0e0e0;"
            " border-radius: 8px; }"
        )
        v = QVBoxLayout(container)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        container.setFixedHeight(190)
        self._camera_layout = v
        self._camera_placeholder: QLabel | None = None

        # Fire the macOS permission prompt early (fire-and-forget). Without
        # this, QCamera silently shows black frames the first time.
        self._kick_macos_camera_permission()

        try:
            from PyQt6.QtMultimedia import QCamera, QMediaCaptureSession, QMediaDevices
            from PyQt6.QtMultimediaWidgets import QVideoWidget
        except Exception:
            logger.info("Camera preview unavailable — QtMultimedia not present")
            self._show_camera_placeholder("Camera unavailable")
            return container

        device = QMediaDevices.defaultVideoInput()
        if device is None or device.isNull():
            self._show_camera_placeholder(self._no_device_hint())
            return container

        try:
            self._video_widget = QVideoWidget()
            self._video_widget.setStyleSheet("background: #000;")
            v.addWidget(self._video_widget)

            self._camera = QCamera(device)
            self._capture_session = QMediaCaptureSession()
            self._capture_session.setCamera(self._camera)
            self._capture_session.setVideoOutput(self._video_widget)
            # Surface camera errors (denied permission, in-use, etc.) in the UI.
            try:
                self._camera.errorOccurred.connect(self._on_camera_error)
            except Exception:
                pass
        except Exception:
            logger.exception("Camera preview setup failed")
            self._camera = None
            self._capture_session = None
            self._show_camera_placeholder("Camera setup failed")
        return container

    def _show_camera_placeholder(self, text: str):
        # Replace the video widget with a label, or update the existing one.
        if self._camera_placeholder is not None:
            self._camera_placeholder.setText(text)
            return
        if getattr(self, "_video_widget", None) is not None:
            self._camera_layout.removeWidget(self._video_widget)
            self._video_widget.deleteLater()
            self._video_widget = None
        label = QLabel(text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("color: #bbb; font-size: 12px;")
        label.setWordWrap(True)
        self._camera_layout.addWidget(label)
        self._camera_placeholder = label

    def _kick_macos_camera_permission(self):
        import sys
        if sys.platform != "darwin":
            return
        try:
            from AVFoundation import AVCaptureDevice, AVMediaTypeVideo
        except Exception:
            return
        try:
            status = AVCaptureDevice.authorizationStatusForMediaType_(AVMediaTypeVideo)
        except Exception:
            return
        # 3 = Authorized; nothing to do. 1/2 = Restricted/Denied; prompt won't help.
        if status != 0:
            return
        try:
            # Fire-and-forget. The handler may never run if Info.plist lacks
            # NSCameraUsageDescription, so we don't block UI on it.
            AVCaptureDevice.requestAccessForMediaType_completionHandler_(
                AVMediaTypeVideo, lambda _granted: None
            )
        except Exception:
            logger.exception("Camera permission request failed")

    def _no_device_hint(self) -> str:
        import sys
        if sys.platform == "darwin":
            return (
                "No camera detected.\nIf you have one, allow access in\n"
                "System Settings → Privacy & Security → Camera."
            )
        if sys.platform.startswith("win"):
            return (
                "No camera detected.\nIf you have one, allow access in\n"
                "Settings → Privacy & security → Camera."
            )
        return "No camera detected."

    def _on_camera_error(self, *_args):
        try:
            err = self._camera.errorString() if self._camera else ""
        except Exception:
            err = ""
        logger.warning("Camera error: %s", err or "unknown")
        self._show_camera_placeholder(err or "Camera unavailable")

    def _start_camera(self):
        if self._camera is not None:
            try:
                self._camera.start()
            except Exception:
                logger.exception("Camera start failed")

    def _stop_camera(self):
        if self._camera is not None:
            try:
                self._camera.stop()
            except Exception:
                logger.exception("Camera stop failed")

    def hideEvent(self, event):  # noqa: N802
        self._stop_camera()
        super().hideEvent(event)

    # ── Speech wiring ────────────────────────────────────────────
    def _maybe_setup_speech(self):
        try:
            from api.speech import SpeechToText, TextToSpeech, is_supported
        except Exception:
            self._mic_btn.setEnabled(False)
            self._mic_btn.setToolTip("Speech not available.")
            return

        import sys
        if sys.platform == "darwin":
            self._tts = TextToSpeech(self)
            self._tts.finished.connect(self._on_tts_finished)
            self._tts.error.connect(lambda _msg: self._on_tts_finished())
            # Pre-warm `say` so the first real utterance plays without
            # the macOS audio-subsystem startup delay swallowing it.
            try:
                self._tts.speak(" ")
            except Exception:
                logger.exception("TTS prewarm failed")

        if not is_supported():
            self._mic_btn.setEnabled(False)
            self._mic_btn.setToolTip("Speech recognition not available on this platform.")
            return
        self._stt = SpeechToText(self)
        self._stt.partial.connect(self._on_stt_partial)
        self._stt.final.connect(self._on_stt_final)
        self._stt.error.connect(self._on_stt_error)
        self._stt.finished.connect(self._on_stt_finished)

    def _on_mic_toggled(self, checked: bool):
        if self._stt is None:
            return
        if checked:
            self._stop_speaking()
            self._stt_active = True
            self._mic_btn.setText("⏺")
            try:
                self._stt.start()
            except Exception as exc:
                logger.exception("STT start failed")
                self._on_stt_error(str(exc))
        else:
            self._stt_active = False
            self._stt.stop()
            QTimer.singleShot(50, self._on_send)

    def _speak(self, text: str) -> None:
        if self._tts is None:
            return
        try:
            self._tts.speak(text)
        except Exception:
            logger.exception("TTS speak failed")

    def _stop_speaking(self) -> None:
        if self._tts is None:
            return
        try:
            self._tts.stop()
        except Exception:
            logger.exception("TTS stop failed")

    def _on_stt_partial(self, text: str):
        if self._stt_active:
            self._input.setPlainText(text)

    def _on_stt_final(self, text: str):
        if not self._stt_active:
            # Late final emitted after we already stopped (e.g. user hit
            # Send or pressed the mic again). Ignore so we don't undo
            # the input clear.
            return
        self._input.setPlainText(text)

    def _on_stt_error(self, msg: str):
        logger.warning("STT error: %s", msg)
        self._mic_btn.setChecked(False)
        self._mic_btn.setText("🎤")
        self._stt_active = False

    def _on_stt_finished(self):
        self._mic_btn.setChecked(False)
        self._mic_btn.setText("🎤")
        self._stt_active = False

    def _auto_start_listening(self):
        if self._stt is None or self._stt_active or self._reply_in_flight:
            self._pending_auto_listen = False
            return
        if not self._mic_btn.isEnabled():
            self._pending_auto_listen = False
            return
        self._pending_auto_listen = False
        self._input.clear()
        self._mic_btn.setChecked(True)
        self._on_mic_toggled(True)

    def _on_tts_finished(self):
        if self._pending_auto_listen:
            self._auto_start_listening()

    # ── Job picker ───────────────────────────────────────────────
    def _populate_job_picker(self):
        self._job_picker.blockSignals(True)
        self._job_picker.clear()
        self._job_picker.addItem("Generic — no job", userData=None)
        apps = self._get_applications() or []
        for idx, entry in enumerate(apps):
            company = (entry.get("company") or "").strip()
            role = (entry.get("role") or "").strip()
            if not company and not role:
                continue
            label = " — ".join([s for s in (company, role) if s])
            self._job_picker.addItem(label, userData=idx)

        # Restore previously selected job so it survives re-show / apps changes.
        target_row = 0
        if self._current_job_app_idx is not None:
            found = False
            for row in range(self._job_picker.count()):
                if self._job_picker.itemData(row) == self._current_job_app_idx:
                    target_row = row
                    found = True
                    break
            if not found:
                self._current_job_app_idx = None
                self._current_job = None
        self._job_picker.setCurrentIndex(target_row)
        self._job_picker.blockSignals(False)

    def _on_job_changed(self, index: int):
        if index < 0:
            self._current_job_app_idx = None
            self._current_job = None
            return
        app_idx = self._job_picker.itemData(index)
        if app_idx is None:
            self._current_job_app_idx = None
            self._current_job = None
            return
        apps = self._get_applications() or []
        if not (0 <= app_idx < len(apps)):
            self._current_job_app_idx = None
            self._current_job = None
            return
        entry = apps[app_idx]
        from .applier import _research_from_cache
        research = _research_from_cache(
            self._get_research_cache() or {}, entry.get("company", "")
        )
        self._current_job_app_idx = app_idx
        self._current_job = {
            "company_name": entry.get("company") or None,
            "title": entry.get("role") or None,
            "company_research": research,
            "job_description": entry.get("description") or None,
        }

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        self._populate_job_picker()
        self._start_camera()

    # ── Transcript bubbles ───────────────────────────────────────
    def _add_bubble(self, role: str, text: str) -> QLabel:
        card = QFrame()
        card.setObjectName("card")
        if role == "user":
            card.setStyleSheet(
                "QFrame#card { background: #eef3fb; border: 1px solid #cfd8e3;"
                " border-radius: 8px; }"
            )
        else:
            card.setStyleSheet(
                "QFrame#card { background: #ffffff; border: 1px solid #e0e0e0;"
                " border-radius: 8px; }"
            )
        v = QVBoxLayout(card)
        v.setContentsMargins(12, 8, 12, 10)
        v.setSpacing(4)

        who = QLabel("You" if role == "user" else "Interviewer")
        who.setStyleSheet("color: #666; font-size: 11px; font-weight: 600;")
        v.addWidget(who)

        body = QLabel(text)
        body.setWordWrap(True)
        body.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        body.setStyleSheet("font-size: 14px;")
        v.addWidget(body)

        self._transcript_layout.addWidget(card)
        QTimer.singleShot(0, self._scroll_transcript_to_bottom)
        return body

    def _scroll_transcript_to_bottom(self):
        bar = self._transcript_scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _scroll_cards_to_bottom(self):
        bar = self._cards_scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    # ── Per-answer feedback cards ────────────────────────────────
    def _add_feedback_card(self, question: str) -> dict:
        if self._cards_empty_label is not None:
            self._cards_empty_label.setVisible(False)

        card = QFrame()
        card.setObjectName("card")
        card.setStyleSheet(
            "QFrame#card { background: #fff; border: 1px solid #e0e0e0;"
            " border-radius: 8px; }"
        )
        v = QVBoxLayout(card)
        v.setContentsMargins(10, 8, 10, 10)
        v.setSpacing(4)

        q_label = QLabel(question or "Opening exchange")
        q_label.setWordWrap(True)
        q_label.setStyleSheet("color: #555; font-size: 11px; font-weight: 600;")
        v.addWidget(q_label)

        title = QLabel("GENERATING…")
        title.setStyleSheet("color: #888; font-size: 10px; font-weight: 700;")
        v.addWidget(title)

        body = QLabel("")
        body.setWordWrap(True)
        body.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        body.setStyleSheet("font-size: 13px;")
        body.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        body.setMinimumWidth(1)
        body_sp = body.sizePolicy()
        body_sp.setHeightForWidth(True)
        body_sp.setVerticalPolicy(QSizePolicy.Policy.MinimumExpanding)
        body.setSizePolicy(body_sp)
        v.addWidget(body)

        self._cards_layout_v.addWidget(card)
        QTimer.singleShot(0, self._scroll_cards_to_bottom)
        record = {
            "question": question,
            "answer": "",
            "rubric_md": "",
            "buffer": "",
            "widget": card,
            "title": title,
            "body": body,
        }
        self._cards.append(record)
        return record

    # ── Send flow ────────────────────────────────────────────────
    def eventFilter(self, obj, event):  # noqa: N802 (Qt API)
        from PyQt6.QtCore import QEvent
        if obj is self._input and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            mods = event.modifiers()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and (
                mods & Qt.KeyboardModifier.ControlModifier
            ):
                self._on_send()
                return True
        return super().eventFilter(obj, event)

    def _refresh_send_enabled(self):
        has_text = bool(self._input.toPlainText().strip())
        self._send_btn.setEnabled(has_text and not self._reply_in_flight)

    def _set_reply_in_flight(self, value: bool):
        self._reply_in_flight = value
        self._refresh_send_enabled()

    def _kick_off_opening_turn(self):
        # Empty history → AI greets and asks first question.
        self._spawn_chat_reply()

    def _on_send(self):
        if self._reply_in_flight:
            return
        text = self._input.toPlainText().strip()
        if not text:
            return
        if self._stt is not None and self._stt_active:
            self._stt_active = False
            self._stt.stop()
        self._stop_speaking()
        self._input.clear()

        last_question = ""
        for turn in reversed(self._history):
            if turn.get("role") == "assistant" and (turn.get("content") or "").strip():
                last_question = turn["content"]
                break

        self._add_bubble("user", text)
        self._history.append({"role": "user", "content": text})

        card = self._add_feedback_card(last_question)
        card["answer"] = text
        self._spawn_feedback_worker(last_question, text, card)

        self._spawn_chat_reply()

    def _spawn_chat_reply(self):
        profile = self._get_profile() or {}
        job = self._current_job or {}

        bubble_body = self._add_bubble("assistant", "")
        buffer = {"text": ""}

        worker = _ChatReplyWorker(
            history=list(self._history),
            profile=profile,
            company_name=job.get("company_name"),
            company_research=job.get("company_research"),
            job_description=job.get("job_description"),
        )
        thread = QThread(self)
        worker.moveToThread(thread)

        self._set_reply_in_flight(True)

        def on_chunk(delta: str):
            buffer["text"] += delta
            bubble_body.setText(buffer["text"])
            self._scroll_transcript_to_bottom()

        def on_finished():
            final = buffer["text"].strip()
            spoke = False
            if final:
                self._history.append({"role": "assistant", "content": final})
                if self._tts is not None:
                    self._speak(final)
                    spoke = True
                self._spawn_notes_worker()
            self._set_reply_in_flight(False)
            thread.quit()
            if spoke:
                # Wait for TTS to finish before opening the mic — otherwise
                # starting STT immediately stops TTS playback.
                self._pending_auto_listen = True
            else:
                self._auto_start_listening()

        def on_error(msg: str):
            bubble_body.setText(f"(error: {msg})")
            self._set_reply_in_flight(False)
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

    def _spawn_feedback_worker(self, question: str, response: str, card: dict):
        profile = self._get_profile() or {}
        job = self._current_job or {}

        worker = _FeedbackWorker(
            question=question or "(opening — interviewer had not asked a question yet)",
            response=response,
            profile=profile,
            company_name=job.get("company_name"),
            company_research=job.get("company_research"),
            job_description=job.get("job_description"),
        )
        thread = QThread(self)
        worker.moveToThread(thread)

        def on_chunk(delta: str):
            card["buffer"] += delta
            partial = _extract_partial_feedback(card["buffer"])
            if partial:
                card["title"].setText("STREAMING…")
                card["body"].setText(partial)

        def on_finished():
            buf = card["buffer"]
            try:
                parsed = json.loads(buf)
                score = parsed.get("score")
                feedback = parsed.get("feedback", "") or ""
                score_str = (
                    f"{score:g}" if isinstance(score, (int, float)) else str(score)
                )
                card["title"].setText(f"SCORE {score_str}/10")
                rendered = feedback if feedback else "Strong answer — nothing actionable."
                card["body"].setText(rendered)
                card["rubric_md"] = f"**Score:** {score_str}/10\n\n{rendered}"
            except (ValueError, TypeError):
                card["title"].setText("FEEDBACK")
                card["body"].setText(buf)
                card["rubric_md"] = buf
            thread.quit()

        def on_error(msg: str):
            card["title"].setText("FEEDBACK · ERROR")
            card["body"].setText(msg)
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

    def _spawn_notes_worker(self):
        profile = self._get_profile() or {}
        job = self._current_job or {}

        self._notes_buffer = ""

        worker = _NotesWorker(
            history=list(self._history),
            prior_notes=self._notes_md,
            profile=profile,
            company_name=job.get("company_name"),
            company_research=job.get("company_research"),
            job_description=job.get("job_description"),
        )
        thread = QThread(self)
        worker.moveToThread(thread)

        def on_chunk(delta: str):
            self._notes_buffer += delta
            self._notes_view.setMarkdown(self._notes_buffer)

        def on_finished():
            self._notes_md = self._notes_buffer
            self._notes_view.setMarkdown(self._notes_md)
            thread.quit()

        def on_error(msg: str):
            self._notes_view.setMarkdown(
                self._notes_md
                + f"\n\n_(notes update failed: {msg})_"
            )
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

    # ── Session lifecycle ────────────────────────────────────────
    def _on_new_chat(self):
        self._stop_speaking()
        self.flush_active_chat()
        self._reset_state()

    def _reset_state(self):
        self._history = []
        self._cards = []
        self._notes_md = ""
        self._notes_buffer = ""
        self._session_id = uuid.uuid4().hex
        self._started_at = datetime.datetime.now()

        # Clear transcript
        while self._transcript_layout.count():
            item = self._transcript_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        # Clear feedback cards
        while self._cards_layout_v.count():
            item = self._cards_layout_v.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._cards_empty_label = QLabel(
            "Per-answer feedback will appear here after you send a reply."
        )
        self._cards_empty_label.setWordWrap(True)
        self._cards_empty_label.setStyleSheet("color: #888; padding: 8px 4px;")
        self._cards_layout_v.addWidget(self._cards_empty_label)

        self._notes_view.setMarkdown("")

        QTimer.singleShot(0, self._kick_off_opening_turn)

    def flush_active_chat(self) -> None:
        if not any(t.get("role") == "user" for t in self._history):
            return
        try:
            from api.data_store import append_interview_feedback
            job_meta = None
            if self._current_job:
                job_meta = {
                    "company": self._current_job.get("company_name"),
                    "title": self._current_job.get("title"),
                }
            session = {
                "id": self._session_id,
                "started_at": self._started_at.isoformat(timespec="seconds"),
                "ended_at": datetime.datetime.now().isoformat(timespec="seconds"),
                "job": job_meta,
                "transcript": list(self._history),
                "cards": [
                    {
                        "question": c["question"],
                        "answer": c["answer"],
                        "rubric_md": c["rubric_md"],
                    }
                    for c in self._cards
                ],
                "notes_md": self._notes_md,
            }
            append_interview_feedback(session)
        except Exception:
            logger.exception("flush_active_chat — failed to persist session")


class PastFeedbackPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._list = QListWidget()
        self._list.setObjectName("sidebar")
        self._list.setFixedWidth(260)
        outer.addWidget(self._list)

        self._right = QWidget()
        right_layout = QVBoxLayout(self._right)
        right_layout.setContentsMargins(20, 18, 20, 14)
        right_layout.setSpacing(10)
        right_layout.addWidget(_label("Past Feedback", "section-title"))

        self._detail_tabs = QTabWidget()
        self._transcript_view = QTextBrowser()
        self._cards_view = QTextBrowser()
        self._notes_view = QTextBrowser()
        self._detail_tabs.addTab(self._transcript_view, "Transcript")
        self._detail_tabs.addTab(self._cards_view, "Per-Answer")
        self._detail_tabs.addTab(self._notes_view, "Overall Notes")
        right_layout.addWidget(self._detail_tabs, 1)

        outer.addWidget(self._right, 1)

        self._sessions: list[dict] = []
        self._list.currentRowChanged.connect(self._on_select)

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        self._refresh()

    def _refresh(self):
        from api.data_store import load_interview_feedback
        try:
            self._sessions = load_interview_feedback() or []
        except Exception:
            logger.exception("PastFeedbackPage._refresh — load failed")
            self._sessions = []
        # newest first
        self._sessions.sort(
            key=lambda s: s.get("started_at", ""), reverse=True
        )
        self._list.clear()
        for s in self._sessions:
            started = s.get("started_at", "")[:16].replace("T", " ")
            job = s.get("job") or {}
            company = job.get("company") or "Generic"
            label = f"{started} — {company}"
            self._list.addItem(label)
        if self._sessions:
            self._list.setCurrentRow(0)
        else:
            self._transcript_view.setMarkdown(
                "_No past sessions yet. Run a chat in Interview Practice and click "
                "🆕 New Chat or close the app to save feedback here._"
            )
            self._cards_view.setMarkdown("")
            self._notes_view.setMarkdown("")

    def _on_select(self, row: int):
        if not (0 <= row < len(self._sessions)):
            return
        s = self._sessions[row]

        transcript_md_lines: list[str] = []
        for t in s.get("transcript") or []:
            who = "**You:**" if t.get("role") == "user" else "**Interviewer:**"
            transcript_md_lines.append(f"{who} {t.get('content', '').strip()}\n")
        self._transcript_view.setMarkdown("\n".join(transcript_md_lines))

        cards_md_lines: list[str] = []
        for c in s.get("cards") or []:
            q = (c.get("question") or "Opening exchange").strip()
            cards_md_lines.append(f"### Q: {q}\n")
            ans = (c.get("answer") or "").strip()
            if ans:
                cards_md_lines.append(f"_Your answer:_ {ans}\n")
            cards_md_lines.append((c.get("rubric_md") or "").strip())
            cards_md_lines.append("\n---\n")
        self._cards_view.setMarkdown("\n".join(cards_md_lines))

        self._notes_view.setMarkdown(s.get("notes_md") or "_No notes saved._")


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
            "💬  Interview Practice",
            "❓  Interview Questions",
            "🎯  Job-specific Interview",
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
        self._stack.addWidget(self._chat_page)
        self._stack.addWidget(self._questions_page)
        if self._job_page is not None:
            self._stack.addWidget(self._job_page)
        else:
            self._stack.addWidget(self._build_blank_page("Job-specific Interview"))
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

    def flush_active_chat(self) -> None:
        if self._chat_page is not None:
            self._chat_page.flush_active_chat()
