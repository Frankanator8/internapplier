from __future__ import annotations

import datetime
import logging
import threading

from .constants import TOKEN_USAGE_FILE
from .json_store import load_json, save_json

logger = logging.getLogger(__name__)

_TIERS = ("basic", "fast", "powerful")
_lock = threading.Lock()


def record_usage(tier: str, input_tokens: int, output_tokens: int) -> None:
    if tier not in _TIERS:
        tier = "fast"
    try:
        input_tokens = int(input_tokens or 0)
        output_tokens = int(output_tokens or 0)
    except (TypeError, ValueError):
        return
    if input_tokens <= 0 and output_tokens <= 0:
        return
    today = datetime.date.today().isoformat()
    with _lock:
        data = load_json(TOKEN_USAGE_FILE, {})
        if not isinstance(data, dict):
            data = {}
        day = data.setdefault(today, {})
        entry = day.setdefault(tier, {"input": 0, "output": 0})
        entry["input"] = int(entry.get("input", 0)) + input_tokens
        entry["output"] = int(entry.get("output", 0)) + output_tokens
        try:
            save_json(TOKEN_USAGE_FILE, data)
        except OSError:
            logger.exception("token_usage: failed to write %s", TOKEN_USAGE_FILE)


def load_usage() -> dict:
    with _lock:
        data = load_json(TOKEN_USAGE_FILE, {})
        return data if isinstance(data, dict) else {}


def usage_since(start: datetime.date) -> dict:
    data = load_usage()
    totals: dict[str, dict[str, int]] = {t: {"input": 0, "output": 0} for t in _TIERS}
    grand = {"input": 0, "output": 0}
    for day_key, tiers in data.items():
        try:
            day = datetime.date.fromisoformat(day_key)
        except ValueError:
            continue
        if day < start:
            continue
        if not isinstance(tiers, dict):
            continue
        for tier, counts in tiers.items():
            if not isinstance(counts, dict):
                continue
            inp = int(counts.get("input", 0) or 0)
            out = int(counts.get("output", 0) or 0)
            bucket = totals.setdefault(tier, {"input": 0, "output": 0})
            bucket["input"] += inp
            bucket["output"] += out
            grand["input"] += inp
            grand["output"] += out
    totals["__total__"] = grand
    return totals
