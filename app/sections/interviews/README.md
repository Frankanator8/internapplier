# app/sections/interviews/

Interview prep — a question bank, per-job prep, mock-interview chats, and past feedback.

| File | Purpose |
|---|---|
| `page.py` | `InterviewsPage` — sidebar container. |
| `questions_page.py` | Question bank with linked questions and AI grading (`QuestionGroupCard`). |
| `job_page.py` | A template plus one question set per tracked application. |
| `chat/` | Mock-interview chat: `page.py`, `camera.py` (local preview), `speech.py` (TTS/STT via `api/speech.py`), `feedback_card.py`, `job_picker.py`. |
| `past_feedback_page.py` | Browse saved chat sessions (`api/interview_sessions.py`). |
| `grading.py` | Shared grading worker and result parsing. |
| `link_picker.py` | Dialog for choosing a question to link with. |
