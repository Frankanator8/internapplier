from __future__ import annotations

from fastapi import APIRouter

from api.app_settings import get_theme_preference

router = APIRouter()


@router.get("/theme")
def theme() -> dict:
    return {"preference": get_theme_preference()}
