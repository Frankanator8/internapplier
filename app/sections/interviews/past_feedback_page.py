from __future__ import annotations

import logging

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout, QListWidget, QSplitter, QTabWidget, QTextBrowser,
    QVBoxLayout, QWidget,
)

from ..base import _label

logger = logging.getLogger(__name__)


class PastFeedbackPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        outer.addWidget(splitter, 1)

        left = QWidget()
        left.setMinimumWidth(200)
        left.setMaximumWidth(320)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(16, 16, 8, 0)
        left_layout.setSpacing(6)
        left_layout.addWidget(_label("Saved Sessions"))

        self._list = QListWidget()
        self._list.setObjectName("company-cache-list")
        left_layout.addWidget(self._list, 1)
        splitter.addWidget(left)

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

        splitter.addWidget(self._right)
        splitter.setSizes([240, 700])

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
