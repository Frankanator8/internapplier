from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import data_store
from .constants import DEFAULT_STATUS, STATUS_OPTIONS


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


app = FastAPI(title="InternApplier Localhost API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^(moz-extension://.*|null)$",
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.get("/profile")
def profile() -> dict:
    return data_store.load()


@app.get("/profile/general_info")
def general_info() -> dict:
    return data_store.load().get("general_info", {})


@app.get("/statuses")
def statuses() -> dict:
    return {"statuses": STATUS_OPTIONS, "default": DEFAULT_STATUS}


@app.get("/autofill/fields")
def autofill_fields() -> dict:
    info = data_store.load().get("general_info", {}) or {}
    return {key: info.get(key, "") for key in ALL_FIELDS}


@app.get("/applications")
def list_applications() -> list[dict]:
    apps = data_store.load().get("applications") or []
    out = []
    for i, e in enumerate(apps):
        if not isinstance(e, dict):
            continue
        out.append({
            "index": i,
            "company": e.get("company", ""),
            "role": e.get("role", ""),
            "links": e.get("links") or [],
        })
    return out


@app.post("/applications")
def create_application(entry: ApplicationEntry) -> dict:
    data = data_store.load()
    apps = data.get("applications") or []
    apps.append(entry.model_dump())
    data["applications"] = apps
    data_store.save(data)
    return {"ok": True, "count": len(apps)}


@app.post("/applications/{index}/links")
def attach_link(index: int, body: AttachLinkBody) -> dict:
    url = (body.url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="url required")
    data = data_store.load()
    apps = data.get("applications") or []
    if not (0 <= index < len(apps)):
        raise HTTPException(status_code=404, detail="application not found")
    entry = apps[index]
    links = entry.get("links")
    if not isinstance(links, list):
        links = []
    if url not in links:
        links.append(url)
    entry["links"] = links
    apps[index] = entry
    data["applications"] = apps
    data_store.save(data)
    return {"ok": True, "links": links}
