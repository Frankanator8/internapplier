from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLineEdit, QMessageBox, QTextEdit,
    QVBoxLayout, QWidget,
)

from api.interview_links import (
    QuestionGroup, default_groups, grading_question, merge_groups, parse_entries,
    serialize_groups, unlink_question,
)
from app.ui.feedback_panel import FeedbackPanel
from app.ui.widgets import (
    BusyButton, button, clear_layout, icon_button, iter_widgets, label, line_edit,
    page_layout, scroll_area, section_header,
)
from app.ui.workers import WorkerPool

from .grading import GRADE_FORMAT_ERROR, grade_worker, parse_grade
from .link_picker import LinkPickerDialog


class QuestionGroupCard(QFrame):
    """One or more linked questions sharing a single drafted answer."""

    link_requested = pyqtSignal(object)        # source card
    remove_requested = pyqtSignal(object, int)  # card, question index
    grade_requested = pyqtSignal(object)
    edited = pyqtSignal()

    def __init__(self, questions: list[str], answer: str, group_id: str | None):
        super().__init__()
        self.setObjectName("card")
        self.group_id = group_id
        self._question_edits: list[QLineEdit] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(10)

        self._linked_badge = label("", "linked-badge")
        self._linked_badge.setVisible(False)
        badge_row = QHBoxLayout()
        badge_row.setContentsMargins(0, 0, 0, 0)
        badge_row.addWidget(self._linked_badge, 0, Qt.AlignmentFlag.AlignLeft)
        badge_row.addStretch()
        layout.addLayout(badge_row)

        self._rows = QVBoxLayout()
        self._rows.setContentsMargins(0, 0, 0, 0)
        self._rows.setSpacing(6)
        layout.addLayout(self._rows)

        answer_row = QHBoxLayout()
        answer_row.setSpacing(8)
        self.answer_edit = QTextEdit()
        self.answer_edit.setObjectName("answer-edit")
        self.answer_edit.setPlaceholderText("Draft your answer here…")
        self.answer_edit.setPlainText(answer or "")
        self.answer_edit.setMinimumHeight(160)
        answer_row.addWidget(self.answer_edit, 1)
        self.grade_btn = BusyButton("✦ AI Feedback", "…", "secondary", 110)
        self.grade_btn.setToolTip("Get AI feedback on your answer")
        self.grade_btn.clicked.connect(lambda: self.grade_requested.emit(self))
        answer_row.addWidget(self.grade_btn, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(answer_row)

        self.feedback = FeedbackPanel(with_title=True)
        layout.addWidget(self.feedback)

        for q in questions or [""]:
            self._add_question_row(q)
        self._refresh_badge()

    def _add_question_row(self, text: str) -> None:
        edit = line_edit("Question…", text)
        edit.setObjectName("question-edit")
        edit.textChanged.connect(self.edited.emit)
        link_btn = icon_button("🔗", tooltip="Link to another question")
        link_btn.clicked.connect(lambda: self.link_requested.emit(self))
        remove_btn = icon_button(tooltip="Remove / unlink question")
        remove_btn.clicked.connect(lambda: self.remove_requested.emit(self, self._question_edits.index(edit)))

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)
        row_layout.addWidget(edit, 1)
        row_layout.addWidget(link_btn, 0, Qt.AlignmentFlag.AlignTop)
        row_layout.addWidget(remove_btn, 0, Qt.AlignmentFlag.AlignTop)
        self._rows.addWidget(row)
        self._question_edits.append(edit)

    def _refresh_badge(self) -> None:
        n = len(self._question_edits)
        self._linked_badge.setText(f"Linked · {n}")
        self._linked_badge.setVisible(n >= 2)
        if n < 2:
            self.group_id = None

    def questions(self) -> list[str]:
        return [e.text() for e in self._question_edits]

    def answer(self) -> str:
        return self.answer_edit.toPlainText()

    def snapshot(self) -> QuestionGroup:
        return QuestionGroup(group_id=self.group_id, questions=self.questions(), answer=self.answer())

    def matches(self, query: str) -> bool:
        return query in "\n".join([*self.questions(), self.answer()]).lower()


