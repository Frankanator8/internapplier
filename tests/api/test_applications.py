from __future__ import annotations

from api.applications import app_label, job_context


def test_app_label_joins_company_and_role():
    assert app_label({"company": " Acme ", "role": "SWE Intern"}) == "Acme — SWE Intern"


def test_app_label_uses_whichever_half_exists():
    assert app_label({"company": "Acme"}) == "Acme"
    assert app_label({"role": "SWE"}) == "SWE"


def test_app_label_fallback():
    assert app_label({}) == "(untitled)"
    assert app_label({"company": "  "}, fallback="(untitled job)") == "(untitled job)"


def test_job_context_blanks_become_none():
    ctx = job_context({"company": "", "description": "JD"}, {"summary": "s"})
    assert ctx == {"company_name": None, "company_research": {"summary": "s"}, "job_description": "JD"}
