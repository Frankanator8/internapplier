import pytest

from api import app_settings as s
from api._settings_base import _set


pytestmark = pytest.mark.usefixtures("isolated_app_dir")


class TestThemePreference:
    def test_default_is_system(self):
        assert s.get_theme_preference() == "system"

    def test_invalid_normalized(self):
        s.save_theme_preference("rainbow")
        assert s.get_theme_preference() == "system"

    def test_valid_choices(self):
        for v in ("light", "dark", "system"):
            s.save_theme_preference(v)
            assert s.get_theme_preference() == v


class TestHeatmapThresholds:
    def test_default_when_not_set(self):
        assert s.get_heatmap_day_thresholds() == [1, 2, 3, 4]

    def test_must_be_sorted_and_length_4(self):
        s.save_heatmap_day_thresholds([10, 5, 2, 1])  # sorted internally
        assert s.get_heatmap_day_thresholds() == [1, 2, 5, 10]

    def test_rejects_non_strict_ascending(self):
        # writing equal values should round-trip but fail validation on read
        _set("heatmap_day_thresholds", [1, 1, 2, 3])
        assert s.get_heatmap_day_thresholds() == [1, 2, 3, 4]  # fallback


class TestScraperCandidatePaths:
    def test_default_returned(self):
        out = s.get_scraper_candidate_paths()
        assert "/" in out

    def test_round_trip(self):
        s.save_scraper_candidate_paths(["/x", "/y"])
        assert s.get_scraper_candidate_paths() == ["/x", "/y"]


class TestWritingSample:
    def test_default_empty(self):
        assert s.get_writing_sample() == ""

    def test_round_trip(self):
        s.save_writing_sample("I write like this.")
        assert s.get_writing_sample() == "I write like this."
