# app/

PyQt6 desktop UI. The main window is a sidebar-driven shell that hosts the feature sections in [`sections/`](sections/).

| File | Purpose |
|---|---|
| `main_window.py` | Top-level `QMainWindow` — sidebar nav + stacked section pages. |
| `onboarding.py` | First-run dialog (LinkedIn import, AI key setup, etc.). |
| `theme.py` | Light/dark/system theme switching; macOS appearance listener. |
| `style.py` | Shared Qt stylesheet snippets. |
| `sections/` | One subpackage per feature area (applier, applications, interviews, settings) plus simple per-resume-section editors (education, experience, skills, …). |
