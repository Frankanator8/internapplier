# api/generate_resume/

Pipeline that turns a job posting + the user's base resume into a tailored resume.

| File | Purpose |
|---|---|
| `generator.py` | Top-level orchestrator — runs the full pipeline end to end. |
| `agent_tools.py` | Tool definitions exposed to the LLM agent (`page_length` compile + fill check). |
| `compile.py` | pdflatex compile + page-fill measurement + plain-text extraction for grading. |
| `preview.py` | Compiles the Settings template editor's LaTeX to PDF as-is; falls back to the bundled default when the editor is empty. |
| `persist.py` | Saves generated resumes into the on-disk library. |
| `json_recovery.py` | Salvages malformed JSON from LLM grader responses. |
