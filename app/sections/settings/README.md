# app/sections/settings/

Settings pages exposed in the sidebar.

| File | Purpose |
|---|---|
| `page.py` | Settings shell — hosts the sub-pages below. |
| `general_page.py` | Theme, auto-resync, misc app preferences. |
| `ai_model_page.py` | AI provider + model + API key configuration. |
| `prompts_page.py` | View/edit the templates in [`prompts/`](../../../prompts/). |
| `resume_page.py` | Resume import/export and base-resume editing. |
| `token_usage_page.py` | Per-model token + cost usage; backed by `api/token_usage.py`. |
