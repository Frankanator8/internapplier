"""Standalone test entry point for the generate_resume module.

Usage examples:
    python test_generate_resume.py --jd "Software engineering intern. Python, ML infra..."
    python test_generate_resume.py --jd-file jd.txt
    python test_generate_resume.py --jd-file jd.txt --company Acme --url https://acme.com
    python test_generate_resume.py --jd-file jd.txt --latex
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import pathlib
import sys


def _load_dotenv(path: pathlib.Path = pathlib.Path(".env")) -> None:
    if not path.exists():
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


_load_dotenv()

from app.ai_provider import get_provider
from app.data_store import load as load_profile
from app.generate_resume import ResumeGenerator


def _read_jd(args) -> str:
    if args.jd:
        return args.jd
    if args.jd_file:
        return pathlib.Path(args.jd_file).read_text(encoding="utf-8")
    print("Paste the job description, then end with Ctrl-D (Unix) / Ctrl-Z+Enter (Windows):")
    return sys.stdin.read()


def _from_cache(cache: dict, company: str) -> dict | None:
    """Cache shape: {company_name: {"url": str, "result": research_dict}}.
    Returns the unwrapped research dict, or None if not found."""
    if not company:
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


def _research(args, profile: dict) -> dict:
    cache = profile.get("research_cache") or {}
    if args.company:
        cached = _from_cache(cache, args.company)
        if cached is not None:
            print(f"[info] using cached research for {args.company!r}")
            return cached

    if args.company and args.url:
        try:
            from app.web_scraper import fetch_company_pages
        except Exception as e:
            print(f"[warn] could not import web_scraper: {e}; using stub research")
            return _stub_research(args.company)
        print(f"[info] no cache hit — scraping {args.url} ...")
        try:
            text = fetch_company_pages(args.url)
            return get_provider().research_company(args.company, text)
        except Exception as e:
            print(f"[warn] research_company failed: {e}; using stub research")
            return _stub_research(args.company)

    return _stub_research(args.company or "the target company")


def _stub_research(company: str) -> dict:
    return {
        "summary": f"{company} is the target company.",
        "core_values": [],
        "recent_projects": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jd", help="Job description as a string.")
    parser.add_argument("--jd-file", help="Path to file with job description.")
    parser.add_argument("--company", help="Company name (for cached or live research).")
    parser.add_argument("--url", help="Company URL (triggers live scrape + research).")
    parser.add_argument("--latex", action="store_true", help="Also call generate_latex and write out.tex.")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    profile = load_profile()
    jd = _read_jd(args).strip()
    if not jd:
        print("error: no job description provided", file=sys.stderr)
        return 2

    research = _research(args, profile)
    print("\n=== Company Research ===")
    print(json.dumps(research, indent=2))

    gen = ResumeGenerator(profile, jd, research)

    print("\n=== Selected Courses (top 10) ===")
    try:
        courses = gen.select_courses(10)
        for c in courses:
            print(f"  - {c}")
        print(f"  ({len(courses)} courses returned)")
    except Exception as e:
        print(f"[error] select_courses failed: {e}")

    print("\n=== Scored Entries ===")
    try:
        scored = gen.score_entries()
    except Exception as e:
        print(f"[error] score_entries failed: {e}")
        return 1

    for section in ("relevant_experience", "projects", "awards", "leadership"):
        print(f"\n-- {section} --")
        rows = scored.get(section, [])
        if not rows:
            print("  (none)")
            continue
        for r in rows:
            print(
                f"  {r['final_score']:.3f}  ai={r['ai']}  recency={r['recency']:.2f}  "
                f"{r['label']}"
            )

    print("\n=== build_filtered_profile() keys ===")
    filtered = gen.build_filtered_profile()
    print("  keys:", sorted(filtered.keys()))
    print("  experience:", len(filtered["experience"]),
          "projects:", len(filtered["projects"]),
          "awards:", len(filtered["awards"]),
          "education:", len(filtered["education"]))

    if args.latex:
        print("\n=== generate_latex() ===")
        latex = gen.generate_latex()
        out = pathlib.Path("out.tex")
        out.write_text(latex, encoding="utf-8")
        ok = latex.lstrip().startswith("\\documentclass")
        print(f"  wrote {out} ({len(latex)} chars). starts with \\documentclass: {ok}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
