from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import data_store
from .schemas import ApplicationEntry, AttachLinkBody, BulkApplicationsBody

router = APIRouter()


@router.get("/applications")
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


@router.post("/applications")
def create_application(entry: ApplicationEntry) -> dict:
    data = data_store.load()
    apps = data.get("applications") or []
    apps.append(entry.model_dump())
    data["applications"] = apps
    data_store.save(data)
    return {"ok": True, "count": len(apps)}


@router.post("/applications/bulk")
def bulk_create_applications(body: BulkApplicationsBody) -> dict:
    data = data_store.load()
    apps = data.get("applications") or []
    added = 0
    for entry in body.entries:
        apps.append(entry.model_dump())
        added += 1
    data["applications"] = apps
    data_store.save(data)
    return {"ok": True, "added": added, "count": len(apps)}


@router.post("/applications/{index}/links")
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