class InterviewQuestionsPage(QWidget):
    """Editable bank of interview questions with drafted answers and AI grading.

    Questions that share an answer can be linked into one card. Data is the
    ``api.interview_links`` entry list.
    """

    def __init__(
        self,
        get_profile: Callable[[], dict],
        get_job_context: Callable[[], dict | None] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._get_profile = get_profile
        self._get_job_context = get_job_context
        self._pool = WorkerPool(self)

        outer = page_layout(self)
        self._search_edit = line_edit("Search questions…")
        self._search_edit.setFixedWidth(240)
        self._search_edit.textChanged.connect(self._apply_filter)
        top_add_btn = button("+ Add Question")
        top_add_btn.clicked.connect(self._add_blank)
        outer.addLayout(section_header("Interview Questions", self._search_edit, top_add_btn))

        scroll, self._cards_layout = scroll_area()
        outer.addWidget(scroll, 1)

        bottom_row = QHBoxLayout()
        bottom_row.addStretch()
        bottom_add_btn = button("+ Add Question")
        bottom_add_btn.clicked.connect(self._add_blank)
        bottom_row.addWidget(bottom_add_btn)
        bottom_row.addStretch()
        outer.addLayout(bottom_row)

    # ── Data ────────────────────────────────────────────────────
    def get_data(self) -> list[dict]:
        return serialize_groups(self._snapshot())

    def load(self, value: list[dict] | None) -> None:
        self._rebuild(default_groups() if value is None else parse_entries(value))

    def _cards(self) -> list[QuestionGroupCard]:
        return [w for w in iter_widgets(self._cards_layout) if isinstance(w, QuestionGroupCard)]

    def _snapshot(self) -> list[QuestionGroup]:
        return [card.snapshot() for card in self._cards()]

    def _rebuild(self, groups: list[QuestionGroup]) -> None:
        clear_layout(self._cards_layout)
        for g in groups:
            self._add_group(list(g.questions) or [""], g.answer, g.group_id)

    def _add_blank(self) -> None:
        self._add_group([""], "", None)

    def _add_group(self, questions: list[str], answer: str, group_id: str | None) -> None:
        card = QuestionGroupCard(questions, answer, group_id)
        card.edited.connect(lambda: self._apply_filter(self._search_edit.text()))
        card.link_requested.connect(self._link)
        card.remove_requested.connect(self._remove_question)
        card.grade_requested.connect(self._grade)
        self._cards_layout.addWidget(card)
        self._apply_filter(self._search_edit.text())

    def _apply_filter(self, text: str) -> None:
        query = (text or "").strip().lower()
        for card in self._cards():
            card.setVisible(not query or card.matches(query))

    # ── Linking ─────────────────────────────────────────────────
    def _link(self, source: QuestionGroupCard) -> None:
        cards = self._cards()
        source_idx = cards.index(source)
        targets = [i for i, c in enumerate(cards) if c is not source]
        if not targets:
            QMessageBox.information(self, "Link question", "There are no other questions to link to.")
            return

        candidates = []
        for i in targets:
            questions = cards[i].questions()
            group_label = f"linked group ({len(questions)})" if len(questions) >= 2 else None
            candidates.append((questions[0] if questions else "", group_label))
        dlg = LinkPickerDialog(candidates, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted or dlg.selected_index() is None:
            return
        target_idx = targets[dlg.selected_index()]

        groups = self._snapshot()
        answer_choice = self._choose_answer(groups[source_idx].answer, groups[target_idx].answer)
        if answer_choice is not None:
            self._rebuild(merge_groups(groups, source_idx, target_idx, answer_choice))

    def _choose_answer(self, source_answer: str, target_answer: str) -> str | None:
        """Which answer a merged group keeps: "auto", "source", "target", or None to cancel."""
        s, t = source_answer.strip(), target_answer.strip()
        if not (s and t and s != t):
            return "auto"
        box = QMessageBox(self)
        box.setWindowTitle("Conflicting answers")
        box.setText("Both questions have answers. Which one should the linked group keep?")
        src_btn = box.addButton("Keep source", QMessageBox.ButtonRole.AcceptRole)
        tgt_btn = box.addButton("Keep target", QMessageBox.ButtonRole.AcceptRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        return {src_btn: "source", tgt_btn: "target"}.get(box.clickedButton())

    def _remove_question(self, card: QuestionGroupCard, question_idx: int) -> None:
        if len(card.questions()) == 1:
            # The only question of a standalone card: delete the card.
            self._cards_layout.removeWidget(card)
            card.setParent(None)
            card.deleteLater()
            return
        group_idx = self._cards().index(card)
        self._rebuild(unlink_question(self._snapshot(), group_idx, question_idx))

    # ── Grading ─────────────────────────────────────────────────
    def _grade(self, card: QuestionGroupCard) -> None:
        questions = [q.strip() for q in card.questions() if q.strip()]
        answer = card.answer().strip()
        if not questions or not answer:
            return
        card.feedback.begin("GENERATING…")
        card.grade_btn.set_busy(True)

        def on_finished(buf: str):
            card.grade_btn.set_busy(False)
            parsed = parse_grade(buf)
            if parsed is None:
                card.feedback.set_title("AI FEEDBACK · ERROR")
                card.feedback.set_text(GRADE_FORMAT_ERROR)
                return
            score, feedback = parsed
            card.feedback.set_title(f"AI FEEDBACK · SCORE {score}/10")
            card.feedback.set_text(feedback or "No feedback — answer looks strong.")

        def on_error(msg: str):
            card.grade_btn.set_busy(False)
            card.feedback.set_title("AI FEEDBACK · ERROR")
            card.feedback.set_text(msg)

        job = self._get_job_context() if self._get_job_context else None
        self._pool.start(
            grade_worker(grading_question(questions), answer, self._get_profile(), job),
            finished=on_finished,
            error=on_error,
        )
