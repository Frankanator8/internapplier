from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import data_store


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


app = FastAPI(title="InternApplier Localhost API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^(moz-extension://.*|null)$",
    allow_methods=["GET"],
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


@app.get("/autofill/fields")
def autofill_fields() -> dict:
    info = data_store.load().get("general_info", {}) or {}
    return {key: info.get(key, "") for key in ALL_FIELDS}
