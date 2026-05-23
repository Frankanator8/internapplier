"""Shared fixtures for the api/ test suite.

The patterns here are:

* ``isolated_app_dir`` — points every module that holds a path constant
  to ``constants.APP_DIR`` at a tmp directory, and resets the in-process
  caches in ``data_store`` and ``ai_provider.settings``.

* ``fake_api_key`` — sets ``OPENROUTER_API_KEY`` so the provider does not
  raise during construction.

* ``sse_response`` + ``mock_openrouter`` — build a fake ``requests.post``
  context manager whose ``iter_lines`` yields scripted Server-Sent Events,
  and capture the JSON body submitted.

Importing this module pulls in ``api`` modules, which in turn may import
``api.generate_resume.step_timing`` which writes to a file in CWD on
import. The autouse fixture below redirects that timing file at session
start so we never pollute the project root.
"""
from __future__ import annotations

import json
import pathlib
import sys
from typing import Any

import pytest


# ---- Path & module setup ------------------------------------------------

# The repo root is the parent of `tests/`. Make sure it's on sys.path so
# `import api` works from a fresh pytest run.
_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


@pytest.fixture(autouse=True, scope="session")
def _redirect_step_timing_file(tmp_path_factory):
    """Redirect step_timing._TIMING_FILE before any test touches it."""
    from api.generate_resume import step_timing

    tmp = tmp_path_factory.mktemp("step_timing")
    step_timing._TIMING_FILE = tmp / "step_timings.txt"
    yield


# ---- isolated app dir ---------------------------------------------------

_PATH_BINDINGS = [
    # (module dotted name, attribute name, relative path under APP_DIR)
    ("api.constants", "APP_DIR", ""),
    ("api.constants", "RESUME_DATA_FILE", "resume.json"),
    ("api.constants", "INTERVIEW_TEMPLATE_FILE", "interview_template.json"),
    ("api.constants", "INTERVIEW_FEEDBACK_FILE", "interview_feedback.json"),
    ("api.constants", "MODELS_FILE", "models.txt"),
    ("api.constants", "SETTINGS_FILE", "settings.json"),
    ("api.constants", "TOKEN_USAGE_FILE", "token_usage.json"),
    ("api.constants", "APP_PROMPTS_DIR", "prompts"),
    ("api.data_store", "APP_DIR", ""),
    ("api.data_store", "RESUME_DATA_FILE", "resume.json"),
    ("api.data_store", "INTERVIEW_TEMPLATE_FILE", "interview_template.json"),
    ("api.data_store", "INTERVIEW_FEEDBACK_FILE", "interview_feedback.json"),
    ("api.token_usage", "APP_DIR", ""),
    ("api.token_usage", "TOKEN_USAGE_FILE", "token_usage.json"),
    ("api.ai_provider.settings", "APP_DIR", ""),
    ("api.ai_provider.settings", "MODELS_FILE", "models.txt"),
    ("api.ai_provider.settings", "SETTINGS_FILE", "settings.json"),
    ("api.ai_provider.prompts", "APP_PROMPTS_DIR", "prompts"),
]


@pytest.fixture
def isolated_app_dir(tmp_path, monkeypatch):
    """Point every cached APP_DIR-derived constant at a tmp directory.

    Also clears the module-level caches in ``data_store`` and
    ``ai_provider.settings`` so reads after the fixture sees the empty
    fresh state.
    """
    import importlib

    app_dir = tmp_path / "app"
    app_dir.mkdir()

    for module_name, attr, rel in _PATH_BINDINGS:
        module = importlib.import_module(module_name)
        target = app_dir if rel == "" else app_dir / rel
        monkeypatch.setattr(module, attr, target)

    # Reset module caches.
    import api.data_store as data_store
    import api.ai_provider.settings as ap_settings

    monkeypatch.setattr(data_store, "_cache", None)
    monkeypatch.setattr(data_store, "_cache_mtime", None)
    monkeypatch.setattr(ap_settings, "_settings_cache", None)
    monkeypatch.setattr(ap_settings, "_model_config_cache", None)

    # Seed prompt files into the isolated dir from the project's PROMPTS_DIR.
    from api.ai_provider.prompts import _seed_prompts
    _seed_prompts()

    yield app_dir


# ---- API key ------------------------------------------------------------

