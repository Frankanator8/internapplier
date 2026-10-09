from datetime import date, timedelta

import pytest

from api import leetcode_store as store


pytestmark = pytest.mark.usefixtures("isolated_app_dir")


@pytest.fixture
def freeze_today(monkeypatch):
    monkeypatch.setattr(store, "today", lambda: date(2026, 9, 16))
    return date(2026, 9, 16)


class TestPersistence:
    def test_load_empty_when_no_file(self):
        assert store.load() == {"cards": []}
        assert store.list_cards() == []
        assert store.list_decks() == []

    def test_add_and_round_trip(self, freeze_today):
        card = store.add_card("Two Sum", "Use a hashmap", "Blind 75", ["array"])
        assert card["deck"] == "Blind 75"
        assert card["due"] == "2026-09-16"
        assert card["ease"] == store.DEFAULT_EASE
        store.invalidate()
        loaded = store.list_cards()
        assert len(loaded) == 1
        assert loaded[0]["front"] == "Two Sum"
        assert loaded[0]["tags"] == ["array"]

    def test_update_and_delete(self):
        card = store.add_card("Q", "A", "DP")
        updated = store.update_card(card["id"], front="Q2", back="A2", deck="Graphs")
        assert updated["front"] == "Q2"
        assert updated["deck"] == "Graphs"
        assert store.delete_card(card["id"]) is True
        assert store.get_card(card["id"]) is None

    def test_add_cards_skips_empty(self):
        created = store.add_cards([
            {"front": "A", "back": "B", "deck": "X"},
            {"front": "  ", "back": "", "deck": "X"},
        ])
        assert len(created) == 1
        assert len(store.list_cards()) == 1


class TestScheduling:
    def test_new_card_learning_steps(self, freeze_today):
        card = store.add_card("Q", "A")
        intervals = store.preview_intervals(card)
        assert intervals["again"] == "<1d"
        assert intervals["hard"] == "1d"
        assert intervals["good"] == "1d"
        assert intervals["easy"] == "4d"

        store.grade_card(card, "good")
        assert card["repetitions"] == 1
        assert card["interval_days"] == 1
        assert card["due"] == "2026-09-17"

        store.grade_card(card, "good")
        assert card["repetitions"] == 2
        assert card["interval_days"] == 3
        assert card["due"] == (freeze_today + timedelta(days=3)).isoformat()

    def test_again_resets_and_counts_lapse(self, freeze_today):
        card = store.add_card("Q", "A")
        store.grade_card(card, "easy")
        assert card["repetitions"] == 2
        store.grade_card(card, "again")
        assert card["repetitions"] == 0
        assert card["interval_days"] == 0
        assert card["lapses"] == 1
        assert card["due"] == "2026-09-16"
        assert card["ease"] < store.DEFAULT_EASE

    def test_graduated_good_multiplies_ease(self, freeze_today):
        card = store._new_card("Q", "A")
        card["repetitions"] = 2
        card["interval_days"] = 3
        card["ease"] = 2.5
        store.grade_card(card, "good")
        assert card["interval_days"] == 8
        assert card["repetitions"] == 3
        assert card["due"] == (freeze_today + timedelta(days=8)).isoformat()

    def test_due_cards_filters_by_deck_and_date(self, freeze_today):
        a = store.add_card("now", "a", "A")
        b = store.add_card("later", "b", "B")
        store.grade(b["id"], "good")  # due tomorrow
        assert [c["id"] for c in store.due_cards()] == [a["id"]]
        assert store.due_cards("B") == []
        assert len(store.due_cards("A")) == 1
        decks = {d["name"]: d for d in store.list_decks()}
        assert decks["A"]["due"] == 1
        assert decks["B"]["due"] == 0

    def test_format_interval(self):
        assert store.format_interval(0) == "<1d"
        assert store.format_interval(12) == "12d"
        assert store.format_interval(45) == "2mo"
        assert store.format_interval(400) == "1.1y"

    def test_grade_unknown_rating(self):
        with pytest.raises(ValueError):
            store.grade_card(store._new_card("Q", "A"), "maybe")


class TestRender:
    def test_plain_preview_strips_html_and_cloze(self):
        text = "<b>Two {{c1::Sum}}</b><br>hash"
        assert store.plain_preview(text) == "Two Sum hash"

    def test_render_side_hides_and_reveals_cloze(self):
        text = "Use a {{c1::hashmap::hint}}"
        hidden = store.render_side(text, reveal_cloze=False)
        assert "[hint]" in hidden
        assert "hashmap" not in hidden
        shown = store.render_side(text, reveal_cloze=True)
        assert "hashmap" in shown
        assert "[sound:foo.mp3]" not in store.render_side("x[sound:foo.mp3]y")
