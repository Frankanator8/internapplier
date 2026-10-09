# app/sections/applier/

The "Applier" tab — tailor a resume to a job, hand-build one, research the company, and draft answers.

| File | Purpose |
|---|---|
| `page.py` | `ApplierPage` — sidebar container; sub-pages refresh when shown. |
| `generate_resume_page.py` | Runs the [`api/generate_resume/`](../../../api/generate_resume/) pipeline and shows attempts. |
| `resume_builder_page.py` | Drag-and-drop builder with a live PDF preview; widgets live in `builder/`. |
| `builder/` | `model.py` (palette data, MIME payloads), `cards.py`, `palette.py`, `canvas.py`. |
| `research_page.py` | Company research, backed by the shared `ResearchCache`. |
| `library_page.py` | Browse saved resumes; edit and recompile their LaTeX. |
| `answer_question_page.py` | Drafts answers to application short-response questions. |
| `collision.py` | Asks whether to overwrite when a saved resume's name is taken. |
| `workers.py` | Research and resume-generation `Worker`s. |
