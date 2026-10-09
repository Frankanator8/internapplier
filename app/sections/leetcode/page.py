from __future__ import annotations

from app.ui.sidebar_stack import SidebarStack

from .browse_page import BrowsePage
from .review_page import ReviewPage


class LeetcodePage(SidebarStack):
    """Spaced-repetition flashcards: review due cards, browse and edit the deck."""

    def __init__(self, parent=None):
        super().__init__(parent)
        review = self.add_page("🎯  Review", ReviewPage())
        browse = self.add_page("🗂  Browse", BrowsePage())
        review.cards_changed.connect(browse.refresh)
        browse.cards_changed.connect(review.refresh)
