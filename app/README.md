# app/

PyQt6 desktop UI. The main window is a sidebar-driven shell that hosts the feature sections in [`sections/`](sections/).

| File | Purpose |
|---|---|
| `main_window.py` | Top-level `QMainWindow` — sidebar nav + stacked section pages. |
| `onboarding.py` | First-run dialog (profile import, AI key setup, etc.). |
| `import_review_dialog.py` | Checkable review of imported profile data before it is applied. |
| `resume_pdf_worker.py` | Off-thread worker: resume-PDF text extraction + AI structuring. |
| `theme.py` | Light/dark/system theme switching; macOS appearance listener. |
| `style.py` | Shared Qt stylesheet snippets. |
| `sections/` | One subpackage per feature area (applier, applications, interviews, settings) plus simple per-resume-section editors (education, experience, skills, …). |
