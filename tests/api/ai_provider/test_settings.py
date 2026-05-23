import pytest

from api.ai_provider import settings as s


pytestmark = pytest.mark.usefixtures("isolated_app_dir")


class TestResumeTemplate:
    def test_default_empty(self):
        assert s.get_resume_template() == ""

    def test_round_trip(self):
        s.save_resume_template("hello")
        assert s.get_resume_template() == "hello"


class TestPageCap:
    def test_default(self):
        assert s.get_resume_page_cap() == 1

    def test_clamps_under_one(self):
        s.save_resume_page_cap(0)
        assert s.get_resume_page_cap() == 1

    def test_round_trip(self):
        s.save_resume_page_cap(2)
        assert s.get_resume_page_cap() == 2


class TestMaxAttempts:
    def test_round_trip(self):
        s.save_max_generation_attempts(5)
        assert s.get_max_generation_attempts() == 5

    def test_invalid_returns_default(self):
        s.save_max_generation_attempts(0)
        # 0 < 1 → falls back to default
        assert s.get_max_generation_attempts() == 3


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
        # set valid
        s.save_heatmap_day_thresholds([10, 5, 2, 1])  # sorted internally
        assert s.get_heatmap_day_thresholds() == [1, 2, 5, 10]

    def test_rejects_non_strict_ascending(self, monkeypatch):
        # _valid_thresholds requires strictly increasing
        # writing equal values should round-trip but fail validation on read
        s._set("heatmap_day_thresholds", [1, 1, 2, 3])
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


class TestModelConfig:
    def test_defaults_when_no_file(self):
        cfg = s._load_model_config()
        assert "basic" in cfg and "fast" in cfg and "powerful" in cfg

    def test_save_and_reload(self, monkeypatch):
        s.save_model_config("B1", "F1", "P1")
        # bust cache to force reread
        monkeypatch.setattr(s, "_model_config_cache", None)
        cfg = s._load_model_config()
        assert cfg == {"basic": "B1", "fast": "F1", "powerful": "P1"}


class TestResumeScoreThreshold:
    def test_round_trip(self):
        s.save_resume_score_threshold(8.0)
        assert s.get_resume_score_threshold() == pytest.approx(8.0)
