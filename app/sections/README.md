# app/sections/

One subpackage per main-window tab. Multi-page tabs subclass `app.ui.sidebar_stack.SidebarStack`; pages take an `AppContext` rather than individual callbacks.

| Path | Purpose |
|---|---|
| `profile/` | Profile editors (general info, experience, projects, education, awards, skills, hobbies). |
| `applier/` | Resume generation, the drag-and-drop resume builder, company research, the resume library, question answering. |
| `applications/` | Application tracker, "Prep All" batch generation, toolbar heatmap. |
| `interviews/` | Question bank, per-job prep, mock-interview chat, past feedback. |
| `leetcode/` | Spaced-repetition flashcards (review, browse, Anki import). |
| `settings/` | Settings pages (general, AI model, resume, prompts, token usage). |
