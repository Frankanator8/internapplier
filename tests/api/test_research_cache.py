from api.research_cache import lookup


class TestLookup:
    def test_returns_none_for_empty_inputs(self):
        assert lookup({}, "Acme") is None
        assert lookup({"Acme": {"result": {}}}, "") is None

    def test_exact_match_returns_result(self):
        cache = {"Acme": {"result": {"summary": "ok"}}}
        assert lookup(cache, "Acme") == {"summary": "ok"}

    def test_case_insensitive_match(self):
        cache = {"Acme": {"result": {"summary": "ok"}}}
        assert lookup(cache, "acme") == {"summary": "ok"}

    def test_returns_inline_shape(self):
        # Legacy shape: entry IS the result (has summary/core_values etc.)
        cache = {"Acme": {"summary": "ok", "core_values": [], "recent_projects": []}}
        assert lookup(cache, "Acme") == cache["Acme"]

    def test_returns_none_for_unknown_shape(self):
        cache = {"Acme": {"random": "data"}}
        assert lookup(cache, "Acme") is None

    def test_returns_none_when_missing(self):
        assert lookup({"Acme": {"result": {}}}, "Other") is None
