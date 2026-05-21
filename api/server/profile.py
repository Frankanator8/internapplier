from __future__ import annotations

from fastapi import APIRouter

from .. import data_store
from ..constants import DEFAULT_STATUS, STATUS_OPTIONS
from .schemas import ALL_FIELDS

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
