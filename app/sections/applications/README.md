# app/sections/applications/

Application tracker — log internships you've applied to and visualize activity.

| File | Purpose |
|---|---|
| `page.py` | Container that hosts the tracker and heatmap. |
| `tracker_page.py` | List/table of application entries with status tracking. |
| `entry_dialog.py` | Add/edit dialog for a single application. |
| `heatmap.py` | Calendar-style heatmap of applications-per-day. |

Backed by `api/data_store.py` (UUID-keyed application records).
