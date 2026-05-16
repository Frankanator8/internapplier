from .registry import ToolError, tool
from . import schemas


def _profile(context: dict) -> dict:
    profile = context.get("profile")
    if profile is None:
        raise ToolError("context['profile'] is missing")
    return profile


def _lookup(items: list, prefix: str, item_id: str) -> dict:
    if not item_id.startswith(prefix + "_"):
        raise ToolError(f"id must start with '{prefix}_', got {item_id!r}")
    try:
        idx = int(item_id[len(prefix) + 1 :])
    except ValueError:
        raise ToolError(f"invalid id: {item_id!r}")
    if idx < 0 or idx >= len(items):
        raise ToolError(f"id out of range: {item_id!r}")
    return items[idx]


@tool(schemas.LIST_EXPERIENCES)
def list_experiences(_inp: dict, context: dict) -> dict:
    items = _profile(context).get("experience", []) or []
    return {
        "experiences": [
            {
                "id": f"exp_{i}",
                "company": x.get("company", ""),
                "role": x.get("role", ""),
                "category": x.get("category", ""),
                "start": x.get("start", ""),
                "end": x.get("end", ""),
            }
            for i, x in enumerate(items)
        ]
    }


@tool(schemas.LIST_PROJECTS)
def list_projects(_inp: dict, context: dict) -> dict:
    items = _profile(context).get("projects", []) or []
    return {
        "projects": [
            {"id": f"proj_{i}", "name": x.get("name", ""), "url": x.get("url", "")}
            for i, x in enumerate(items)
        ]
    }


@tool(schemas.LIST_EDUCATION)
def list_education(_inp: dict, context: dict) -> dict:
    items = _profile(context).get("education", []) or []
    return {
        "education": [
            {
                "id": f"edu_{i}",
                "school": x.get("school", ""),
                "degree": x.get("degree", ""),
                "start": x.get("start", ""),
                "end": x.get("end", ""),
            }
            for i, x in enumerate(items)
        ]
    }


@tool(schemas.LIST_AWARDS)
def list_awards(_inp: dict, context: dict) -> dict:
    items = _profile(context).get("awards", []) or []
    return {
        "awards": [
            {
                "id": f"award_{i}",
                "title": x.get("title", ""),
                "issuer": x.get("issuer", ""),
                "date": x.get("date", ""),
            }
            for i, x in enumerate(items)
        ]
    }


@tool(schemas.LIST_SKILLS)
def list_skills(_inp: dict, context: dict) -> dict:
    return {"skills": list(_profile(context).get("skills", []) or [])}


@tool(schemas.LIST_HOBBIES)
def list_hobbies(_inp: dict, context: dict) -> dict:
    return {"hobbies": list(_profile(context).get("hobbies", []) or [])}


@tool(schemas.GET_EXPERIENCE_DETAIL)
def get_experience_detail(inp: dict, context: dict) -> dict:
    items = _profile(context).get("experience", []) or []
    entry = _lookup(items, "exp", inp["id"])
    return {"id": inp["id"], **entry}


@tool(schemas.GET_PROJECT_DETAIL)
def get_project_detail(inp: dict, context: dict) -> dict:
    items = _profile(context).get("projects", []) or []
    entry = _lookup(items, "proj", inp["id"])
    return {"id": inp["id"], **entry}


@tool(schemas.GET_EDUCATION_DETAIL)
def get_education_detail(inp: dict, context: dict) -> dict:
    items = _profile(context).get("education", []) or []
    entry = _lookup(items, "edu", inp["id"])
    return {"id": inp["id"], **entry}


@tool(schemas.GET_AWARD_DETAIL)
def get_award_detail(inp: dict, context: dict) -> dict:
    items = _profile(context).get("awards", []) or []
    entry = _lookup(items, "award", inp["id"])
    return {"id": inp["id"], **entry}


@tool(schemas.SEARCH_BY_SKILL)
def search_by_skill(inp: dict, context: dict) -> dict:
    needle = (inp.get("skill") or "").strip().lower()
    if not needle:
        raise ToolError("skill must be a non-empty string")
    profile = _profile(context)
    matches: dict[str, list[dict]] = {
        "experiences": [],
        "projects": [],
        "education": [],
        "awards": [],
    }

    def has_skill(entry: dict) -> bool:
        return any(needle in (s or "").lower() for s in entry.get("skills", []) or [])

    for i, x in enumerate(profile.get("experience", []) or []):
        if has_skill(x):
            matches["experiences"].append(
                {"id": f"exp_{i}", "company": x.get("company", ""), "role": x.get("role", "")}
            )
    for i, x in enumerate(profile.get("projects", []) or []):
        if has_skill(x):
            matches["projects"].append({"id": f"proj_{i}", "name": x.get("name", "")})
    for i, x in enumerate(profile.get("education", []) or []):
        if has_skill(x):
            matches["education"].append(
                {"id": f"edu_{i}", "school": x.get("school", ""), "degree": x.get("degree", "")}
            )
    for i, x in enumerate(profile.get("awards", []) or []):
        if has_skill(x):
            matches["awards"].append({"id": f"award_{i}", "title": x.get("title", "")})

    return {"skill": inp["skill"], "matches": matches}
