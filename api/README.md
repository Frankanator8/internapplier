# InternApplier Localhost API

A small FastAPI server that exposes the saved InternApplier profile (read from
`~/Library/Application Support/InternApplier/resume.json`) over HTTP on
`127.0.0.1:8765`. It is the data source for the Firefox autofill extension in
`../extension/`.

## Install

```
pip install -r requirements.txt
```

(Run from the repo root so `app/` is importable as a sibling of `api/`.)

## Run

```
python -m api.run
```

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness check. Returns `{"ok": true}`. |
| GET | `/profile` | Full `resume.json` dict. |
| GET | `/profile/general_info` | The `general_info` subsection only. |
| GET | `/autofill/fields` | Flat `{key: value}` map of the canonical autofill fields, ready for the content script to consume. |

CORS is restricted to `moz-extension://*` origins (and `null`, which Firefox
sometimes sends from extension contexts). The server binds to `127.0.0.1` only.
