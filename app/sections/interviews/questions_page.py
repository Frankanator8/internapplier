from __future__ import annotations

import logging
from typing import Callable

from PyQt6.QtCore import QObject, QThread, Qt
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea,
    QTextEdit, QVBoxLayout, QWidget,
)

from api.interview_parsing import parse_grade_payload

from ..base import _icon_btn, _label, _primary_btn, _secondary_btn
from .workers import _GradeWorker

logger = logging.getLogger(__name__)


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
                score, feedback = parse_grade_payload(buf)
                fb_title.setText(f"AI FEEDBACK · SCORE {score:g}/10")
                fb_body.setText(feedback if feedback else "No feedback — answer looks strong.")
            except (ValueError, TypeError) as exc:
                logger.error(
                    "_GradeWorker.on_finished — parse failed: %s; raw=%r",
                    exc, buf[:500],
                )
                fb_title.setText("AI FEEDBACK · ERROR")
                fb_body.setText("AI returned unexpected format — please try again.")
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
