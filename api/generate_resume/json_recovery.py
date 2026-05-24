"""Recover JSON objects from model output that may contain prose.

The model occasionally emits a JSON object surrounded by a sentence of
explanation. ``parse_lenient_json`` strips fences, parses, and falls
back to balanced-brace extraction when the strict parse fails.
"""
from __future__ import annotations

import json
import logging
import re

from ..ai_provider import strip_code_fence

logger = logging.getLogger(__name__)


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip()).casefold()


def extract_json_object(text: str) -> str | None:
    """Return the first balanced ``{...}`` substring, or ``None`` if absent.

    Tolerates prose before/after the JSON. Respects string literals and
    backslash escapes so braces inside strings don't throw off the depth.
    """
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def parse_lenient_json(raw: str, *, log_label: str) -> dict:
    """Strip code fences, parse JSON, fall back to balanced-brace extraction.

    Raises ``ValueError`` with a user-facing message if recovery fails.
    """
    cleaned = strip_code_fence(raw, lang_hints=("json",))
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        extracted = extract_json_object(cleaned)
        if extracted is None:
            logger.error("%s — JSON parse failed, raw=%r", log_label, cleaned[:500])
            raise ValueError("AI returned unexpected format — please try again.")
        try:
            obj = json.loads(extracted)
        except json.JSONDecodeError:
            logger.error(
                "%s — balanced extract still unparseable, raw=%r",
                log_label, cleaned[:500],
            )
            raise ValueError("AI returned unexpected format — please try again.")
        logger.info(
            "%s — recovered JSON via balanced extract "
            "(%d chars of surrounding prose discarded)",
            log_label, len(cleaned) - len(extracted),
        )
        return obj
