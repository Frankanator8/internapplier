from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from ..constants import ALL_FIELDS, COMBO_FIELDS, DEFAULT_STATUS, LINE_FIELDS

__all__ = [
    "ALL_FIELDS",
    "COMBO_FIELDS",
    "LINE_FIELDS",
    "ApplicationEntry",
    "AttachLinkBody",
    "BulkApplicationsBody",
    "AnswerQuestionBody",
]


class ApplicationEntry(BaseModel):
    uuid: str = Field(default_factory=lambda: uuid.uuid4().hex)
    company: str = ""
    role: str = ""
    date: str = ""
    links: list[str] = Field(default_factory=list)
    status: str = DEFAULT_STATUS
    notes: str = ""
    description: str = ""
    interview_questions: list = Field(default_factory=list)
    resume_pdf: str = ""


class AttachLinkBody(BaseModel):
    url: str


class BulkApplicationsBody(BaseModel):
    entries: list[ApplicationEntry] = Field(default_factory=list)


class AnswerQuestionBody(BaseModel):
    question: str
    application_uuid: str | None = None
