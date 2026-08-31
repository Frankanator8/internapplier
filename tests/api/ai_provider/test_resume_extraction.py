"""Tests for OpenRouterProvider.extract_resume — the resume-PDF parse call."""
from __future__ import annotations

import json

import pytest

from api.ai_provider.prompts import load_prompt, load_schema
from api.ai_provider.provider import OpenRouterProvider

pytestmark = pytest.mark.usefixtures("isolated_app_dir")


@pytest.fixture
def provider(fake_api_key, isolated_app_dir):
    return OpenRouterProvider()


def _resp(body: dict, status: int = 200):
    class _R:
        status_code = status
        text = json.dumps(body)

        def raise_for_status(self):
            if status >= 400:
                import requests
                raise requests.HTTPError(f"HTTP {status}")

        @staticmethod
        def json():
            return body

    return _R()


def _success_body(content: str, usage: dict | None = None) -> dict:
    body: dict = {"choices": [{"message": {"content": content}}]}
    if usage is not None:
        body["usage"] = usage
    return body


_MINIMAL = {
    "general_info": {"first_name": "Ada"},
    "experience": [], "projects": [], "education": [],
    "awards": [], "skills": [], "hobbies": [],
}


class TestExtractResume:
    def test_happy_path_returns_the_parsed_object(self, provider, mocker):
        mocker.patch("api.ai_provider.http_client.requests.post",
                     return_value=_resp(_success_body(json.dumps(_MINIMAL))))
        assert provider.extract_resume("Ada Lovelace\nEngineer") == _MINIMAL

    def test_strips_markdown_fence(self, provider, mocker):
        wrapped = "```json\n" + json.dumps(_MINIMAL) + "\n```"
        mocker.patch("api.ai_provider.http_client.requests.post",
                     return_value=_resp(_success_body(wrapped)))
        assert provider.extract_resume("text")["general_info"]["first_name"] == "Ada"

    def test_recovers_json_wrapped_in_prose(self, provider, mocker):
        """Long structured outputs are exactly where models add commentary."""
        chatty = "Here is the resume:\n" + json.dumps(_MINIMAL) + "\nHope that helps!"
        mocker.patch("api.ai_provider.http_client.requests.post",
                     return_value=_resp(_success_body(chatty)))
        assert provider.extract_resume("text") == _MINIMAL

    def test_malformed_json_raises_value_error(self, provider, mocker):
        mocker.patch("api.ai_provider.http_client.requests.post",
                     return_value=_resp(_success_body("not json at all")))
        with pytest.raises(ValueError, match="unexpected format"):
            provider.extract_resume("text")

    def test_non_object_json_raises_value_error(self, provider, mocker):
        """A top-level array would sail through json.loads and blow up later."""
        mocker.patch("api.ai_provider.http_client.requests.post",
                     return_value=_resp(_success_body('[{"school": "MIT"}]')))
        with pytest.raises(ValueError, match="unexpected format"):
            provider.extract_resume("text")

    def test_missing_api_key_raises_before_http(self, mocker, monkeypatch):
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        post = mocker.patch("api.ai_provider.http_client.requests.post")
        with pytest.raises(ValueError, match="No API key"):
            OpenRouterProvider().extract_resume("text")
        post.assert_not_called()

    def test_uses_the_fast_tier_and_strict_schema(self, provider, mocker):
        post = mocker.patch("api.ai_provider.http_client.requests.post",
                            return_value=_resp(_success_body(json.dumps(_MINIMAL))))
        provider.extract_resume("text")
        payload = post.call_args.kwargs["json"]
        from api.ai_provider.settings import _load_model_config
        assert payload["model"] == _load_model_config()["fast"]
        schema = payload["response_format"]["json_schema"]
        assert schema["strict"] is True
        assert schema["name"] == "import_resume_output"

    def test_records_usage_against_the_fast_tier(self, provider, mocker):
        rec = mocker.patch("api.ai_provider.http_client.record_usage")
        mocker.patch(
            "api.ai_provider.http_client.requests.post",
            return_value=_resp(_success_body(
                json.dumps(_MINIMAL),
                usage={"prompt_tokens": 10, "completion_tokens": 20},
            )),
        )
        provider.extract_resume("text")
        rec.assert_called_once_with("fast", 10, 20)


class TestImportResumeSchema:
    def test_schema_is_strict_mode_compatible(self):
        """OpenRouter strict mode 400s unless every object node is closed and
        lists all its properties as required — a runtime-only failure."""
        schema = load_schema("import_resume.schema.json")

        def walk(node, path="root"):
            if not isinstance(node, dict):
                return
            if node.get("type") == "object":
                assert node.get("additionalProperties") is False, path
                assert set(node.get("required") or []) == set(node.get("properties") or {}), path
            for key, child in (node.get("properties") or {}).items():
                walk(child, f"{path}.{key}")
            if "items" in node:
                walk(node["items"], f"{path}[]")

        walk(schema)

    def test_prompt_inlines_the_schema(self):
        prompt = load_prompt("import_resume.txt")
        assert "import_resume_output" in prompt
        assert "{{schema:" not in prompt

    def test_schema_omits_the_constrained_combo_fields(self):
        """GeneralInfoPage combos are enums the model must never guess at —
        they cover work authorization and EEO answers."""
        from api.constants import COMBO_FIELDS
        schema = load_schema("import_resume.schema.json")
        gi = schema["properties"]["general_info"]["properties"]
        assert not set(COMBO_FIELDS) & set(gi)
