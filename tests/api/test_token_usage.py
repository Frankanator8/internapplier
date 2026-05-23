import datetime

import pytest

from api import token_usage


pytestmark = pytest.mark.usefixtures("isolated_app_dir")


# NOTE: api.generate_resume.step_timing monkey-patches record_usage at
# import time. The patched version still calls the original, so behavior
# is preserved — but we test the raw write logic via _write/_read where
# appropriate.


class TestRecordUsage:
    def test_records_for_known_tier(self):
        token_usage.record_usage("fast", 10, 20)
        data = token_usage.load_usage()
        today = datetime.date.today().isoformat()
        assert data[today]["fast"] == {"input": 10, "output": 20}

    def test_unknown_tier_coerced_to_fast(self):
        token_usage.record_usage("banana", 5, 5)
        today = datetime.date.today().isoformat()
        assert "fast" in token_usage.load_usage()[today]

    def test_zero_tokens_skipped(self):
        token_usage.record_usage("fast", 0, 0)
        assert token_usage.load_usage() == {}

    def test_accumulates_over_multiple_calls(self):
        token_usage.record_usage("fast", 10, 5)
        token_usage.record_usage("fast", 3, 2)
        today = datetime.date.today().isoformat()
        assert token_usage.load_usage()[today]["fast"] == {"input": 13, "output": 7}

    def test_non_numeric_tokens_no_op(self):
        token_usage.record_usage("fast", "x", "y")  # type: ignore[arg-type]
        assert token_usage.load_usage() == {}


class TestUsageSince:
    def test_aggregates_only_from_start_date(self):
        # Write directly to bypass "today" logic
        data = {
            "2025-01-01": {"fast": {"input": 1, "output": 2}},
            "2026-05-20": {"fast": {"input": 10, "output": 20}},
        }
        token_usage._write(data)
        totals = token_usage.usage_since(datetime.date(2026, 1, 1))
        assert totals["fast"] == {"input": 10, "output": 20}
        assert totals["__total__"] == {"input": 10, "output": 20}

    def test_skips_invalid_date_keys(self):
        token_usage._write({
            "not-a-date": {"fast": {"input": 5, "output": 5}},
            "2026-05-20": {"basic": {"input": 1, "output": 1}},
        })
        totals = token_usage.usage_since(datetime.date(2026, 1, 1))
        assert totals["basic"] == {"input": 1, "output": 1}
        assert totals["fast"] == {"input": 0, "output": 0}
