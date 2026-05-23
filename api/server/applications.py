from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .. import data_store
from .schemas import ApplicationEntry, AttachLinkBody, BulkApplicationsBody

router = APIRouter()


class SetResumePdfBody(BaseModel):
    pdf_path: str


@router.get("/applications")
def list_applications() -> list[dict]:
    apps = data_store.load().get("applications") or []
    out = []
    for e in apps:
        if not isinstance(e, dict):
            continue
        out.append({
            "uuid": e.get("uuid", ""),
            "company": e.get("company", ""),
            "role": e.get("role", ""),
            "links": e.get("links") or [],
            "resume_pdf": e.get("resume_pdf", ""),
        })
    return out


@router.post("/applications")
def create_application(entry: ApplicationEntry) -> dict:
    data = data_store.load()
    apps = data.get("applications") or []
    apps.append(entry.model_dump())
    data["applications"] = apps
    data_store.save(data)
    return {"ok": True, "count": len(apps), "uuid": entry.uuid}


@router.post("/applications/bulk")
def bulk_create_applications(body: BulkApplicationsBody) -> dict:
    data = data_store.load()
    apps = data.get("applications") or []
    added = 0
    uuids: list[str] = []
    for entry in body.entries:
        apps.append(entry.model_dump())
        uuids.append(entry.uuid)
        added += 1
    data["applications"] = apps
    data_store.save(data)
    return {"ok": True, "added": added, "count": len(apps), "uuids": uuids}


@router.post("/applications/by-uuid/{uuid}/links")
def attach_link(uuid: str, body: AttachLinkBody) -> dict:
    url = (body.url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="url required")
    try:
        links = data_store.attach_application_link(uuid, url)
    except KeyError:
        raise HTTPException(status_code=404, detail="application not found")
    return {"ok": True, "links": links}


def _serve_resume(entry: dict):
    pdf_path = entry.get("resume_pdf") or ""
    if not pdf_path:
        raise HTTPException(status_code=404, detail="resume pdf not linked")
    p = Path(pdf_path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="resume pdf not found")
    return FileResponse(str(p), media_type="application/pdf", filename=p.name)


@router.get("/applications/by-uuid/{uuid}/resume.pdf")
def get_application_resume_by_uuid(uuid: str):
    found = data_store.find_application_by_uuid(uuid)
    if found is None:
        raise HTTPException(status_code=404, detail="application not found")
    _, entry = found
    return _serve_resume(entry)


@router.post("/applications/by-uuid/{uuid}/resume")
def set_application_resume(uuid: str, body: SetResumePdfBody) -> dict:
    pdf_path = (body.pdf_path or "").strip()
    if not pdf_path:
        raise HTTPException(status_code=400, detail="pdf_path required")
    try:
        entry = data_store.set_application_resume_pdf(uuid, pdf_path)
    except KeyError:
        raise HTTPException(status_code=404, detail="application not found")
    return {"ok": True, "uuid": uuid, "resume_pdf": entry.get("resume_pdf", "")}
