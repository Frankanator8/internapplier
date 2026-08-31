"""Merge an imported profile dict into the on-disk resume store.

Shared by every importer (LinkedIn ZIP, resume PDF) so the merge rules can't
drift between them. Two modes:

    replace  — imported sections overwrite the stored ones wholesale
    append   — imported entries are added after the stored ones

``replace`` only touches sections the importer actually emits — a source that
has no concept of hobbies (the LinkedIn export) must not clear them. For the
same reason ``general_info`` is overlaid rather than cleared in both modes:
wiping someone's phone number because their resume omitted it would be the
wrong kind of surprise.
"""
from __future__ import annotations

# Sections held as lists of entry dicts.
LIST_SECTIONS = ("experience", "projects", "education", "awards")
# Sections held as flat lists of strings, deduped case-insensitively on append.
FLAT_SECTIONS = ("skills", "hobbies")


def merge_profile(store: dict, data: dict, mode: str = "append") -> dict:
    """Return a new store with ``data`` merged in. Neither argument is mutated."""
    merged = dict(store)

    for key in LIST_SECTIONS:
        if key not in data:
            continue
        incoming = list(data.get(key) or [])
        if mode == "replace":
            merged[key] = incoming
        else:
            merged[key] = list(merged.get(key) or []) + incoming

    for key in FLAT_SECTIONS:
        if key not in data:
            continue
        incoming = [str(x) for x in (data.get(key) or [])]
        if mode == "replace":
            merged[key] = incoming
        else:
            existing = list(merged.get(key) or [])
            seen = {str(x).lower() for x in existing}
            for value in incoming:
                if value.lower() not in seen:
                    existing.append(value)
                    seen.add(value.lower())
            merged[key] = existing

    imported_general = data.get("general_info") or {}
    if imported_general:
        current_general = merged.get("general_info") or {}
        if mode == "replace":
            merged["general_info"] = {**current_general, **imported_general}
        else:
            filled = dict(current_general)
            for k, v in imported_general.items():
                if not filled.get(k):
                    filled[k] = v
            merged["general_info"] = filled

    return merged


def apply_to_store(data: dict, mode: str = "append") -> None:
    """Merge ``data`` into the resume store on disk.

    Used by flows that don't have the main window open (e.g. onboarding). The
    toolbar import paths in MainWindow update live UI widgets instead.
    """
    from . import data_store

    data_store.save(merge_profile(data_store.load(), data, mode))
