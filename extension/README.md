# InternApplier Firefox Extension

A Firefox WebExtension that autofills job-application forms using the saved
InternApplier profile. Data is served by the small FastAPI server in
[`../api/`](../api/) — the extension itself never touches the JSON file
directly.

## Scope (v0.1)

- **Static field autofill only.** Maps the canonical `general_info` fields
  (name, contact info, work authorization, EEO answers, etc.) to detected
  form inputs.
- No AI-generated free-text answers.
- No resume PDF upload.

## Prerequisites

The localhost API must be running:

```
pip install -r ../requirements.txt
python -m api.run            # from the repo root
```

The server listens on `http://127.0.0.1:8765`.

## Load in Firefox

1. Open `about:debugging#/runtime/this-firefox`.
2. Click **Load Temporary Add-on…**.
3. Select `extension/manifest.json`.

The extension's toolbar icon opens a popup with:
- A green/red dot showing whether the API is reachable.
- The currently loaded profile name.
- An **Autofill this page** button.

The extension also auto-fills on page load when the API is reachable.

## How field matching works

`content.js` walks every `<input>`, `<select>`, and `<textarea>` on the page,
builds a normalized label from `<label>`, `name`, `id`, `placeholder`, and
`aria-label`, then matches against a small regex alias table. First match wins.
Inputs that already have a value are left alone. For `<select>`, the option is
matched by value, then by visible text, then by fuzzy contains.

To add a new mapping, edit the `ALIASES` list at the top of `content.js`.

## Future work

- AI-generated answers for free-text application questions (would wrap
  `ai_provider`).
- Resume PDF upload into file inputs (would wrap `ResumeGenerator`).
- Chrome/Edge port (convert manifest to v3).
- Profile editing from the extension (write endpoints on the API).
