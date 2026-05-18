from __future__ import annotations

import json
import logging
import time

import requests

from app.ai_provider import OpenRouterProvider, load_prompt

logger = logging.getLogger(__name__)


AI_WEIGHT = 0.7
RECENCY_WEIGHT = 0.3


def combine_score(ai_avg_0_10: float, recency_0_1: float) -> float:
    return AI_WEIGHT * (ai_avg_0_10 / 10.0) + RECENCY_WEIGHT * recency_0_1


def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
        if raw.endswith("```"):
            raw = raw[:-3].strip()
    return raw


def _format_research(research: dict) -> str:
    summary = (research or {}).get("summary", "").strip()
    values = (research or {}).get("core_values") or []
    projects = (research or {}).get("recent_projects") or []
    out = []
    if summary:
        out.append(f"Company summary: {summary}")
    if values:
        out.append("Core values: " + "; ".join(str(v) for v in values))
    if projects:
        out.append("Recent projects: " + "; ".join(str(p) for p in projects))
    return "\n".join(out) if out else "(no company research available)"


def _format_numbered_entries(entries: list[tuple[str, str, list[str]]]) -> str:
    blocks = []
    for i, (name, when, bullets) in enumerate(entries, start=1):
        header = f"{i}. {name}"
        if when:
            header += f"  ({when})"
        bullet_block = "\n".join(f"  - {b}" for b in bullets) if bullets else "  (no bullets)"
        blocks.append(f"{header}\n{bullet_block}")
    return "\n\n".join(blocks)


def _post(provider: OpenRouterProvider, system_prompt: str, user_message: str, timeout: int = 60) -> str:
    if not provider.api_key:
        raise ValueError(
            "No API key found. Set the OPENROUTER_API_KEY environment variable."
        )
    t0 = time.perf_counter()
    response = requests.post(
        provider.BASE_URL,
        headers={
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": provider.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        },
        timeout=timeout,
    )
    elapsed = time.perf_counter() - t0
    logger.info("scoring POST — HTTP %s in %.2fs", response.status_code, elapsed)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def score_entries_ai(
    provider: OpenRouterProvider,
    entries: list[tuple[str, str, list[str]]],
    job_description: str,
    company_research: dict,
    *,
    include_relevancy: bool,
) -> list[dict]:
    """Returns a list of dicts (same length/order as entries):
       include_relevancy=True  -> {impact, prestige, relevancy}
       include_relevancy=False -> {impact, prestige}
    """
    if not entries:
        return []

    system_prompt_name = "score_entries.txt" if include_relevancy else "score_leadership.txt"
    system_prompt = load_prompt(system_prompt_name)

    user_message = (
        f"Job Description:\n{job_description}\n\n"
        f"Company Context:\n{_format_research(company_research)}\n\n"
        f"Entries:\n{_format_numbered_entries(entries)}\n\n"
        f"Return a JSON array of exactly {len(entries)} objects, in input order."
    )

    raw = _strip_fences(_post(provider, system_prompt, user_message))
    try:
        items = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("score_entries_ai — JSON parse failed: %r", raw[:500])
        raise ValueError("AI returned unexpected format for scoring — please try again.")

    if not isinstance(items, list) or len(items) != len(entries):
        raise ValueError(
            f"AI returned {type(items).__name__} of length "
            f"{len(items) if isinstance(items, list) else 'n/a'}, expected list of {len(entries)}."
        )

    out: list[dict] = []
    for it in items:
        if not isinstance(it, dict):
            raise ValueError("AI scoring item was not an object.")
        d = {
            "impact": _clamp_int(it.get("impact")),
            "prestige": _clamp_int(it.get("prestige")),
        }
        if include_relevancy:
            d["relevancy"] = _clamp_int(it.get("relevancy"))
        out.append(d)
    return out


def _clamp_int(v) -> int:
    try:
        n = int(round(float(v)))
    except (TypeError, ValueError):
        return 0
    return max(0, min(10, n))


def select_courses_ai(
    provider: OpenRouterProvider,
    courses: list[str],
    job_description: str,
    company_research: dict,
    top_n: int,
) -> list[str]:
    if not courses:
        return []
    if len(courses) <= top_n:
        return list(courses)

    system_prompt = load_prompt("select_courses.txt")
    numbered = "\n".join(f"{i + 1}. {c}" for i, c in enumerate(courses))
    user_message = (
        f"Job Description:\n{job_description}\n\n"
        f"Company Context:\n{_format_research(company_research)}\n\n"
        f"Completed Courses:\n{numbered}\n\n"
        f"Select the {top_n} most relevant courses. Return a JSON array of exactly "
        f"{top_n} course-name strings drawn verbatim from the list above."
    )
    raw = _strip_fences(_post(provider, system_prompt, user_message))
    try:
        items = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("select_courses_ai — JSON parse failed: %r", raw[:500])
        raise ValueError("AI returned unexpected format for course selection.")

    if not isinstance(items, list) or not all(isinstance(s, str) for s in items):
        raise ValueError("AI returned unexpected format for course selection.")

    valid = {c.strip().lower(): c for c in courses}
    selected: list[str] = []
    seen: set[str] = set()
    for s in items:
        key = s.strip().lower()
        if key in valid and key not in seen:
            selected.append(valid[key])
            seen.add(key)
        if len(selected) >= top_n:
            break
    return selected
