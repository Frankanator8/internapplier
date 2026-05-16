import re

from .registry import tool
from . import schemas


_COMMENT_RE = re.compile(r"(?<!\\)%.*")
_CMD_WITH_ARG_RE = re.compile(r"\\[a-zA-Z]+\*?\s*(\[[^\]]*\])?\s*\{([^{}]*)\}")
_BARE_CMD_RE = re.compile(r"\\[a-zA-Z]+\*?")
_BRACES_RE = re.compile(r"[{}]")

LINES_PER_PAGE = 50.0


@tool(schemas.ESTIMATE_PAGE_COUNT)
def estimate_page_count(inp: dict, _context: dict) -> dict:
    text = inp.get("resume_text") or ""

    item_count = len(re.findall(r"\\item\b", text))
    section_count = len(re.findall(r"\\(section|subsection|cvsection|resumeSubheading)\*?\b", text))

    stripped = _COMMENT_RE.sub("", text)
    # Replace \cmd{arg} with arg so visible text survives one level deep.
    for _ in range(3):
        new = _CMD_WITH_ARG_RE.sub(lambda m: " " + m.group(2) + " ", stripped)
        if new == stripped:
            break
        stripped = new
    stripped = _BARE_CMD_RE.sub(" ", stripped)
    stripped = _BRACES_RE.sub(" ", stripped)

    content_lines = sum(1 for ln in stripped.splitlines() if ln.strip())

    weighted = content_lines + 0.2 * item_count + 1.0 * section_count
    estimated = round(weighted / LINES_PER_PAGE, 2)

    return {
        "estimated_pages": estimated,
        "lines": content_lines,
        "items": item_count,
        "sections": section_count,
        "notes": (
            "Rough heuristic: strips LaTeX commands, counts non-empty content lines, "
            f"adds weight for \\item and section headers, assumes ~{int(LINES_PER_PAGE)} "
            "content lines per US-letter page. Not a substitute for compiling."
        ),
    }
