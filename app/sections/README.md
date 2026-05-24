# app/sections/

Feature pages mounted into the main window's sidebar. Each top-level `.py` file here is a resume-section editor (education, experience, skills, projects, awards, hobbies, general info) built on `base.py`. The subpackages are larger multi-page features:

| Path | Purpose |
|---|---|
| `base.py` | Shared base widgets/utilities for resume-section editors. |
| `_thread_cleanup.py` | Helper for tearing down worker threads on shutdown. |
| `education.py`, `experience.py`, `skills.py`, `projects.py`, `awards.py`, `hobbies.py`, `general_info.py` | Per-section resume editors. |
| `applier/` | Resume generation, question answering, research, library browsing. |
| `applications/` | Application tracker (heatmap, entries, status). |
| `interviews/` | Interview prep — questions, chat practice, per-job pages, past feedback. |
| `settings/` | Settings pages (AI model, general, prompts, resume, token usage). |
