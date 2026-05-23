"""Lightweight, fully-local job-description keyword extractor.

Uses purpose-built skill-NER models (JobBERT family, Zhang et al.) to
tag concrete skill and knowledge spans inside a JD, so the resume
generator can be fed a compact `<jd_signals>` block of *differentiating*
phrases rather than the JD-centroid noise that an embedding-based
keyphrase extractor surfaces (soft-skill bigrams, boilerplate, etc.).

Two small DistilBERT-sized models are used:
  - knowledge: tools, technologies, domains  (e.g. "Kubernetes", "FX trading")
  - skill:     methodologies, actions        (e.g. "designing APIs", "A/B testing")

Models are loaded lazily on first use and cached for the process
lifetime. Per-JD results are LRU-cached.
"""
from __future__ import annotations

import logging
import re
from functools import lru_cache
from typing import Any

logger = logging.getLogger(__name__)

_KNOWLEDGE_MODEL = "jjzha/jobbert_knowledge_extraction"
_SKILL_MODEL = "jjzha/jobbert_skill_extraction"

_pipelines: dict[str, Any] = {}

_SECTION_HEAD_RE = re.compile(
    r"(?im)^\s*(requirements?|responsibilities|qualifications|"
    r"what you'?ll do|what we'?re looking for|must have|nice to have|"
    r"about (?:the|this) role)\s*[:\-]?\s*$"
)


def _get_pipeline(model_name: str):
    pipe = _pipelines.get(model_name)
    if pipe is None:
        from transformers import pipeline  # type: ignore
        logger.info("keyword_extractor — loading NER model %s", model_name)
        pipe = pipeline(
            "ner",
            model=model_name,
            tokenizer=model_name,
            aggregation_strategy="simple",
        )
        _pipelines[model_name] = pipe
    return pipe


def _short_excerpts(jd: str, max_excerpts: int = 4, span_chars: int = 240) -> list[str]:
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


def _chunk(text: str, max_chars: int = 1500) -> list[str]:
    """Naive char-based chunking so we stay under the model's 512-token window.
    JDs are short enough that paragraph-aligned splitting is fine."""
    if len(text) <= max_chars:
        return [text]
    parts: list[str] = []
    buf: list[str] = []
    size = 0
    for para in text.split("\n\n"):
        if size + len(para) + 2 > max_chars and buf:
            parts.append("\n\n".join(buf))
            buf, size = [], 0
        buf.append(para)
        size += len(para) + 2
    if buf:
        parts.append("\n\n".join(buf))
    return parts


def _run_ner(model_name: str, jd: str) -> list[tuple[str, float]]:
    """Return list of (phrase, score) spans tagged by the given model.

    Phrases are normalized (lowercased, whitespace-collapsed, deduped) and
    sorted by descending score with a max length cap to drop noisy spans.
    """
    pipe = _get_pipeline(model_name)
    best: dict[str, float] = {}
    for chunk in _chunk(jd):
        try:
            spans = pipe(chunk) or []
        except Exception:
            logger.exception("keyword_extractor — NER pipeline failed for %s", model_name)
            spans = []
        for s in spans:
            raw = (s.get("word") or "").strip()
            # HF subword artifacts: strip leading ## and stray punctuation
            phrase = re.sub(r"\s+", " ", raw.replace("##", "")).strip(" .,;:()[]\"'")
            if not phrase or len(phrase) < 2 or len(phrase.split()) > 6:
                continue
            key = phrase.lower()
            score = float(s.get("score", 0.0))
            if score > best.get(key, 0.0):
                best[key] = score
    return sorted(best.items(), key=lambda kv: kv[1], reverse=True)


@lru_cache(maxsize=32)
def _extract_cached(jd: str, top_n: int) -> tuple:
    knowledge = _run_ner(_KNOWLEDGE_MODEL, jd)
    skills = _run_ner(_SKILL_MODEL, jd)
    # Cap per-category, knowledge slightly favored since it's what
    # most differentiates a candidate ("Kubernetes" > "deploying services").
    k_cap = max(1, int(top_n * 0.6))
    s_cap = max(1, top_n - k_cap)
    out = (
        tuple(("knowledge", p, s) for p, s in knowledge[:k_cap])
        + tuple(("skill", p, s) for p, s in skills[:s_cap])
    )
    return out


def extract_jd_keywords(jd: str, top_n: int = 30) -> dict:
    """Return categorized JD spans + a few verbatim excerpts.

    Shape:
        {
          "keywords": [{"phrase": str, "score": float, "category": str}, ...],
          "excerpts": [str, ...]
        }
    """
    jd = (jd or "").strip()
    if not jd:
        return {"keywords": [], "excerpts": []}

    rows = _extract_cached(jd, top_n)
    keywords = [
        {"phrase": p, "score": round(s, 4), "category": cat}
        for cat, p, s in rows
    ]
    result = {"keywords": keywords, "excerpts": _short_excerpts(jd)}
    logger.info(
        "extract_jd_keywords — jd_chars=%d top_n=%d extracted=%d excerpts=%d; keywords=[%s]",
        len(jd), top_n, len(result["keywords"]), len(result["excerpts"]),
        ", ".join(f"{k['category']}:{k['phrase']!r}@{k['score']:.3f}" for k in result["keywords"]),
    )
    return result


def format_jd_signals(signals: dict) -> str:
    """Render `extract_jd_keywords()` output as a compact text block for
    inclusion in an LLM user message."""
    lines: list[str] = []
    kws = signals.get("keywords") or []
    by_cat: dict[str, list[str]] = {}
    for kw in kws:
        if isinstance(kw, dict):
            phrase = kw.get("phrase", "")
            cat = kw.get("category", "keyword")
        else:
            phrase = str(kw)
            cat = "keyword"
        if phrase:
            by_cat.setdefault(cat, []).append(phrase)

    label_order = ["knowledge", "skill", "keyword"]
    label_text = {
        "knowledge": "tools / technologies / domains (highest-signal — prefer these):",
        "skill": "methodologies / actions:",
        "keyword": "keywords (ranked, most-relevant first):",
    }
    for cat in label_order:
        items = by_cat.get(cat)
        if not items:
            continue
        if lines:
            lines.append("")
        lines.append(label_text.get(cat, f"{cat}:"))
        for phrase in items:
            lines.append(f"  - {phrase}")

    excerpts = signals.get("excerpts") or []
    if excerpts:
        if lines:
            lines.append("")
        lines.append("verbatim excerpts (tone/seniority cues — NOT the full JD):")
        for ex in excerpts:
            cleaned = " ".join((ex or "").split())
            if cleaned:
                lines.append(f"  > {cleaned}")
    return "\n".join(lines) if lines else "(no signals extracted)"
