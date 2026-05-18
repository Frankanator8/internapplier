from __future__ import annotations

import datetime as _dt

_MONTHS = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


def parse_date(s: str | None) -> _dt.date | None:
    if s is None:
        return None
    raw = s.strip()
    if not raw:
        return None
    low = raw.lower()
    if low in ("present", "current", "now", "ongoing"):
        return _dt.date.today()

    parts = raw.replace(",", " ").split()
    month = None
    year = None
    for p in parts:
        pl = p.lower().strip(".")
        if pl in _MONTHS:
            month = _MONTHS[pl]
        elif pl.isdigit() and len(pl) == 4:
            try:
                year = int(pl)
            except ValueError:
                pass

    if year is None:
        return None
    if month is None:
        month = 6
    day = 15
    try:
        return _dt.date(year, month, day)
    except ValueError:
        return None


def recency_score(date: _dt.date | None, today: _dt.date | None = None) -> float:
    """1.0 if within the last 365 days; linear decay to 0.0 over the next 4 years."""
    if date is None:
        return 0.5
    today = today or _dt.date.today()
    days = (today - date).days
    if days < 0:
        return 1.0
    if days <= 365:
        return 1.0
    extra = days - 365
    decay_window = 365 * 4
    if extra >= decay_window:
        return 0.0
    return 1.0 - (extra / decay_window)
