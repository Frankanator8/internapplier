from __future__ import annotations

import logging
from typing import Callable

from PyQt6.QtCore import QObject, QThread, Qt
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton, QScrollArea,
    QTextEdit, QVBoxLayout, QWidget,
)

from api.interview_links import (
    QuestionGroup,
    default_groups,
    merge_groups,
    parse_entries,
    serialize_groups,
    unlink_question,
)
from api.interview_parsing import parse_grade_payload

from ..base import _icon_btn, _label, _primary_btn, _secondary_btn
from .workers import _GradeWorker

logger = logging.getLogger(__name__)


class _LinkPickerDialog(QDialog):
    """Modal dialog to pick another question to link to."""

    def __init__(self, candidates: list[tuple[str, str | None]], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Link to question")
        self.setMinimumWidth(420)
        self._selected_index: int | None = None
        self._candidates = candidates

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        layout.addWidget(QLabel("Select a question to link with:"))

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search…")
        self._search.textChanged.connect(self._refilter)
        layout.addWidget(self._search)

        self._list = QListWidget()
        self._list.itemDoubleClicked.connect(lambda _i: self._accept())
        layout.addWidget(self._list, 1)

        self._populate("")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate(self, query: str):
        self._list.clear()
        q = query.strip().lower()
        for idx, (text, group_label) in enumerate(self._candidates):
            display = text if text else "(empty question)"
            if group_label:
                display = f"{display}   · {group_label}"
            if q and q not in text.lower():
                continue
            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, idx)
            self._list.addItem(item)

    def _refilter(self, text: str):
        self._populate(text)

    def _accept(self):
        item = self._list.currentItem()
        if item is None:
            return
        self._selected_index = item.data(Qt.ItemDataRole.UserRole)
        self.accept()

    def selected_index(self) -> int | None:
        return self._selected_index


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
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Search questions…")
        self._search_edit.setFixedWidth(240)
        self._search_edit.textChanged.connect(self._apply_filter)
        header_row.addWidget(self._search_edit)
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

    def cleanup_threads(self) -> None:
        from .._thread_cleanup import shutdown_threads
        shutdown_threads(self._threads)
        self._workers.clear()

    # ------------------------------------------------------------------ #
    # Snapshot / rebuild helpers
    # ------------------------------------------------------------------ #

    def _snapshot_groups(self) -> list[QuestionGroup]:
        """Read current widget state into pure-data QuestionGroup objects."""
        groups: list[QuestionGroup] = []
        for card in self._all_cards():
            edits: list[QLineEdit] = card.property("_question_edits") or []
            answer_edit: QTextEdit = card.property("_answer")
            gid = card.property("_group_id")
            questions = [qe.text() for qe in edits]
            if gid is not None and len(questions) < 2:
                gid = None
            groups.append(QuestionGroup(
                group_id=gid,
                questions=questions,
                answer=answer_edit.toPlainText() if answer_edit else "",
            ))
        return groups

    def _rebuild_from(self, groups: list[QuestionGroup]) -> None:
        self._clear()
        for g in groups:
            self._add_group(list(g.questions) or [""], g.answer, g.group_id)

    # ------------------------------------------------------------------ #
    # Card construction
    # ------------------------------------------------------------------ #

    def _add_blank(self):
        self._add_group([""], "", None)

    def add_entry(self, data: dict | None = None):
        """Backwards-compatible single-question entry."""
        data = data or {}
        self._add_group(
            [data.get("question", "")],
            data.get("answer", ""),
            data.get("group_id") or None,
        )

    def _add_group(
        self,
        questions: list[str],
        answer: str,
        group_id: str | None,
    ) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        vbox = QVBoxLayout(card)
        vbox.setContentsMargins(20, 18, 20, 16)
        vbox.setSpacing(10)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(8)
        linked_label = QLabel("")
        linked_label.setStyleSheet(
            "QLabel { color: #6b7280; font-size: 12px; font-weight: 600;"
            " padding: 2px 8px; border: 1px solid #d1d5db; border-radius: 10px; }"
        )
        linked_label.setVisible(False)
        header_row.addWidget(linked_label, 0, Qt.AlignmentFlag.AlignLeft)
        header_row.addStretch()
        vbox.addLayout(header_row)

        rows_container = QWidget()
        rows_layout = QVBoxLayout(rows_container)
        rows_layout.setContentsMargins(0, 0, 0, 0)
        rows_layout.setSpacing(6)
        vbox.addWidget(rows_container)

        answer_row = QHBoxLayout()
        answer_row.setSpacing(8)
        answer_edit = QTextEdit()
        answer_edit.setPlaceholderText("Draft your answer here…")
        answer_edit.setPlainText(answer or "")
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

        card.setProperty("_group_id", group_id)
        card.setProperty("_rows_container", rows_container)
        card.setProperty("_rows_layout", rows_layout)
        card.setProperty("_question_edits", [])
        card.setProperty("_linked_label", linked_label)
        card.setProperty("_answer", answer_edit)
        card.setProperty("_fb_panel", fb_panel)
        card.setProperty("_fb_title", fb_title)
        card.setProperty("_fb_body", fb_body)
        card.setProperty("_fb_buffer", "")

        fb_dismiss.clicked.connect(lambda: self._hide_feedback(card))
        grade_btn.clicked.connect(
            lambda _checked=False, c=card, b=grade_btn: self._grade(c, b)
        )

        for q in (questions if questions else [""]):
            self._append_question_row(card, q)

        self._refresh_group_chrome(card)

        self._cards_layout.addWidget(card)
        self._apply_filter(self._search_edit.text())
        return card

    def _append_question_row(self, card: QFrame, text: str) -> None:
        rows_layout: QVBoxLayout = card.property("_rows_layout")
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        question_edit = QLineEdit(text)
        question_edit.setPlaceholderText("Question…")
        question_edit.setStyleSheet(
            "QLineEdit { font-size: 15px; font-weight: 600; border: none;"
            " background: transparent; padding: 2px 0; }"
        )
        question_edit.textChanged.connect(
            lambda _t=None: self._apply_filter(self._search_edit.text())
        )

        link_btn = _icon_btn("🔗")
        link_btn.setToolTip("Link to another question")
        link_btn.clicked.connect(
            lambda _checked=False, c=card, qe=question_edit: self._open_link_picker(c, qe)
        )

        remove_btn = _icon_btn("✕")
        remove_btn.setToolTip("Remove / unlink question")
        remove_btn.clicked.connect(
            lambda _checked=False, c=card, qe=question_edit: self._remove_row(c, qe)
        )

        row_layout.addWidget(question_edit, 1)
        row_layout.addWidget(link_btn, 0, Qt.AlignmentFlag.AlignTop)
        row_layout.addWidget(remove_btn, 0, Qt.AlignmentFlag.AlignTop)

        row.setProperty("_question_edit", question_edit)

        rows_layout.addWidget(row)

        edits: list[QLineEdit] = list(card.property("_question_edits") or [])
        edits.append(question_edit)
        card.setProperty("_question_edits", edits)

    def _refresh_group_chrome(self, card: QFrame) -> None:
        edits: list[QLineEdit] = card.property("_question_edits") or []
        linked_label: QLabel = card.property("_linked_label")
        n = len(edits)
        if n >= 2:
            linked_label.setText(f"Linked · {n}")
            linked_label.setVisible(True)
        else:
            linked_label.setVisible(False)
            card.setProperty("_group_id", None)

    # ------------------------------------------------------------------ #
    # Linking
    # ------------------------------------------------------------------ #

    def _all_cards(self) -> list[QFrame]:
        out: list[QFrame] = []
        for i in range(self._cards_layout.count()):
            w = self._cards_layout.itemAt(i).widget()
            if isinstance(w, QFrame):
                out.append(w)
        return out

    def _open_link_picker(self, source_card: QFrame, source_edit: QLineEdit) -> None:
        cards = self._all_cards()
        source_idx = cards.index(source_card)

        candidates: list[tuple[str, str | None]] = []
        index_map: list[int] = []  # candidate position -> target group index
        for idx, card in enumerate(cards):
            if card is source_card:
                continue
            edits: list[QLineEdit] = card.property("_question_edits") or []
            first_text = edits[0].text() if edits else ""
            group_label = None
            if len(edits) >= 2:
                group_label = f"linked group ({len(edits)})"
            candidates.append((first_text, group_label))
            index_map.append(idx)

        if not candidates:
            QMessageBox.information(
                self, "Link question",
                "There are no other questions to link to."
            )
            return

        dlg = _LinkPickerDialog(candidates, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        picked = dlg.selected_index()
        if picked is None:
            return
        target_idx = index_map[picked]

        # Snapshot live widget state, then ask the api layer to merge.
        groups = self._snapshot_groups()
        source_g = groups[source_idx]
        target_g = groups[target_idx]

        answer_choice = "auto"
        s_ans = source_g.answer.strip()
        t_ans = target_g.answer.strip()
        if s_ans and t_ans and s_ans != t_ans:
            box = QMessageBox(self)
            box.setWindowTitle("Conflicting answers")
            box.setText("Both questions have answers. Which one should the linked group keep?")
            src_btn = box.addButton("Keep source", QMessageBox.ButtonRole.AcceptRole)
            tgt_btn = box.addButton("Keep target", QMessageBox.ButtonRole.AcceptRole)
            box.addButton(QMessageBox.StandardButton.Cancel)
            box.exec()
            clicked = box.clickedButton()
            if clicked is src_btn:
                answer_choice = "source"
            elif clicked is tgt_btn:
                answer_choice = "target"
            else:
                return

        new_groups = merge_groups(groups, source_idx, target_idx, answer_choice)
        self._rebuild_from(new_groups)

    # ------------------------------------------------------------------ #
    # Unlinking / removal
    # ------------------------------------------------------------------ #

    def _remove_row(self, card: QFrame, question_edit: QLineEdit) -> None:
        edits: list[QLineEdit] = card.property("_question_edits") or []
        if question_edit not in edits:
            return

        # Standalone card: deleting the only question deletes the card itself.
        if len(edits) == 1:
            self._cards_layout.removeWidget(card)
            card.setParent(None)
            card.deleteLater()
            return

        # Multi-member group: delegate the unlink to the api layer.
        cards = self._all_cards()
        group_idx = cards.index(card)
        question_idx = edits.index(question_edit)

        groups = self._snapshot_groups()
        new_groups = unlink_question(groups, group_idx, question_idx)
        self._rebuild_from(new_groups)

    # ------------------------------------------------------------------ #
    # Filter / feedback / persistence
    # ------------------------------------------------------------------ #

    def _apply_filter(self, text: str):
        query = (text or "").strip().lower()
        for card in self._all_cards():
            if not query:
                card.setVisible(True)
                continue
            edits: list[QLineEdit] = card.property("_question_edits") or []
            answer_edit: QTextEdit = card.property("_answer")
            haystack_parts = [qe.text() for qe in edits]
            if answer_edit is not None:
                haystack_parts.append(answer_edit.toPlainText())
            haystack = "\n".join(haystack_parts).lower()
            card.setVisible(query in haystack)

    def _grade(self, card: QFrame, grade_btn: QPushButton):
        edits: list[QLineEdit] = card.property("_question_edits") or []
        answer_edit: QTextEdit = card.property("_answer")
        questions = [qe.text().strip() for qe in edits if qe.text().strip()]
        answer = answer_edit.toPlainText().strip()
        if not questions or not answer:
            return

        if len(questions) == 1:
            question_arg = questions[0]
        else:
            bullets = "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))
            question_arg = (
                "You are evaluating one answer that the candidate uses for "
                "multiple related questions:\n" + bullets
            )

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
            question_arg,
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

    def _clear(self):
        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def get_data(self) -> list[dict]:
        return serialize_groups(self._snapshot_groups())

    def load(self, value: list[dict] | None):
        self._clear()
        groups = default_groups() if value is None else parse_entries(value)
        for g in groups:
            self._add_group(list(g.questions) or [""], g.answer, g.group_id)
