# app/sections/settings/

Settings pages exposed in the sidebar. Each is a standalone `SettingsPane`.

| File | Purpose |
|---|---|
| `page.py` | `SettingsPage` — sidebar container. |
| `common.py` | `SettingsPane` base and `SettingsCard`. |
| `general_page.py` | Theme, writing sample, scraper paths, heatmap thresholds. |
| `ai_model_page.py` | API key and the three model slots. |
| `resume_page.py` | Generation limits, output folder, LaTeX template with a sample-data preview. |
| `prompts_page.py` | View/edit the templates in [`prompts/`](../../../prompts/). |
| `token_usage_page.py` | Per-tier token usage; backed by `api/token_usage.py`. |
