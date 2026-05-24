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
