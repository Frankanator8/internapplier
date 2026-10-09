from __future__ import annotations

from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QPlainTextEdit, QSizePolicy, QTextEdit, QWidget,
)

from api import data_store
from app.context import AppContext
from app.ui.application_picker import ApplicationPicker
from app.ui.widgets import (
    BusyButton, append_stream_text, button, clear_layout, copy_text, field,
    hsplitter, label, line_edit, mono_font, open_path, scroll_area, set_status,
    set_titled_content, status_label, vbox_widget,
)
from app.ui.workers import WorkerPool

from .collision import resolve_pdf_collision
from .research_page import result_row, render_research
from .workers import GenerateResumeWorker


def saved_applications() -> list[dict]:
    # Read from disk, not the tracker: the browser extension adds applications
    # there directly, and they should be pickable without a manual Refresh.
    return data_store.load().get("applications") or []


def _button_row(*buttons: QWidget) -> QFrame:
    frame = QFrame()
    row = QHBoxLayout(frame)
    row.setContentsMargins(0, 4, 0, 0)
    row.setSpacing(8)
    for b in buttons:
        row.addWidget(b)
    row.addStretch()
    return frame


class GenerateResumePage(QWidget):
    """Run the AI resume pipeline for a job and show the result and attempts."""

    def __init__(self, ctx: AppContext, parent=None):
        super().__init__(parent)
        self._ctx = ctx
        self._pool = WorkerPool(self)
        self._selected_app_uuid: str | None = None
        self._stream_stage: str | None = None

        # ── Left: inputs ─────────────────────────────────────────
        left, left_layout = vbox_widget((0, 8, 0, 0), spacing=10)
        left.setMinimumWidth(320)
        left_layout.addWidget(label("Fill from Application"))
        self._app_picker = ApplicationPicker(saved_applications)
        self._app_picker.picked.connect(self._fill_from_application)
        left_layout.addWidget(self._app_picker)

        self._name_input = line_edit("e.g. Anthropic")
        self._url_input = line_edit("https://www.example.com")
        self._title_input = line_edit("e.g. Software Engineer Intern")
        form_row = QHBoxLayout()
        form_row.setSpacing(8)
        for caption, edit, stretch in (
            ("Company Name *", self._name_input, 1), ("Website (optional)", self._url_input, 2),
        ):
            col = field(caption, edit)
            col.setSpacing(4)
            form_row.addLayout(col, stretch)
        left_layout.addLayout(form_row)
        title_col = field("Job Title (optional)", self._title_input)
        title_col.setSpacing(4)
        left_layout.addLayout(title_col)

        left_layout.addWidget(label("Job Description"))
        self._jd_input = QTextEdit()
        self._jd_input.setPlaceholderText("Paste the job description here…")
        left_layout.addWidget(self._jd_input, 1)

        self._gen_btn = BusyButton("📄  Generate Resume", "Generating…")
        self._gen_btn.clicked.connect(self._generate)
        left_layout.addWidget(self._gen_btn)
        self._status = status_label()
        left_layout.addWidget(self._status)

        # ── Right: live stream view, then results ────────────────
        right, right_layout = vbox_widget(spacing=0)
        self._stream_view = QPlainTextEdit()
        self._stream_view.setReadOnly(True)
        self._stream_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self._stream_view.setFont(mono_font())
        self._stream_view.setObjectName("code-stream")
        self._stream_view.setVisible(False)
        right_layout.addWidget(self._stream_view, 1)

        self._results_scroll, self._results = scroll_area(margins=(12, 0, 4, 16), spacing=10)
        self._results_scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        right_layout.addWidget(self._results_scroll, 1)

        set_titled_content(self, "Generate Resume", hsplitter(left, right, sizes=[400, 560]))

    def on_shown(self) -> None:
        self._app_picker.refresh()

    def _fill_from_application(self, entry: dict) -> None:
        self._name_input.setText(entry.get("company", "") or "")
        self._title_input.setText(entry.get("role", "") or "")
        self._jd_input.setPlainText(entry.get("description", "") or "")
        self._selected_app_uuid = entry.get("uuid") or None

    def _on_stream(self, stage: str, chunk: str) -> None:
        if stage != self._stream_stage:
            lead = "\n\n\n" if self._stream_stage is not None else ""
            append_stream_text(self._stream_view, f"{lead}══════ {stage} ══════\n\n")
            self._stream_stage = stage
        append_stream_text(self._stream_view, chunk)

    def _show_stream(self, streaming: bool) -> None:
        self._stream_view.setVisible(streaming)
        self._results_scroll.setVisible(not streaming)

    def _generate(self) -> None:
        jd = self._jd_input.toPlainText().strip()
        if not jd:
            set_status(self._status, "error", "Paste a job description first.")
            return
        name = self._name_input.text().strip()
        url = self._url_input.text().strip()

        clear_layout(self._results)
        self._stream_view.clear()
        self._stream_stage = None
        self._show_stream(True)
        self._gen_btn.set_busy(True)
        set_status(self._status, "neutral", "Starting…")

        def on_finished(payload: dict):
            self._gen_btn.set_busy(False)
            self._status.setText("")
            self._show_stream(False)
            resolve_pdf_collision(self, payload)
            self._render_results(payload)
            if payload.get("new_research") and name:
                self._ctx.research.put(name, url, payload["research"])
                self._ctx.save()

        def on_error(msg: str):
            self._gen_btn.set_busy(False)
            set_status(self._status, "error", f"Error: {msg}")

        self._pool.start(
            GenerateResumeWorker(
                self._ctx.get_profile(), jd, name, url, self._ctx.research.to_dict(),
                self._title_input.text().strip(),
                application_uuid=self._selected_app_uuid,
            ),
            progress=lambda msg: set_status(self._status, "neutral", msg),
            stream=self._on_stream,
            finished=on_finished,
            error=on_error,
        )
        self._selected_app_uuid = None

    def _render_results(self, payload: dict) -> None:
        layout = self._results
        layout.addWidget(label("COMPANY RESEARCH", "applier-section-header"))
        render_research(layout, payload.get("research") or {})

        fill = payload.get("fill")
        grade = payload.get("grade") or {}
        latex = payload.get("latex") or ""
        pdf = payload.get("pdf") or ""
        if not (latex or fill is not None or grade or pdf):
            return

        layout.addWidget(label("GENERATED RESUME", "applier-section-header"))
        layout.addWidget(result_row("Pages: (failed to compile)" if fill is None else f"Pages: {fill:.2f}"))
        if grade:
            layout.addWidget(result_row(f"Grade: {grade.get('score', 0):.2f}/10"))
            if grade.get("feedback"):
                layout.addWidget(result_row("Feedback: " + grade["feedback"]))
            if grade.get("drops"):
                layout.addWidget(result_row("Dropped for page-fit: " + "; ".join(grade["drops"])))

        buttons = []
        if pdf:
            open_btn = button("Open PDF")
            open_btn.clicked.connect(lambda: open_path(pdf))
            buttons.append(open_btn)
        if latex:
            copy_btn = button("Copy LaTeX", "secondary", 120)
            copy_btn.clicked.connect(lambda: copy_text(latex))
            buttons.append(copy_btn)
        layout.addWidget(_button_row(*buttons))

        attempts = payload.get("attempts") or []
        if len(attempts) > 1:
            layout.addWidget(label("ALL ATTEMPTS", "applier-section-header"))
            for attempt in attempts:
                self._render_attempt(attempt, payload.get("chosen_attempt"))

    def _render_attempt(self, attempt: dict, chosen) -> None:
        n = attempt.get("attempt")
        a_pdf = attempt.get("pdf") or ""
        a_grade = attempt.get("grade") or {}
        a_fill = attempt.get("fill")
        score = f"{a_grade.get('score', 0):.2f}/10" if a_grade else "ungraded"
        pages = f"{a_fill:.2f}pg" if a_fill is not None else "compile✗"
        mark = " ★" if n == chosen else ""

        btn = button(f"Attempt {n} ({score}, {pages}){mark}", "secondary")
        btn.setEnabled(bool(a_pdf))
        if a_pdf:
            btn.clicked.connect(lambda: open_path(a_pdf))
        row = _button_row(btn)
        row.layout().setContentsMargins(0, 0, 0, 0)
        self._results.addWidget(row)

        if attempt.get("compile_error"):
            self._results.addWidget(result_row("Compile error: " + attempt["compile_error"]))
        elif a_grade.get("feedback"):
            self._results.addWidget(result_row("Feedback: " + a_grade["feedback"]))
