from __future__ import annotations

from fastapi import APIRouter

from api.ai_provider import get_theme_preference

router = APIRouter()


@router.get("/theme")
def theme() -> dict:
    return {"preference": get_theme_preference()}
