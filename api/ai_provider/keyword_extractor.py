"""Lightweight, fully-local job-description keyword extractor.

Uses KeyBERT (sentence-transformers backbone) to surface the most
JD-relevant phrases so the resume generator can be fed a compact
`<jd_signals>` block instead of the full job description. The grader
still receives the full JD elsewhere.

The KeyBERT model is loaded lazily on first use and cached for the
process lifetime. Per-JD results are LRU-cached.
"""
from __future__ import annotations

import logging
import re
from functools import lru_cache
from typing import Any

logger = logging.getLogger(__name__)

_KEYBERT_MODEL_NAME = "all-MiniLM-L6-v2"
_keybert_instance: Any = None

_SECTION_HEAD_RE = re.compile(
    r"(?im)^\s*(requirements?|responsibilities|qualifications|"
    r"what you'?ll do|what we'?re looking for|must have|nice to have|"
    r"about (?:the|this) role)\s*[:\-]?\s*$"
)


def _get_keybert():
    global _keybert_instance
    if _keybert_instance is None:
        from keybert import KeyBERT
        logger.info("keyword_extractor — loading KeyBERT model %s", _KEYBERT_MODEL_NAME)
        _keybert_instance = KeyBERT(model=_KEYBERT_MODEL_NAME)
    return _keybert_instance


def _short_excerpts(jd: str, max_excerpts: int = 4, span_chars: int = 240) -> list[str]:
    """Pull a few short verbatim spans from the JD so the generator
    retains tone/seniority cues without seeing the whole thing.

    Always include the JD's first paragraph; then any section heading
    we recognize plus its following 1-2 sentences.
    """
    if not jd:
        return []
    out: list[str] = []
    first_para = jd.strip().split("\n\n", 1)[0].strip()
    if first_para:
        out.append(first_para[:span_chars])

    for m in _SECTION_HEAD_RE.finditer(jd):
        start = m.start()
        snippet = jd[start:start + span_chars].strip()
        if snippet:
            out.append(snippet)
        if len(out) >= max_excerpts:
            break
    return out[:max_excerpts]


@lru_cache(maxsize=32)
def _extract_cached(jd: str, top_n: int) -> tuple:
    kb = _get_keybert()
    try:
        raw = kb.extract_keywords(
            jd,
            keyphrase_ngram_range=(1, 3),
            stop_words="english",
            use_mmr=True,
            diversity=0.5,
            top_n=top_n,
        )
    except Exception:
        logger.exception("keyword_extractor — KeyBERT.extract_keywords failed; returning empty list")
        raw = []
    # raw: list of (phrase, score) tuples — make it hashable for the cache layer
    return tuple((str(p), float(s)) for p, s in raw)


def extract_jd_keywords(jd: str, top_n: int = 30) -> dict:
    """Return ranked KeyBERT phrases + a few verbatim excerpts from the JD.

    Shape:
        {
          "keywords": [{"phrase": str, "score": float}, ...],
          "excerpts": [str, ...]
        }
    """
    jd = (jd or "").strip()
    if not jd:
        return {"keywords": [], "excerpts": []}

    keywords_raw = _extract_cached(jd, top_n)
    result = {
        "keywords": [{"phrase": p, "score": round(s, 4)} for p, s in keywords_raw],
        "excerpts": _short_excerpts(jd),
    }
    logger.info(
        "extract_jd_keywords — jd_chars=%d top_n=%d extracted=%d excerpts=%d; keywords=[%s]",
        len(jd), top_n, len(result["keywords"]), len(result["excerpts"]),
        ", ".join(f"{k['phrase']!r}@{k['score']:.3f}" for k in result["keywords"]),
    )
    return result


def format_jd_signals(signals: dict) -> str:
    """Render `extract_jd_keywords()` output as a compact text block for
    inclusion in an LLM user message."""
    lines: list[str] = []
    kws = signals.get("keywords") or []
    if kws:
        lines.append("keywords (ranked, most-relevant first):")
        for kw in kws:
            phrase = kw.get("phrase", "") if isinstance(kw, dict) else str(kw)
            if phrase:
                lines.append(f"  - {phrase}")
    excerpts = signals.get("excerpts") or []
    if excerpts:
        lines.append("")
        lines.append("verbatim excerpts (tone/seniority cues — NOT the full JD):")
        for ex in excerpts:
            cleaned = " ".join((ex or "").split())
            if cleaned:
                lines.append(f"  > {cleaned}")
    return "\n".join(lines) if lines else "(no signals extracted)"
