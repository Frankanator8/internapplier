from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .applications import router as applications_router
from .health import router as health_router
from .profile import router as profile_router


app = FastAPI(title="I*ternship Localhost API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^(moz-extension://.*|null)$",
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(profile_router)
app.include_router(applications_router)


__all__ = ["app"]
