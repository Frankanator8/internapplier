from __future__ import annotations


def lookup(cache: dict, company: str) -> dict | None:
    if not company or not cache:
        return None
    entry = cache.get(company)
    if entry is None:
        for k, v in cache.items():
            if k.lower() == company.lower():
                entry = v
                break
    if entry is None:
        return None
    if isinstance(entry, dict) and "result" in entry and isinstance(entry["result"], dict):
        return entry["result"]
    if isinstance(entry, dict) and {"summary", "core_values", "recent_projects"} & entry.keys():
        return entry
    return None
