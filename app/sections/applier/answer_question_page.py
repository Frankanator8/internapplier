from __future__ import annotations

from PyQt6.QtWidgets import QHBoxLayout, QTextEdit, QWidget

from app.context import AppContext
from app.ui.application_picker import ApplicationPicker
from app.ui.widgets import (
    BusyButton, append_stream_text, button, copy_text, hsplitter, label,
    line_edit, set_status, set_titled_content, status_label, vbox_widget,
)
from app.ui.workers import StreamWorker, WorkerPool

from .generate_resume_page import saved_applications


class AnswerQuestionPage(QWidget):
    """Draft an answer to an application question from the profile (and research)."""

    def __init__(self, ctx: AppContext, parent=None):
        super().__init__(parent)
        self._ctx = ctx
        self._pool = WorkerPool(self)

        left, left_layout = vbox_widget((0, 8, 0, 0), spacing=10)
        left.setMinimumWidth(320)
        left_layout.addWidget(label("Fill from Application"))
        self._app_picker = ApplicationPicker(saved_applications)
        self._app_picker.picked.connect(self._fill_from_application)
        left_layout.addWidget(self._app_picker)

        left_layout.addWidget(label("Company (optional)"))
        self._company_input = line_edit("Match a researched company to tailor the answer")
        left_layout.addWidget(self._company_input)

        left_layout.addWidget(label("Question"))
        self._question_input = QTextEdit()
        self._question_input.setPlaceholderText("e.g. Why are you interested in this role?")
        left_layout.addWidget(self._question_input, 1)

        left_layout.addWidget(label("Job Description (optional)"))
        self._jd_input = QTextEdit()
        self._jd_input.setPlaceholderText("Paste the job description to tailor the answer to the role…")
        left_layout.addWidget(self._jd_input, 2)

        self._answer_btn = BusyButton("❓  Answer Question", "Answering…")
        self._answer_btn.clicked.connect(self._answer)
        left_layout.addWidget(self._answer_btn)
        self._status = status_label()
        left_layout.addWidget(self._status)

        right, right_layout = vbox_widget((0, 8, 0, 0), spacing=8)
        self._output = QTextEdit()
        self._output.setReadOnly(True)
        self._output.setPlaceholderText("The generated answer will stream here.")
        right_layout.addWidget(self._output, 1)
        copy_btn = button("Copy Answer", "secondary", 120)
        copy_btn.clicked.connect(lambda: copy_text(self._output.toPlainText()))
        btn_row = QHBoxLayout()
        btn_row.addWidget(copy_btn)
        btn_row.addStretch()
        right_layout.addLayout(btn_row)

        set_titled_content(self, "Answer Question", hsplitter(left, right, sizes=[360, 600]))

    def on_shown(self) -> None:
        self._app_picker.refresh()

    def _fill_from_application(self, entry: dict) -> None:
        self._company_input.setText(entry.get("company", "") or "")
        self._jd_input.setPlainText(entry.get("description", "") or "")

    def _answer(self) -> None:
        question = self._question_input.toPlainText().strip()
        if not question:
            set_status(self._status, "error", "Type a question first.")
            return
        company = self._company_input.text().strip()
        jd = self._jd_input.toPlainText().strip()
        research = self._ctx.research.lookup(company) if company else None

        if research:
            message = f"Using cached research for {company!r}…"
        elif company:
            message = f"No cached research for {company!r} — answering from profile only."
        else:
            message = "Answering from profile…"
        self._output.clear()
        self._answer_btn.set_busy(True)
        set_status(self._status, "neutral", message)

        def on_finished(_text: str):
            self._answer_btn.set_busy(False)
            self._status.setText("")

        def on_error(msg: str):
            self._answer_btn.set_busy(False)
            set_status(self._status, "error", f"Error: {msg}")

        self._pool.start(
            StreamWorker.provider(
                "answer_question_stream",
                question=question,
                profile=self._ctx.get_profile(),
                company_research=research,
                company_name=company or None,
                job_description=jd or None,
            ),
            chunk=lambda text: append_stream_text(self._output, text),
            finished=on_finished,
            error=on_error,
        )