@pytest.fixture
def fake_api_key(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-abcdef")
    yield "test-key-abcdef"


# ---- SSE response builder ----------------------------------------------

class _FakeResponse:
    """Stand-in for the streaming ``requests.Response`` used by provider."""

    def __init__(self, lines: list[str], status_code: int = 200):
        self._lines = lines
        self.status_code = status_code
        self.encoding = "utf-8"
        self.text = "\n".join(lines)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def iter_lines(self, decode_unicode=True):
        for ln in self._lines:
            yield ln

    def json(self):
        return json.loads("\n".join(self._lines))


def _sse(events: list[dict]) -> list[str]:
    """Render a list of event payloads as SSE ``data: ...`` lines."""
    out: list[str] = []
    for ev in events:
        out.append(f"data: {json.dumps(ev)}")
    out.append("data: [DONE]")
    return out


def _delta_event(content: str | None = None, tool_calls: list[dict] | None = None,
                 finish_reason: str | None = None, usage: dict | None = None,
                 index: int = 0) -> dict:
    delta: dict[str, Any] = {}
    if content is not None:
        delta["content"] = content
    if tool_calls is not None:
        delta["tool_calls"] = tool_calls
    ev: dict[str, Any] = {
        "choices": [{"index": index, "delta": delta}]
    }
    if finish_reason:
        ev["choices"][0]["finish_reason"] = finish_reason
    if usage is not None:
        ev["usage"] = usage
    return ev


@pytest.fixture
def sse_factory():
    """Return helper builders for SSE events and lines."""
    class _Builder:
        delta = staticmethod(_delta_event)
        lines = staticmethod(_sse)
    return _Builder


@pytest.fixture
def mock_openrouter(mocker, fake_api_key):
    """Patch ``requests.post`` inside the provider module.

    The returned object behaves like a mock: ``calls`` is a list of
    ``(args, kwargs)`` tuples, and ``responses`` is a list of scripted
    ``_FakeResponse`` objects consumed in order. Test code populates
    ``responses`` before invoking the provider.
    """
    state: dict[str, Any] = {"calls": [], "responses": []}

    def _fake_post(url, **kwargs):
        state["calls"].append({"url": url, **kwargs})
        if not state["responses"]:
            return _FakeResponse(["data: [DONE]"])
        return state["responses"].pop(0)

    mocker.patch("api.ai_provider.provider.requests.post", side_effect=_fake_post)

    class _Handle:
        FakeResponse = _FakeResponse

        @staticmethod
        def queue_stream(events: list[dict], status_code: int = 200):
            state["responses"].append(_FakeResponse(_sse(events), status_code=status_code))

        @staticmethod
        def queue_raw(lines: list[str], status_code: int = 200):
            state["responses"].append(_FakeResponse(lines, status_code=status_code))

        @staticmethod
        def queue_json(body: dict, status_code: int = 200):
            state["responses"].append(_FakeResponse([json.dumps(body)], status_code=status_code))

        @staticmethod
        def calls():
            return state["calls"]

        @staticmethod
        def last_payload():
            return state["calls"][-1]["json"]

    return _Handle


# ---- sample data --------------------------------------------------------

@pytest.fixture
def sample_profile():
    return {
        "general_info": {
            "first_name": "Ada", "last_name": "Lovelace",
            "email": "ada@example.com", "phone": "555-0100",
            "city": "London", "country": "UK",
        },
        "experience": [
            {"company": "Analytical Engines", "role": "Programmer",
             "start": "1842", "end": "1843",
             "bullets": ["Wrote first algorithm", "Translated Menabrea's notes"]},
        ],
        "projects": [
            {"name": "Bernoulli computation", "start": "1842", "end": "1843",
             "bullets": ["Designed punch-card program"]},
        ],
        "education": [
            {"school": "Self-taught", "degree": "", "start": "", "end": ""},
        ],
        "awards": [],
        "skills": ["math", "programming"],
        "hobbies": [],
    }


@pytest.fixture
def sample_resume_json(sample_profile):
    return {
        "header": {"name": "Ada Lovelace", "email": "ada@example.com"},
        "sections": [
            {"kind": "experience", "items": [
                {"role": "Programmer", "company": "Analytical Engines",
                 "start": "1842", "end": "1843",
                 "bullets": ["Wrote first algorithm"]},
            ]},
            {"kind": "skills", "groups": [
                {"label": "Languages", "items": ["punch-card"]},
            ]},
        ],
    }


@pytest.fixture
def sample_jd():
    return (
        "We are looking for a Software Engineer.\n\n"
        "Requirements:\n"
        "- Python expertise\n"
        "- Strong CS fundamentals\n"
    )
