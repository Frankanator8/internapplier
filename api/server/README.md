# api/server/

FastAPI route modules mounted by `api/server/__init__.py` into the app served on `127.0.0.1:8765`.

| File | Purpose |
|---|---|
| `health.py` | `GET /health` liveness probe. |
| `profile.py` | `GET /profile`, `/profile/general_info`, `/autofill/fields` — read endpoints used by the Firefox extension. |
| `applications.py` | CRUD routes for application tracker entries. |
| `theme.py` | Theme preference endpoints. |
| `schemas.py` | Shared Pydantic request/response models. |
