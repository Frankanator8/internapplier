from __future__ import annotations

from pydantic import BaseModel, Field

from ..constants import DEFAULT_STATUS


LINE_FIELDS = [
    "first_name", "last_name", "preferred_name", "pronouns",
    "email", "phone", "address1", "address2", "city", "state",
    "postal_code", "country", "linkedin", "website", "github",
    "earliest_start_date", "desired_salary", "date_of_birth",
]
COMBO_FIELDS = [
    "employment_status", "work_authorization", "require_sponsorship",
    "willing_to_relocate", "gender", "ethnicity", "veteran_status",
    "disability_status",
]
ALL_FIELDS = LINE_FIELDS + COMBO_FIELDS


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


class AnswerQuestionBody(BaseModel):
    question: str
    application_index: int | None = None
