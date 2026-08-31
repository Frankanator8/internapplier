"""A fictional resume used to preview LaTeX templates.

Shaped exactly like the JSON the generator produces (see
``validate_resume_shape`` in ``render.py``), and covers every ``kind`` the
default template branches on, so previewing a custom template exercises all
of its section handling. Bullets are metric-led and roughly the length real
generated bullets run to, so line wrapping and page fill look honest.
"""
from __future__ import annotations

SAMPLE_RESUME: dict = {
    "header": {
        "name": "Jordan Alvarez",
        "email": "jordan.alvarez@example.com",
        "phone": "(555) 010-2938",
        "location": "Toronto, ON",
        "links": [
            {"label": "github.com/jalvarez", "url": "https://github.com/jalvarez"},
            {"label": "linkedin.com/in/jalvarez", "url": "https://linkedin.com/in/jalvarez"},
        ],
    },
    "sections": [
        {
            "kind": "education",
            "items": [
                {
                    "school": "University of Waterloo",
                    "degree": "BASc, Computer Engineering",
                    "start": "Sep 2023",
                    "end": "Apr 2028",
                    "gpa": "3.9/4.0",
                    "courses": [
                        "Data Structures & Algorithms",
                        "Operating Systems",
                        "Databases",
                        "Machine Learning",
                        "Computer Networks",
                    ],
                },
            ],
        },
        {
            "kind": "experience",
            "items": [
                {
                    "role": "Software Engineer Intern",
                    "company": "Northwind Labs",
                    "location": "Toronto, ON",
                    "start": "May 2025",
                    "end": "Aug 2025",
                    "bullets": [
                        "Cut p95 API latency from 340ms to 90ms by adding a Redis read-through "
                        "cache across 12 endpoints serving 200k daily requests",
                        "Built a batch ingest job in Python processing 4M rows/day, replacing a "
                        "manual pipeline and saving the data team ~6 hours a week",
                        "Raised backend test coverage from 41% to 78% and wired the suite into CI, "
                        "cutting regressions caught in QA by roughly half",
                    ],
                },
                {
                    "role": "Backend Developer Intern",
                    "company": "Cedar & Bloom Analytics",
                    "location": "Remote",
                    "start": "Jan 2025",
                    "end": "Apr 2025",
                    "bullets": [
                        "Designed a Postgres schema and REST API for a reporting product used by "
                        "30+ enterprise customers, shipping it two weeks ahead of schedule",
                        "Instrumented services with structured logging and Grafana dashboards, "
                        "cutting mean time to diagnose incidents from 45 to 12 minutes",
                        "Automated nightly report delivery with Celery, eliminating a daily manual "
                        "step and reducing delivery errors to zero over three months",
                    ],
                },
            ],
        },
        {
            "kind": "projects",
            "items": [
                {
                    "name": "TrailMark",
                    "tagline": "Offline-first hiking tracker",
                    "start": "Sep 2024",
                    "end": "Dec 2024",
                    "bullets": [
                        "Built a React Native app with local SQLite sync that keeps full trail "
                        "history usable with no signal; 1.2k downloads in the first month",
                        "Shrank map tile storage 60% with a custom quadtree cache eviction policy",
                    ],
                },
                {
                    "name": "ParseKit",
                    "tagline": "Open-source LaTeX resume parser",
                    "start": "Feb 2024",
                    "end": "Present",
                    "bullets": [
                        "Wrote a tolerant tokenizer that recovers structure from malformed LaTeX, "
                        "reaching 96% field-extraction accuracy on a 500-resume benchmark",
                        "Maintained the project through 40+ community issues and 9 merged PRs",
                    ],
                },
            ],
        },
        {
            "kind": "skills",
            "groups": [
                {
                    "label": "Languages",
                    "items": ["Python", "TypeScript", "Go", "SQL", "C++"],
                },
                {
                    "label": "Frameworks",
                    "items": ["FastAPI", "React", "PyTorch", "Django", "Qt"],
                },
                {
                    "label": "Tools",
                    "items": ["Docker", "Postgres", "Redis", "AWS", "Git", "Grafana"],
                },
            ],
        },
        {
            "kind": "awards",
            "items": [
                {
                    "title": "1st Place, HackTheNorth",
                    "issuer": "University of Waterloo",
                    "date": "Sep 2024",
                },
                {
                    "title": "President's Entrance Scholarship",
                    "issuer": "University of Waterloo",
                    "date": "Sep 2023",
                },
            ],
        },
        {
            "kind": "hobbies",
            "items": ["Trail running", "Film photography", "Bread baking", "Chess"],
        },
    ],
}
