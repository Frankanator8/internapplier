from __future__ import annotations

import logging

from PyQt6.QtWidgets import QHBoxLayout, QTabWidget, QTextBrowser, QWidget

from api.data_store import load_interview_feedback
from api.interview_sessions import cards_markdown, session_label, transcript_markdown
from app.ui.widgets import hsplitter, label, list_pane, vbox_widget

logger = logging.getLogger(__name__)


class PastFeedbackPage(QWidget):
    """Read-only browser of saved Interview Practice sessions, newest first."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sessions: list[dict] = []

        left, _layout, self._list = list_pane("Saved Sessions")
        self._list.currentRowChanged.connect(self._on_select)

        right, right_layout = vbox_widget((20, 18, 20, 14), spacing=10)
        right_layout.addWidget(label("Past Feedback", "section-title"))
        tabs = QTabWidget()
        self._transcript_view = QTextBrowser()
        self._cards_view = QTextBrowser()
        self._notes_view = QTextBrowser()
        tabs.addTab(self._transcript_view, "Transcript")
        tabs.addTab(self._cards_view, "Per-Answer")
        tabs.addTab(self._notes_view, "Overall Notes")
        right_layout.addWidget(tabs, 1)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(hsplitter(left, right, sizes=[240, 700]), 1)

    def showEvent(self, event):  # noqa: N802 (Qt API)
        super().showEvent(event)
        self._refresh()

    def _refresh(self) -> None:
        try:
            self._sessions = load_interview_feedback() or []
        except Exception:
            logger.exception("PastFeedbackPage — load failed")
            self._sessions = []
        self._sessions.sort(key=lambda s: s.get("started_at", ""), reverse=True)
        self._list.clear()
        self._list.addItems([session_label(s) for s in self._sessions])
        if self._sessions:
            self._list.setCurrentRow(0)
        else:
            self._transcript_view.setMarkdown(
                "_No past sessions yet. Run a chat in Interview Practice and click "
                "🆕 New Chat or close the app to save feedback here._"
            )
            self._cards_view.setMarkdown("")
            self._notes_view.setMarkdown("")

    def _on_select(self, row: int) -> None:
        if not (0 <= row < len(self._sessions)):
            return
        session = self._sessions[row]
        self._transcript_view.setMarkdown(transcript_markdown(session))
        self._cards_view.setMarkdown(cards_markdown(session))
        self._notes_view.setMarkdown(session.get("notes_md") or "_No notes saved._")
