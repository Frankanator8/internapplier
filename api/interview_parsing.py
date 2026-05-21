from __future__ import annotations

import json

from .ai_provider import strip_code_fence


def parse_grade_payload(buf: str) -> tuple[float | None, str]:
    """Parse a grade_interview JSON payload from a streamed buffer.

    Returns (score, feedback). Raises ValueError if the payload is missing
    required keys or the score is non-numeric. Strips markdown fences first
    since the fast-tier model sometimes wraps JSON despite the prompt.
    """
    cleaned = strip_code_fence(buf, lang_hints=("json",))
    obj = json.loads(cleaned)
    if not isinstance(obj, dict) or "score" not in obj or "feedback" not in obj:
        raise ValueError("missing required keys")
    try:
        score = float(obj["score"])
    except (TypeError, ValueError) as exc:
        raise ValueError("score not numeric") from exc
    feedback = obj.get("feedback") or ""
    if not isinstance(feedback, str):
        feedback = str(feedback)
    return score, feedback


def extract_partial_feedback(buf: str) -> str:
    """Pull the `feedback` string out of a possibly-incomplete JSON buffer.

    Lets us stream the body text as it arrives instead of waiting for the
    whole JSON object to close.
    """
    idx = buf.find('"feedback"')
    if idx < 0:
        return ""
    colon = buf.find(':', idx)
    if colon < 0:
        return ""
    start = buf.find('"', colon + 1)
    if start < 0:
        return ""
    out: list[str] = []
    i = start + 1
    n = len(buf)
    while i < n:
        c = buf[i]
        if c == '\\' and i + 1 < n:
            nxt = buf[i + 1]
            out.append(
                {'n': '\n', 't': '\t', '"': '"', '\\': '\\', '/': '/'}.get(nxt, nxt)
            )
            i += 2
        elif c == '"':
            break
        else:
            out.append(c)
            i += 1
    return ''.join(out)
