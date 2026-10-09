from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# QtWebEngine must be imported before QApplication is constructed. Importing
# the browse page pulls in the package, which imports ReviewPage/WebEngine.
from app.sections.leetcode.browse_page import BrowsePage  # noqa: E402
from app.sections.leetcode.card_dialog import CardEditorDialog  # noqa: E402

pytestmark = pytest.mark.usefixtures("isolated_app_dir")


def test_browse_page_lists_added_cards(qapp):
    from api import leetcode_store

    leetcode_store.add_card("Two Sum", "Hash map", "Blind 75", ["array"])
    page = BrowsePage()
    assert page._table.rowCount() == 1
    assert page._table.item(0, 0).text() == "Blind 75"
    assert "Two Sum" in page._table.item(0, 1).text()


def test_card_editor_dialog_round_trip(qapp):
    dlg = CardEditorDialog(
        decks=["Blind 75"],
        card={"deck": "Blind 75", "front": "Q", "back": "A", "tags": ["t1"]},
    )
    assert dlg.get_data()["front"] == "Q"
    assert dlg.get_data()["deck"] == "Blind 75"
    assert dlg.get_data()["tags"] == ["t1"]
