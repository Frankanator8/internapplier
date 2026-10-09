from __future__ import annotations

import datetime
import logging
import uuid

from PyQt6.QtCore import QEvent, Qt, QTimer
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QSizePolicy, QTabWidget, QTextBrowser,
    QTextEdit, QVBoxLayout, QWidget,
)

from api.applications import job_context
from api.data_store import append_interview_feedback
from api.interview_sessions import build_session
from app.context import AppContext
from app.ui.widgets import (
    button, clear_layout, icon_button, label, make_selectable, scroll_area,
    section_header, vbox_widget,
)
from app.ui.workers import StreamWorker, WorkerPool

from ..grading import grade_worker
from .camera import CameraPreview
from .feedback_card import FeedbackCard
from .job_picker import JobPicker
from .speech import SpeechController

logger = logging.getLogger(__name__)

_EMPTY_CARDS = "Per-answer feedback will appear here after you send a reply."


class InterviewChatPage(QWidget):
    """Mock interview: the AI asks questions, the user answers by text or voice.

    Every answer is graded in the side panel and overall coaching notes are
    kept up to date. Sessions are saved on New Chat and on app close.
    """

    def __init__(self, ctx: AppContext, parent=None):
        super().__init__(parent)
        self._ctx = ctx
        self._pool = WorkerPool(self)
        self._speech = SpeechController(self)
        self._speech.transcript.connect(lambda text: self._input.setPlainText(text))
        self._speech.listening_stopped.connect(self._reset_mic)
        self._speech.speaking_finished.connect(self._on_speaking_finished)

        self._history: list[dict] = []
        self._cards: list[FeedbackCard] = []
        self._notes_md = ""
        self._session_id = uuid.uuid4().hex
        self._started_at = datetime.datetime.now()
        self._reply_in_flight = False
        self._pending_auto_listen = False
        # Speech setup and the opening AI turn wait until the page is first
        # shown — otherwise TTS prewarm and the first interviewer reply fire at
        # app startup, while the user is on a different tab.
        self._opened = False

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._build_main_column(), 1)
        outer.addWidget(self._build_side_panel())

    def _build_main_column(self) -> QWidget:
        col, layout = vbox_widget((20, 18, 12, 14), spacing=10)
        self._job_picker = JobPicker(self._ctx.get_applications)
        new_chat_btn = button("🆕 New Chat", "secondary", 110)
        new_chat_btn.clicked.connect(self._on_new_chat)
        header = section_header("Interview Practice", label("Job:", ""), self._job_picker, new_chat_btn)
        header.setSpacing(8)
        layout.addLayout(header)

        self._transcript_scroll, self._transcript = scroll_area(margins=(0, 0, 8, 8), spacing=10)
        layout.addWidget(self._transcript_scroll, 1)

        input_row = QHBoxLayout()
        input_row.setSpacing(8)
        self._input = QTextEdit()
        self._input.setPlaceholderText("Type your answer, or click 🎤 to speak…")
        self._input.setFixedHeight(80)
        self._input.textChanged.connect(self._refresh_send_enabled)
        self._input.installEventFilter(self)  # Ctrl+Enter sends
        input_row.addWidget(self._input, 1)

        btn_col = QVBoxLayout()
        btn_col.setSpacing(6)
        self._mic_btn = icon_button("🎤", tooltip="Speak your answer")
        self._mic_btn.setCheckable(True)
        self._mic_btn.clicked.connect(self._on_mic_toggled)
        self._send_btn = button("Send", width=90)
        self._send_btn.clicked.connect(self._on_send)
        self._send_btn.setEnabled(False)
        btn_col.addWidget(self._mic_btn, 0, Qt.AlignmentFlag.AlignRight)
        btn_col.addWidget(self._send_btn, 0, Qt.AlignmentFlag.AlignRight)
        input_row.addLayout(btn_col)
        layout.addLayout(input_row)
        return col

    def _build_side_panel(self) -> QWidget:
        side, layout = vbox_widget((8, 18, 20, 14), spacing=8)
        side.setFixedWidth(340)
        side.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self._camera = CameraPreview()
        layout.addWidget(self._camera)
        layout.addWidget(label("Feedback", "section-title"))

        tabs = QTabWidget()
        tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._cards_scroll, self._cards_layout = scroll_area(margins=(0, 4, 4, 4), spacing=10)
        self._cards_scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._cards_empty = label(_EMPTY_CARDS, "empty-note", wrap=True)
        self._cards_layout.addWidget(self._cards_empty)
        tabs.addTab(self._cards_scroll, "Per-Answer")

        self._notes_view = QTextBrowser()
        self._notes_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._notes_view.setPlaceholderText(
            "Overall coaching notes will populate as the conversation progresses."
        )
        tabs.addTab(self._notes_view, "Overall Notes")
        layout.addWidget(tabs, 1)
        return side

    # ── Visibility ──────────────────────────────────────────────
    def showEvent(self, event):  # noqa: N802 (Qt API)
        super().showEvent(event)
        self._job_picker.refresh()
        self._camera.start()
        if not self._opened:
            self._opened = True
            self._setup_speech()
            QTimer.singleShot(0, self._request_reply)

    def hideEvent(self, event):  # noqa: N802 (Qt API)
        self._camera.stop()
        self._speech.stop_speaking()
        super().hideEvent(event)

    def _job(self) -> tuple[dict, dict | None]:
        """(AI kwargs describing the selected job, ``{company, title}`` for the session)."""
        entry = self._job_picker.current_entry()
        if entry is None:
            return {}, None
        research = self._ctx.research.lookup(entry.get("company", ""))
        meta = {"company": entry.get("company") or None, "title": entry.get("role") or None}
        return job_context(entry, research), meta

    # ── Speech ──────────────────────────────────────────────────
    def _setup_speech(self) -> None:
        self._speech.setup()
        if not self._speech.can_listen:
            self._mic_btn.setEnabled(False)
            self._mic_btn.setToolTip(self._speech.unavailable_reason)

    def _on_mic_toggled(self, checked: bool) -> None:
        if not self._speech.can_listen:
            return
        if checked:
            self._mic_btn.setText("⏺")
            self._speech.start_listening()
        else:
            self._speech.stop_listening()
            QTimer.singleShot(50, self._on_send)

    def _reset_mic(self) -> None:
        self._mic_btn.setChecked(False)
        self._mic_btn.setText("🎤")

    def _auto_start_listening(self) -> None:
        self._pending_auto_listen = False
        if (
            not self._speech.can_listen or self._speech.listening
            or self._reply_in_flight or not self._mic_btn.isEnabled()
        ):
            return
        self._input.clear()
        self._mic_btn.setChecked(True)
        self._on_mic_toggled(True)

    def _on_speaking_finished(self) -> None:
        if self._pending_auto_listen:
            self._auto_start_listening()

    # ── Transcript ──────────────────────────────────────────────
    def _add_bubble(self, role: str, text: str) -> QLabel:
        bubble = QFrame()
        bubble.setObjectName("chat-bubble-user" if role == "user" else "chat-bubble-ai")
        layout = QVBoxLayout(bubble)
        layout.setContentsMargins(12, 8, 12, 10)
        layout.setSpacing(4)
        layout.addWidget(label("You" if role == "user" else "Interviewer", "chat-who"))
        body = make_selectable(label(text, "chat-body", wrap=True))
        layout.addWidget(body)
        self._transcript.addWidget(bubble)
        QTimer.singleShot(0, lambda: self._scroll_to_bottom(self._transcript_scroll))
        return body

    @staticmethod
    def _scroll_to_bottom(scroll) -> None:
        bar = scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    # ── Send flow ───────────────────────────────────────────────
    def eventFilter(self, obj, event):  # noqa: N802 (Qt API)
        if (
            obj is self._input
            and event.type() == QEvent.Type.KeyPress
            and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
            and event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            self._on_send()
            return True
        return super().eventFilter(obj, event)

    def _refresh_send_enabled(self) -> None:
        self._send_btn.setEnabled(bool(self._input.toPlainText().strip()) and not self._reply_in_flight)

    def _set_reply_in_flight(self, value: bool) -> None:
        self._reply_in_flight = value
        self._refresh_send_enabled()

    def _on_send(self) -> None:
        if self._reply_in_flight:
            return
        text = self._input.toPlainText().strip()
        if not text:
            return
        self._speech.stop_listening()
        self._speech.stop_speaking()
        self._input.clear()

        last_question = next(
            (t["content"] for t in reversed(self._history)
             if t.get("role") == "assistant" and (t.get("content") or "").strip()),
            "",
        )
        self._add_bubble("user", text)
        self._history.append({"role": "user", "content": text})
        self._grade_answer(last_question, text)
        self._request_reply()

    def _request_reply(self) -> None:
        """Stream the interviewer's next turn (the greeting, when history is empty)."""
        bubble = self._add_bubble("assistant", "")
        streamed: list[str] = []
        job, _meta = self._job()
        self._set_reply_in_flight(True)

        def on_chunk(delta: str):
            streamed.append(delta)
            try:
                bubble.setText("".join(streamed))
            except RuntimeError:
                return  # Bubble was deleted (New Chat clicked mid-stream).
            self._scroll_to_bottom(self._transcript_scroll)

        def on_finished(text: str):
            final = text.strip()
            spoke = False
            if final:
                self._history.append({"role": "assistant", "content": final})
                if self._speech.can_speak and self.isVisible():
                    self._speech.speak(final)
                    spoke = True
                self._update_notes()
            self._set_reply_in_flight(False)
            if spoke:
                # Wait for TTS to finish before opening the mic — starting STT
                # immediately would stop the playback.
                self._pending_auto_listen = True
            else:
                self._auto_start_listening()

        def on_error(msg: str):
            try:
                bubble.setText(f"(error: {msg})")
            except RuntimeError:
                pass
            self._set_reply_in_flight(False)

        self._pool.start(
            StreamWorker.provider(
                "chat_interview_stream",
                history=list(self._history), profile=self._ctx.get_profile(), **job,
            ),
            chunk=on_chunk, finished=on_finished, error=on_error,
        )

    def _grade_answer(self, question: str, answer: str) -> None:
        self._cards_empty.setVisible(False)
        card = FeedbackCard(question, answer)
        self._cards_layout.addWidget(card)
        self._cards.append(card)
        QTimer.singleShot(0, lambda: self._scroll_to_bottom(self._cards_scroll))

        job, _meta = self._job()
        self._pool.start(
            grade_worker(
                question or "(opening — interviewer had not asked a question yet)",
                answer, self._ctx.get_profile(), job,
            ),
            chunk=card.append, finished=card.finish, error=card.fail,
        )

    def _update_notes(self) -> None:
        streamed: list[str] = []
        job, _meta = self._job()

        def on_chunk(delta: str):
            streamed.append(delta)
            self._notes_view.setMarkdown("".join(streamed))

        def on_finished(text: str):
            self._notes_md = text
            self._notes_view.setMarkdown(text)

        self._pool.start(
            StreamWorker.provider(
                "summarize_interview_notes_stream",
                history=list(self._history), prior_notes=self._notes_md,
                profile=self._ctx.get_profile(), **job,
            ),
            chunk=on_chunk,
            finished=on_finished,
            error=lambda msg: self._notes_view.setMarkdown(
                self._notes_md + f"\n\n_(notes update failed: {msg})_"
            ),
        )

    # ── Session lifecycle ───────────────────────────────────────
    def _on_new_chat(self) -> None:
        self._speech.stop_speaking()
        self.flush_active_chat()
        self._history = []
        self._cards = []
        self._notes_md = ""
        self._session_id = uuid.uuid4().hex
        self._started_at = datetime.datetime.now()
        clear_layout(self._transcript)
        clear_layout(self._cards_layout)
        self._cards_empty = label(_EMPTY_CARDS, "empty-note", wrap=True)
        self._cards_layout.addWidget(self._cards_empty)
        self._notes_view.setMarkdown("")
        QTimer.singleShot(0, self._request_reply)

    def flush_active_chat(self) -> None:
        """Save the current session to Past Feedback, if the user said anything."""
        if not any(t.get("role") == "user" for t in self._history):
            return
        _job, meta = self._job()
        try:
            append_interview_feedback(build_session(
                session_id=self._session_id,
                started_at=self._started_at,
                job=meta,
                transcript=self._history,
                cards=[c.to_record() for c in self._cards],
                notes_md=self._notes_md,
            ))
        except Exception:
            logger.exception("flush_active_chat — failed to persist session")
