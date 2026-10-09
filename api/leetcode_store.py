"""Leetcode flashcard store: JSON persistence and SM-2 scheduling.

Cards are grouped into decks and reviewed with Again / Hard / Good / Easy.
New cards use 1-day then 3-day learning steps; graduated cards use SM-2.
"""
from __future__ import annotations

import html
import re
import uuid
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable

from .constants import LEETCODE_CARDS_FILE, LEETCODE_MEDIA_DIR
from .json_store import load_json, save_json

DEFAULT_DECK = "Default"
DEFAULT_EASE = 2.5
MIN_EASE = 1.3
LEARNING_STEPS = (1, 3)  # days
EASY_INTERVAL = 4
EASY_BONUS = 1.3
RATINGS = ("again", "hard", "good", "easy")

_CLOZE_RE = re.compile(r"\{\{c\d+::(.*?)(?:::(.*?))?\}\}", re.DOTALL)
_SOUND_RE = re.compile(r"\[sound:[^\]]+\]")
_TAG_RE = re.compile(r"<[^>]+>")
_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)

_cache: dict | None = None
_cache_mtime: float | None = None


def today() -> date:
    return date.today()


def media_dir() -> Path:
    path = LEETCODE_MEDIA_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def invalidate() -> None:
    global _cache, _cache_mtime
    _cache = None
    _cache_mtime = None


def _empty() -> dict:
    return {"cards": []}


def _normalize_card(raw: dict) -> dict:
    tags = raw.get("tags") or []
    if isinstance(tags, str):
        tags = [t for t in tags.split() if t]
    due = raw.get("due") or today().isoformat()
    return {
        "id": str(raw.get("id") or uuid.uuid4()),
        "deck": (str(raw.get("deck") or DEFAULT_DECK)).strip() or DEFAULT_DECK,
        "front": raw.get("front") or "",
        "back": raw.get("back") or "",
        "tags": [str(t) for t in tags if str(t).strip()],
        "ease": float(raw.get("ease") if raw.get("ease") is not None else DEFAULT_EASE),
        "interval_days": int(raw.get("interval_days") or 0),
        "repetitions": int(raw.get("repetitions") or 0),
        "due": str(due),
        "lapses": int(raw.get("lapses") or 0),
    }


def _new_card(
    front: str,
    back: str,
    deck: str = DEFAULT_DECK,
    tags: Iterable[str] | None = None,
) -> dict:
    return _normalize_card({
        "id": str(uuid.uuid4()),
        "deck": deck,
        "front": front,
        "back": back,
        "tags": list(tags or []),
        "ease": DEFAULT_EASE,
        "interval_days": 0,
        "repetitions": 0,
        "due": today().isoformat(),
        "lapses": 0,
    })


def load() -> dict:
    global _cache, _cache_mtime
    if not LEETCODE_CARDS_FILE.exists():
        invalidate()
        return _empty()
    mtime = LEETCODE_CARDS_FILE.stat().st_mtime
    if _cache is not None and _cache_mtime == mtime:
        return _cache
    raw = load_json(LEETCODE_CARDS_FILE, _empty())
    cards = raw.get("cards") if isinstance(raw, dict) else None
    if not isinstance(cards, list):
        cards = []
    data = {"cards": [_normalize_card(c) for c in cards if isinstance(c, dict)]}
    _cache = data
    _cache_mtime = mtime
    return _cache


def save(data: dict) -> None:
    global _cache, _cache_mtime
    payload = {
        "cards": [_normalize_card(c) for c in (data.get("cards") or []) if isinstance(c, dict)],
    }
    save_json(LEETCODE_CARDS_FILE, payload)
    _cache = payload
    _cache_mtime = LEETCODE_CARDS_FILE.stat().st_mtime


def list_cards(deck: str | None = None) -> list[dict]:
    cards = load()["cards"]
    if deck:
        cards = [c for c in cards if c["deck"] == deck]
    return list(cards)


def get_card(card_id: str) -> dict | None:
    for card in load()["cards"]:
        if card["id"] == card_id:
            return dict(card)
    return None


def list_decks() -> list[dict]:
    today_iso = today().isoformat()
    tallies: dict[str, dict] = {}
    for card in load()["cards"]:
        name = card["deck"]
        bucket = tallies.setdefault(name, {"name": name, "total": 0, "due": 0})
        bucket["total"] += 1
        if card["due"] <= today_iso:
            bucket["due"] += 1
    return sorted(tallies.values(), key=lambda d: d["name"].lower())


def due_cards(deck: str | None = None) -> list[dict]:
    today_iso = today().isoformat()
    out = []
    for card in load()["cards"]:
        if deck and card["deck"] != deck:
            continue
        if card["due"] <= today_iso:
            out.append(dict(card))
    return out


def add_card(
    front: str,
    back: str,
    deck: str = DEFAULT_DECK,
    tags: Iterable[str] | None = None,
) -> dict:
    data = load()
    card = _new_card(front, back, deck, tags)
    data["cards"].append(card)
    save(data)
    return dict(card)


