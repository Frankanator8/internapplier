from __future__ import annotations

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
    company: str = ""
    role: str = ""
    date: str = ""
    links: list[str] = Field(default_factory=list)
    status: str = DEFAULT_STATUS
    notes: str = ""
    description: str = ""
    interview_questions: list = Field(default_factory=list)


class AttachLinkBody(BaseModel):
    url: str


class BulkApplicationsBody(BaseModel):
    entries: list[ApplicationEntry] = Field(default_factory=list)


class AnswerQuestionBody(BaseModel):
    question: str
    application_index: int | None = None
