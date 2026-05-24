# tests/

Pytest suite. Mirrors the structure of [`api/`](../api/) — each test module corresponds to a module under `api/`.

| Path | Covers |
|---|---|
| `conftest.py` | Shared fixtures (tmp data dirs, fake HTTP, etc.). |
| `api/` | Tests for the `api/` package. |

## Run

```
pytest
```

Config lives in `pytest.ini` at the repo root.
