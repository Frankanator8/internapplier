# app/sections/applications/

Application tracker — log internships you've applied to and visualize activity.

| File | Purpose |
|---|---|
| `tracker_page.py` | `TrackerPage` — the tab itself: table of applications with status tracking. |
| `prep_runner.py` | `PrepAllRunner` — generates resumes for every "Added" application, one at a time. |
| `entry_dialog.py` | Add/edit dialog for a single application. |
| `heatmap.py` | Toolbar heatmap of applications per day / week. |

Backed by `api/data_store.py`.
