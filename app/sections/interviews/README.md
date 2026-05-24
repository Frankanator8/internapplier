# app/sections/interviews/

Interview prep — generate practice questions, run mock-interview chats, and review past feedback.

| File | Purpose |
|---|---|
| `page.py` | Top-level container — picks the active job and dispatches to the subpages. |
| `job_page.py` | Per-job interview workspace. |
| `questions_page.py` | Generated practice questions for the job. |
| `chat_page.py` | Mock-interview chat UI; uses TTS/STT from `api/speech.py` when available. |
| `past_feedback_page.py` | Browse and review grades from past mock interviews. |
| `workers.py` | Background `QThread` workers for AI calls. |
