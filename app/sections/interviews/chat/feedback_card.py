from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QSizePolicy, QVBoxLayout

from api.interview_parsing import extract_partial_feedback
from app.ui.widgets import label, make_selectable

from ..grading import GRADE_FORMAT_ERROR, parse_grade


class FeedbackCard(QFrame):
    """Per-answer grade in the chat side panel, filled in as it streams."""

    def __init__(self, question: str, answer: str):
        super().__init__()
        self.setObjectName("card")
        self.question = question
        self.answer = answer
        self.rubric_md = ""
        self._buffer = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(4)
        layout.addWidget(label(question or "Opening exchange", "field-sublabel", wrap=True))
        self._status = label("GENERATING…", "feedback-status")
        layout.addWidget(self._status)

        self._body = make_selectable(label("", "", wrap=True))
        self._body.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._body.setMinimumWidth(1)
        policy = self._body.sizePolicy()
        policy.setHeightForWidth(True)
        policy.setVerticalPolicy(QSizePolicy.Policy.MinimumExpanding)
        self._body.setSizePolicy(policy)
        layout.addWidget(self._body)

    def append(self, delta: str) -> None:
        self._buffer += delta
        partial = extract_partial_feedback(self._buffer)
        if partial:
            self._status.setText("STREAMING…")
            self._body.setText(partial)

    def finish(self, buf: str) -> None:
        parsed = parse_grade(buf)
        if parsed is None:
            self.fail(GRADE_FORMAT_ERROR)
            self.rubric_md = GRADE_FORMAT_ERROR
            return
        score, feedback = parsed
        text = feedback or "Strong answer — nothing actionable."
        self._status.setText(f"SCORE {score}/10")
        self._body.setText(text)
        self.rubric_md = f"**Score:** {score}/10\n\n{text}"

    def fail(self, message: str) -> None:
        self._status.setText("FEEDBACK · ERROR")
        self._body.setText(message)

    def to_record(self) -> dict:
        return {"question": self.question, "answer": self.answer, "rubric_md": self.rubric_md}
