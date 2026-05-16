"""Anthropic tool-use JSON schemas for the resume-generation tools.

Kept in one file so the LLM-facing surface area is easy to audit and edit.
"""

LIST_EXPERIENCES = {
    "name": "list_experiences",
    "description": (
        "List the applicant's work experiences as lightweight summaries "
        "(id, company, role, category, dates). Call get_experience_detail "
        "with the id to fetch bullets and skills."
    ),
    "input_schema": {"type": "object", "properties": {}, "required": []},
}

LIST_PROJECTS = {
    "name": "list_projects",
    "description": (
        "List the applicant's projects (id, name, url). Call get_project_detail "
        "with the id to fetch bullets and skills."
    ),
    "input_schema": {"type": "object", "properties": {}, "required": []},
}

LIST_EDUCATION = {
    "name": "list_education",
    "description": (
        "List the applicant's education entries (id, school, degree, dates). "
        "Call get_education_detail with the id for GPA, courses, bullets, skills."
    ),
    "input_schema": {"type": "object", "properties": {}, "required": []},
}

LIST_AWARDS = {
    "name": "list_awards",
    "description": (
        "List the applicant's awards (id, title, issuer, date). "
        "Call get_award_detail with the id for bullets and skills."
    ),
    "input_schema": {"type": "object", "properties": {}, "required": []},
}

LIST_SKILLS = {
    "name": "list_skills",
    "description": "Return the applicant's flat list of self-declared skills.",
    "input_schema": {"type": "object", "properties": {}, "required": []},
}

LIST_HOBBIES = {
    "name": "list_hobbies",
    "description": "Return the applicant's hobbies.",
    "input_schema": {"type": "object", "properties": {}, "required": []},
}

GET_EXPERIENCE_DETAIL = {
    "name": "get_experience_detail",
    "description": "Fetch the full record for one experience (bullets, skills, dates).",
    "input_schema": {
        "type": "object",
        "properties": {"id": {"type": "string", "description": "id from list_experiences, e.g. 'exp_0'"}},
        "required": ["id"],
    },
}

GET_PROJECT_DETAIL = {
    "name": "get_project_detail",
    "description": "Fetch the full record for one project (bullets, skills, url).",
    "input_schema": {
        "type": "object",
        "properties": {"id": {"type": "string", "description": "id from list_projects, e.g. 'proj_0'"}},
        "required": ["id"],
    },
}

GET_EDUCATION_DETAIL = {
    "name": "get_education_detail",
    "description": "Fetch the full record for one education entry (GPA, bullets, skills, courses).",
    "input_schema": {
        "type": "object",
        "properties": {"id": {"type": "string", "description": "id from list_education, e.g. 'edu_0'"}},
        "required": ["id"],
    },
}

GET_AWARD_DETAIL = {
    "name": "get_award_detail",
    "description": "Fetch the full record for one award (bullets, skills).",
    "input_schema": {
        "type": "object",
        "properties": {"id": {"type": "string", "description": "id from list_awards, e.g. 'award_0'"}},
        "required": ["id"],
    },
}

SEARCH_BY_SKILL = {
    "name": "search_by_skill",
    "description": (
        "Find every experience, project, education entry, or award whose skill list "
        "contains the given skill (case-insensitive substring match). Returns ids "
        "so the model can follow up with get_*_detail."
    ),
    "input_schema": {
        "type": "object",
        "properties": {"skill": {"type": "string", "description": "Skill or technology name to search for"}},
        "required": ["skill"],
    },
}

ESTIMATE_PAGE_COUNT = {
    "name": "estimate_page_count",
    "description": (
        "Roughly estimate how many US-letter pages the given LaTeX resume source "
        "will occupy. Heuristic only — use to gauge whether content is approaching "
        "1 page, not for exact layout decisions."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "resume_text": {
                "type": "string",
                "description": "LaTeX source of the resume so far.",
            }
        },
        "required": ["resume_text"],
    },
}
