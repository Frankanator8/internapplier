from __future__ import annotations

from fastapi import APIRouter

from .. import data_store
from ..ai_provider import get_provider
from ..constants import DEFAULT_STATUS, STATUS_OPTIONS
from .schemas import ALL_FIELDS, AnswerQuestionBody

router = APIRouter()


@router.get("/profile")
def profile() -> dict:
    return data_store.load()


@router.get("/profile/general_info")
def general_info() -> dict:
    return data_store.load().get("general_info", {})


@router.get("/statuses")
def statuses() -> dict:
    return {"statuses": STATUS_OPTIONS, "default": DEFAULT_STATUS}


@router.get("/autofill/fields")
def autofill_fields() -> dict:
    info = data_store.load().get("general_info", {}) or {}
    return {key: info.get(key, "") for key in ALL_FIELDS}


@router.post("/answer/question")
def answer_question(body: AnswerQuestionBody) -> dict:
    profile = data_store.load()
    apps = profile.get("applications") or []
    company = None
    job_description = None
    if body.application_index is not None and 0 <= body.application_index < len(apps):
        app = apps[body.application_index]
        if isinstance(app, dict):
            company = app.get("company") or None
            job_description = app.get("description") or None
    chunks = list(get_provider().answer_question_stream(
        question=body.question,
        profile=profile,
        company_name=company,
        job_description=job_description,
    ))
    return {"answer": "".join(chunks)}