def add_cards(items: list[dict]) -> list[dict]:
    data = load()
    created: list[dict] = []
    for item in items:
        front = item.get("front") or ""
        back = item.get("back") or ""
        if not str(front).strip() and not str(back).strip():
            continue
        card = _new_card(
            front,
            back,
            item.get("deck") or DEFAULT_DECK,
            item.get("tags") or [],
        )
        data["cards"].append(card)
        created.append(dict(card))
    if created:
        save(data)
    return created


def update_card(card_id: str, **fields) -> dict:
    data = load()
    for i, card in enumerate(data["cards"]):
        if card["id"] != card_id:
            continue
        updated = dict(card)
        for key in ("front", "back", "deck", "tags"):
            if key in fields:
                updated[key] = fields[key]
        data["cards"][i] = _normalize_card(updated)
        save(data)
        return dict(data["cards"][i])
    raise KeyError(card_id)


def delete_card(card_id: str) -> bool:
    return delete_cards([card_id]) == 1


def delete_cards(card_ids: Iterable[str]) -> int:
    wanted = set(card_ids)
    data = load()
    before = len(data["cards"])
    data["cards"] = [c for c in data["cards"] if c["id"] not in wanted]
    removed = before - len(data["cards"])
    if removed:
        save(data)
    return removed


def format_interval(days: int) -> str:
    if days <= 0:
        return "<1d"
    if days < 30:
        return f"{days}d"
    if days < 365:
        months = max(1, round(days / 30))
        return f"{months}mo"
    years = days / 365
    if years < 10:
        value = round(years, 1)
        if value == int(value):
            return f"{int(value)}y"
        return f"{value}y"
    return f"{round(years)}y"


def grade_card(card: dict, rating: str) -> dict:
    """Mutate ``card`` in place with SM-2 scheduling for ``rating``."""
    rating = (rating or "").strip().lower()
    if rating not in RATINGS:
        raise ValueError(f"Unknown rating: {rating}")

    ease = float(card.get("ease") if card.get("ease") is not None else DEFAULT_EASE)
    interval = int(card.get("interval_days") or 0)
    reps = int(card.get("repetitions") or 0)
    lapses = int(card.get("lapses") or 0)
    graduated = reps >= len(LEARNING_STEPS)

    if not graduated:
        if rating == "again":
            reps = 0
            interval = 0
            lapses += 1
        elif rating == "hard":
            interval = LEARNING_STEPS[min(reps, len(LEARNING_STEPS) - 1)]
        elif rating == "good":
            if reps < len(LEARNING_STEPS) - 1:
                interval = LEARNING_STEPS[reps]
                reps += 1
            else:
                interval = LEARNING_STEPS[-1]
                reps = len(LEARNING_STEPS)
        else:  # easy
            interval = EASY_INTERVAL
            reps = len(LEARNING_STEPS)
            ease += 0.15
    else:
        if rating == "again":
            reps = 0
            interval = 0
            lapses += 1
            ease = max(MIN_EASE, ease - 0.20)
        elif rating == "hard":
            interval = max(1, round(interval * 1.2))
            ease = max(MIN_EASE, ease - 0.15)
        elif rating == "good":
            interval = max(1, round(interval * ease))
            reps += 1
        else:  # easy
            interval = max(1, round(interval * ease * EASY_BONUS))
            ease += 0.15
            reps += 1

    card["ease"] = round(ease, 4)
    card["interval_days"] = int(interval)
    card["repetitions"] = int(reps)
    card["lapses"] = int(lapses)
    card["due"] = (today() + timedelta(days=int(interval))).isoformat()
    return card


def preview_intervals(card: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for rating in RATINGS:
        clone = deepcopy(card)
        grade_card(clone, rating)
        out[rating] = format_interval(int(clone["interval_days"]))
    return out


def grade(card_id: str, rating: str) -> dict:
    data = load()
    for i, card in enumerate(data["cards"]):
        if card["id"] != card_id:
            continue
        grade_card(card, rating)
        data["cards"][i] = card
        save(data)
        return dict(card)
    raise KeyError(card_id)


def plain_preview(text: str, max_len: int = 80) -> str:
    value = _SOUND_RE.sub("", text or "")
    value = _CLOZE_RE.sub(lambda m: m.group(1), value)
    value = _BR_RE.sub(" ", value)
    value = _TAG_RE.sub("", value)
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value).strip()
    if len(value) > max_len:
        return value[: max_len - 1] + "…"
    return value


def render_side(text: str, reveal_cloze: bool = False) -> str:
    """Normalize Anki-ish markup for display (cloze, sound tags)."""
    value = text or ""
    value = _SOUND_RE.sub("", value)

    def _cloze(match: re.Match) -> str:
        inner = match.group(1)
        hint = match.group(2)
        if reveal_cloze:
            return f"<span class='cloze-reveal'>{inner}</span>"
        label = html.escape(hint) if hint else "..."
        return f"<span class='cloze'>[{label}]</span>"

    return _CLOZE_RE.sub(_cloze, value)
