# api/generate_resume/

Pipeline that turns a job posting + the user's base resume into a tailored resume.

| File | Purpose |
|---|---|
| `generator.py` | Top-level orchestrator — runs the full pipeline end to end. |
| `agent_tools.py` | Tool definitions exposed to the LLM agent (bullet rewriting, ranking, etc.). |
| `compile.py` | Assembles the final resume from selected bullets/sections. |
| `render.py` | Renders the compiled resume to its output format. |
| `preview.py` | Compiles a template to PDF with sample data, for the Settings editor. |
| `sample_data.py` | Fictional resume used by `preview.py` — covers every section kind. |
| `persist.py` | Saves generated resumes into the on-disk library. |
| `json_recovery.py` | Salvages malformed JSON from LLM responses. |
