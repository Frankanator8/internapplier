# app/sections/applier/

The "Applier" feature — paste a job link, get a tailored resume, draft answers, and research the company.

| File | Purpose |
|---|---|
| `page.py` | Top-level tabbed container for the applier feature. |
| `generate_resume_page.py` | Resume generation UI — runs the [`api/generate_resume/`](../../../api/generate_resume/) pipeline. |
| `answer_question_page.py` | Drafts answers to application short-response questions. |
| `research_page.py` | Company research view backed by `api/research_cache.py`. |
| `library_page.py` | Browse previously generated resumes. |
| `workers.py` | `QThread` workers that call the AI provider off the UI thread. |
