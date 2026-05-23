import datetime
import json
import re

TOOL_EVENT_PREFIX = "\x1e"


def _today(today: str | None) -> str:
    return today or datetime.date.today().isoformat()


def _common_context_sections(
    *,
    profile: dict | None = None,
    company_name: str | None = None,
    company_research: dict | None = None,
    job_description: str | None = None,
) -> list[str]:
    """Common `<tag>...</tag>` blocks shared across LLM call sites.

    Callers prepend `<today>` (and any operation-specific blocks like
    `<question>`/`<response>`) themselves; the order returned here is
    company_name → profile → company_research → job_description.
    """
    sections: list[str] = []
    if company_name:
        sections.append(f"<company_name>{company_name}</company_name>")
    if profile is not None:
        sections.append(f"<profile>\n{_profile_json(profile)}\n</profile>")
    if company_research:
        sections.append(
            f"<company_research>\n"
            f"{json.dumps(company_research, separators=(',', ':'))}\n"
            f"</company_research>"
        )
    if job_description:
        sections.append(f"<job_description>\n{job_description}\n</job_description>")
    return sections


def strip_code_fence(raw: str, lang_hints: tuple[str, ...] = ()) -> str:
    raw = raw.strip()
    for hint in lang_hints:
        closed = re.search(
            r"```" + re.escape(hint) + r"[ \t]*\r?\n(.*?)```",
            raw, re.DOTALL | re.IGNORECASE,
        )
        if closed:
            return closed.group(1).strip()
        unclosed = re.search(
            r"```" + re.escape(hint) + r"[ \t]*\r?\n(.*)\Z",
            raw, re.DOTALL | re.IGNORECASE,
        )
        if unclosed:
            return unclosed.group(1).rstrip("`").strip()
    closed = re.search(r"```[a-zA-Z0-9_+-]*[ \t]*\r?\n(.*?)```", raw, re.DOTALL)
    if closed:
        return closed.group(1).strip()
    unclosed = re.search(r"```[a-zA-Z0-9_+-]*[ \t]*\r?\n(.*)\Z", raw, re.DOTALL)
    if unclosed:
        return unclosed.group(1).rstrip("`").strip()
    return raw

_PROFILE_KEYS = ("experience", "projects", "education", "awards", "skills", "hobbies")


def _profile_json(profile: dict) -> str:
    return json.dumps(
        {k: profile.get(k, []) for k in _PROFILE_KEYS},
        separators=(",", ":"),
    )


def _format_tool_event(name: str, round_idx: int, args: dict, result: dict) -> str:
    latex_arg = args.get("latex") if isinstance(args, dict) else None
    latex_chars = len(latex_arg) if isinstance(latex_arg, str) else 0
    ok = result.get("ok")
    badge = "✓" if ok else "✗"

    parts = [f"[tool {badge}] {name} (round {round_idx}, latex={latex_chars} chars)"]
    if name == "page_length" and ok:
        fill = result.get("fill")
        cap = result.get("page_cap")
        try:
            parts.append(f"  → fill={float(fill):.3f} / page_cap={cap}")
        except (TypeError, ValueError):
            parts.append(f"  → fill={fill} / page_cap={cap}")
    elif ok:
        parts.append("  → ok")
    else:
        excerpt = (result.get("log_excerpt") or result.get("error") or "").strip()
        if excerpt:
            lines = excerpt.splitlines()[:6]
            parts.append("  → failed:")
            parts.extend(f"      {ln}" for ln in lines)
        else:
            parts.append("  → failed")
    return "\n".join(parts) + "\n"


def _format_context(context: dict) -> str:
    kind = context.get("type", "")
    if kind == "experience":
        return (
            f"Context: Work experience at {context.get('company', 'a company')}, "
            f"role: {context.get('role', 'unknown role')}."
        )
    if kind == "project":
        return f"Context: Personal/academic project — {context.get('name', 'unnamed project')}."
    if kind == "education":
        return (
            f"Context: Education at {context.get('school', 'a school')}, "
            f"degree: {context.get('degree', 'unknown degree')}."
        )
    return ""
