from __future__ import annotations

from html import escape

from PyQt6.QtCore import QUrl, Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWebEngineCore import QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from api import leetcode_store
from app.theme import current_palette
from app.ui.widgets import button, hint, label, page_layout, section_header

from .deck_combo import DeckCombo

# (rating, label, button kind)
_GRADES = [
    ("again", "Again", "danger"),
    ("hard", "Hard", "secondary"),
    ("good", "Good", "primary"),
    ("easy", "Easy", "secondary"),
]


class ReviewPage(QWidget):
    """Anki-style review: show front, reveal back, then grade the card."""

    cards_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._queue: list[str] = []
        self._current: dict | None = None
        self._showing_answer = False

        outer = page_layout(self)
        self._remaining = label("", "muted")
        outer.addLayout(section_header("Review", self._remaining))

        deck_row = QHBoxLayout()
        deck_row.addWidget(label("Deck"))
        self._deck_combo = DeckCombo(
            all_label=lambda decks: f"All decks ({sum(d['due'] for d in decks)} due)",
            deck_label=lambda d: f"{d['name']}  ·  {d['due']} due / {d['total']}",
        )
        self._deck_combo.setMinimumWidth(280)
        self._deck_combo.currentIndexChanged.connect(self._start_session)
        deck_row.addWidget(self._deck_combo, 1)
        outer.addLayout(deck_row)

        self._view = QWebEngineView()
        settings = self._view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, False)
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True
        )
        outer.addWidget(self._view, 1)

        outer.addWidget(hint("Space to show the answer · 1 Again · 2 Hard · 3 Good · 4 Easy"))

        self._show_btn = button("Show Answer")
        self._show_btn.clicked.connect(self._on_show_answer)
        outer.addWidget(self._show_btn)

        self._grade_row = QWidget()
        grade_layout = QHBoxLayout(self._grade_row)
        grade_layout.setContentsMargins(0, 0, 0, 0)
        grade_layout.setSpacing(8)
        self._grade_buttons: dict[str, QPushButton] = {}
        for rating, text, kind in _GRADES:
            btn = button(text, kind)
            btn.setMinimumWidth(110)
            btn.clicked.connect(lambda _=False, r=rating: self._on_grade(r))
            grade_layout.addWidget(btn)
            self._grade_buttons[rating] = btn
        grade_layout.addStretch()
        outer.addWidget(self._grade_row)

        space = QShortcut(QKeySequence(Qt.Key.Key_Space), self)
        space.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        space.activated.connect(self._on_show_answer)
        for i, rating in enumerate(leetcode_store.RATINGS, start=1):
            shortcut = QShortcut(QKeySequence(str(i)), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(lambda r=rating: self._on_grade(r))

        self.refresh()

    def refresh(self) -> None:
        self._deck_combo.reload()
        self._start_session()

    on_shown = refresh

    def _start_session(self) -> None:
        cards = leetcode_store.due_cards(self._deck_combo.selected_deck())
        self._queue = [c["id"] for c in cards]
        self._show_next()

    def _show_next(self) -> None:
        self._showing_answer = False
        if not self._queue:
            self._current = None
            self._remaining.setText("0 remaining")
            decks = leetcode_store.list_decks()
            if not decks:
                self._render_message(
                    "No cards yet",
                    "Add cards or import an Anki deck from the Browse tab.",
                )
            else:
                self._render_message(
                    "You're done for today",
                    "No cards are due in this deck. Check back tomorrow, or add more cards.",
                )
            self._show_btn.setVisible(False)
            self._grade_row.setVisible(False)
            return

        self._current = leetcode_store.get_card(self._queue[0])
        if self._current is None:
            self._queue.pop(0)
            self._show_next()
            return
        self._remaining.setText(f"{len(self._queue)} remaining")
        self._render_card(answer=False)
        self._show_btn.setVisible(True)
        self._grade_row.setVisible(False)

    def _on_show_answer(self) -> None:
        if not self._current or self._showing_answer:
            return
        self._showing_answer = True
        self._render_card(answer=True)
        self._show_btn.setVisible(False)
        self._update_grade_labels()
        self._grade_row.setVisible(True)

    def _update_grade_labels(self) -> None:
        intervals = leetcode_store.preview_intervals(self._current)
        for rating, text, _kind in _GRADES:
            self._grade_buttons[rating].setText(f"{text}  ·  {intervals[rating]}")

    def _on_grade(self, rating: str) -> None:
        if not self._current or not self._showing_answer:
            return
        card_id = self._current["id"]
        leetcode_store.grade(card_id, rating)
        if self._queue and self._queue[0] == card_id:
            self._queue.pop(0)
        if rating == "again":
            self._queue.append(card_id)
        self.cards_changed.emit()
        self._deck_combo.reload()
        self._show_next()

    def _media_base(self) -> QUrl:
        media = leetcode_store.media_dir()
        return QUrl.fromLocalFile(str(media.resolve()) + "/")

    def _render_card(self, answer: bool) -> None:
        card = self._current or {}
        front = leetcode_store.render_side(card.get("front") or "", reveal_cloze=answer)
        body = f'<div class="front">{front}</div>'
        if answer:
            back = leetcode_store.render_side(card.get("back") or "", reveal_cloze=True)
            body += '<hr id="answer">'
            body += f'<div class="back">{back}</div>'
        self._view.setHtml(self._wrap_html(body), self._media_base())

    def _render_message(self, title: str, detail: str) -> None:
        body = (
            f'<div class="empty"><h2>{escape(title)}</h2>'
            f"<p>{escape(detail)}</p></div>"
        )
        self._view.setHtml(self._wrap_html(body), self._media_base())

    def _wrap_html(self, body: str) -> str:
        pal = current_palette()
        return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  html, body {{
    margin: 0; padding: 0;
    background: {pal["surface_card"]};
    color: {pal["text"]};
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    font-size: 16px;
    line-height: 1.55;
  }}
  body {{ padding: 28px 32px; }}
  img {{ max-width: 100%; height: auto; }}
  hr {{
    border: none;
    border-top: 1px solid {pal["border"]};
    margin: 22px 0;
  }}
  pre, code {{
    font-family: ui-monospace, Menlo, Consolas, monospace;
    font-size: 13px;
  }}
  pre {{
    background: {pal["surface_code"]};
    color: {pal["text_code"]};
    border: 1px solid {pal["border_code"]};
    border-radius: 8px;
    padding: 12px 14px;
    overflow-x: auto;
  }}
  .cloze {{
    color: {pal["accent"]};
    font-weight: 600;
  }}
  .cloze-reveal {{
    background: {pal["accent_soft_bg"]};
    color: {pal["accent"]};
    padding: 0 4px;
    border-radius: 4px;
  }}
  .empty {{
    text-align: center;
    padding: 64px 24px;
    color: {pal["text_muted"]};
  }}
  .empty h2 {{
    color: {pal["text"]};
    font-size: 22px;
    font-weight: 600;
    margin-bottom: 8px;
  }}
</style></head>
<body>{body}</body></html>"""
