# extension/

Firefox extension (manifest v2) that autofills job application forms using the local InternApplier profile. Pulls field values from the FastAPI server at `http://127.0.0.1:8765` (see [`../api/`](../api/)) — the desktop app must be running.

| File | Purpose |
|---|---|
| `manifest.json` | Extension manifest. Grants `activeTab`, `storage`, and host access to `127.0.0.1:8765`. |
| `background.js` | Background script — talks to the local API, caches the profile. |
| `content.js` | Content script injected into all pages — detects form fields and fills them. |
| `popup.html` / `popup.js` | Browser action + sidebar UI for triggering autofill and viewing status. |
| `icons/` | Toolbar/sidebar icons (48px, 96px). |

## Load in Firefox

1. Make sure `python main.py` is running so the API is up on `127.0.0.1:8765`.
2. Open `about:debugging` → "This Firefox" → "Load Temporary Add-on…".
3. Pick `extension/manifest.json`.
