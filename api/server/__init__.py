from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ..data_store import ApplicationNotFound
from ..resume_pipeline import ResumePipelineError
from .applications import router as applications_router
from .health import router as health_router
from .profile import router as profile_router
from .theme import router as theme_router


app = FastAPI(title="I*ternship Localhost API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^(moz-extension://.*|null)$",
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.exception_handler(ApplicationNotFound)
async def _application_not_found_handler(_request: Request, exc: ApplicationNotFound) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": "application not found"})


@app.exception_handler(ResumePipelineError)
async def _resume_pipeline_error_handler(_request: Request, exc: ResumePipelineError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


app.include_router(health_router)
app.include_router(profile_router)
app.include_router(applications_router)
app.include_router(theme_router)


__all__ = ["app"]
