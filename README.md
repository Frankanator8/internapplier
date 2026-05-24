# InternApplier

An AI-powered, local-first internship application assistant for macOS.

InternApplier is a desktop app for students and early-career applicants who are
running a real internship hunt — dozens of postings, each with their own resume
quirks, their own short-response questions, their own interview loop.
It generates a tailored resume per job, autofills the long boring application
forms from your saved profile, tracks where every application stands, and runs
mock interviews you can speak to out loud. Everything lives on your machine;
the only outbound traffic is to whichever LLM you point it at.

## Why InternApplier?

- **AI-tailored resumes, not template-fill.** Paste a job link and the app
  scrapes the company, ranks your bullets against the JD, and compiles a fresh
  one-page LaTeX PDF for that posting.
- **Firefox autofill extension** that recognises 30+ common application fields
  (name, contact, links, work authorization, EEO questions) and fills them from
  your local profile.
- **End-to-end interview prep** — generated question sets, a graded mock-chat
  mode, and on-device speech recognition so you can practice out loud.
- **Application tracker** with a GitHub-style activity heatmap, status pipeline,
  and links back to the generated resume for each app.
- **100% local data, bring-your-own model.** Profile, applications, interview
  history, and generated PDFs never leave your machine. LLM calls go to
  OpenRouter under your own API key — pick Gemini, GPT-4o, Claude, or anything
  else they front.
- **LinkedIn data-export import** to skip the boring part of profile setup.

## Features

<!-- TODO: screenshots -->

### Profile & resume library

Build your profile once in dedicated editors for general info, education,
experience, projects, skills, awards, and hobbies
([`app/sections/`](app/sections/)). Everything is stored as JSON locally and
re-used by every other feature. The resume layout itself is a LaTeX template
you can edit from inside Settings — swap in your own format, change fonts,
add a sidebar — and every generated resume is rendered through it.

### AI resume generator

The `Applier` section ([`app/sections/applier/`](app/sections/applier/),
[`api/generate_resume/`](api/generate_resume/)) takes a job link and runs a
multi-step pipeline:

- Headless-browser scrape of the company site (Playwright, up to ~5 pages)
  to extract values, recent work, and culture cues — cached per company so
  repeat applications don't re-pay the cost.
- Bullet-level scoring of your existing experience against the JD.
- Resume compilation that picks the strongest bullets, rewrites them for the
  posting, and enforces a configurable page cap (default: 1 page).
- LaTeX → PDF render, saved into your resume library and linked to the
  application record.

Every generated resume stays in a browsable library so you can re-open or
re-send a previous version without regenerating.

### Application question drafter

For "Why this company?" / "Tell us about a time…" short-response prompts, the
Applier can draft an answer that pulls from your profile and your writing
sample (captured during onboarding) so the voice matches yours instead of
sounding like generic LLM prose.

### Firefox autofill extension

[`extension/`](extension/) is a Manifest v2 Firefox extension that, on demand,
walks the current page's form and matches fields to your saved profile by
label / `name` / `id` / `placeholder` / `aria-label`. It handles common
variations ("given name" → first name, "phone number" → phone) and dropdowns
by both value and visible text. It pulls data live from the desktop app's
local API at `127.0.0.1:8765`, so the desktop app must be running for the
extension to work. See [`extension/README.md`](extension/README.md) for the
full field list and loading instructions.

### Application tracker

[`app/sections/applications/`](app/sections/applications/) is a tracker with a
status pipeline (Added → Materials Prepped → Applied → Phone Screen →
Interview → Offer / Rejected), multi-link attachments per application
(posting + recruiter email + take-home, etc.), and a calendar heatmap of
activity over the past year. Heatmap thresholds (what counts as a "light" vs.
"heavy" day) are configurable in Settings.

### Interview prep

[`app/sections/interviews/`](app/sections/interviews/) gives each job its own
interview workspace:

- Generates ~18 tailored practice questions per posting.
- A mock-interview chat mode that grades your answers 0–100 with written
  feedback, kept in a per-job feedback history.
- **macOS speech**: text-to-speech via the system `say(1)` voice (configurable
  voice + rate), and speech-to-text via Apple's on-device
  `SFSpeechRecognizer` + `AVAudioEngine` — no audio is uploaded anywhere.

### Settings & token tracking

[`app/sections/settings/`](app/sections/settings/) covers:

- Per-tier model selection (fast / basic / powerful) — any OpenRouter model.
- OpenRouter API key management.
- LaTeX resume template editing.
- Prompt editing (the LLM prompts in [`prompts/`](prompts/) are all
  user-overridable, with an optional auto-resync on disk changes).
- Light / dark / system theme.
- Per-model token usage and estimated cost.
- Output directory for generated resumes.

## How it works

Three components in one repo:

- [`app/`](app/) — PyQt6 desktop UI (the main window the user interacts with).
- [`api/`](api/) — FastAPI server on `127.0.0.1:8765`, plus the AI provider
  layer, resume generation pipeline, and shared data stores.
- [`extension/`](extension/) — Firefox extension that reads from the local
  API.

`main.py` boots the API server in a background thread and then launches the Qt
app. The extension only works while the desktop app is running, because it
talks to the local API.

## Privacy

All your data lives under `~/Library/Application Support/InternApplier/`:

| File | What's in it |
|---|---|
| `resume.json` | Profile, experience, projects, applications, company research cache. |
| `interview_template.json` | Practice question set + your saved answers. |
| `interview_feedback.json` | Past mock-interview grades and feedback. |
| `settings.json` | Model picks, theme, heatmap thresholds, output dir. |
| `.env` | OpenRouter API key. |
| `token_usage.json` | Per-model token counts and estimated cost. |
| `app.log` | Debug log. |

The only outbound network traffic is:

1. LLM calls to OpenRouter (under your own API key, to the model *you* picked).
2. Playwright fetches of the public company site during resume generation.

No analytics, no telemetry, no cloud sync, no account, no server-side copy of
your resume.

## Requirements

- **macOS.** The data path and the speech features are macOS-specific; speech
  raises `NotImplementedError` on other platforms, and the rest is untested
  there.
- **Python 3.13.**
- **Firefox** — only if you want the autofill extension; the desktop app works
  on its own.
- **An OpenRouter API key.** OpenRouter's free-tier Gemini models work out of
  the box, so you can start without a paid plan.
- A working **LaTeX** install (e.g. MacTeX / BasicTeX) for PDF rendering.

## Install & run

```
git clone <this repo>
cd internapplier
pip install -r requirements.txt
playwright install chromium   # used for company-page scraping
python main.py
```

For a bundled `.app` install (instead of running from source), see
[`install.py`](install.py) — and [`uninstall.py`](uninstall.py) to remove it.

## First launch

On first launch you'll go through an onboarding wizard
([`app/onboarding.py`](app/onboarding.py)):

1. Welcome.
2. Drop in your OpenRouter API key.
3. Pick the models you want for the fast / basic / powerful tiers.
4. Pick or paste a LaTeX resume template.
5. Paste a writing sample so generated answers sound like you.
6. (Optional) Import your LinkedIn data export ZIP — parses the CSVs into
   your profile so you don't have to retype everything.
7. Instructions for loading the Firefox extension.

After this the wizard won't show again.

## Loading the Firefox extension

1. In Firefox, open `about:debugging` → "This Firefox".
2. "Load Temporary Add-on…".
3. Pick [`extension/manifest.json`](extension/manifest.json).

The extension stays loaded until Firefox restarts. Full notes in
[`extension/README.md`](extension/README.md).

## Repository layout

| Path | Purpose |
|---|---|
| [`main.py`](main.py) | Entry point — starts the API server + Qt app. |
| [`install.py`](install.py) / [`uninstall.py`](uninstall.py) | Bundle/install helpers for the macOS `.app`. |
| [`app/`](app/) | Qt desktop UI. |
| [`api/`](api/) | Local FastAPI server, data layer, AI pipeline. |
| [`extension/`](extension/) | Firefox autofill extension. |
| [`prompts/`](prompts/) | LLM prompt templates and JSON schemas. |
| [`tests/`](tests/) | Pytest suite (mirrors `api/`). |
| `test_page/` | Static HTML page for manually testing the extension. |

Each top-level sub-directory has its own README with the developer-facing
details.

## Tech stack

- **PyQt6** desktop UI.
- **FastAPI** + **Uvicorn** for the local API.
- **OpenRouter** as the LLM gateway (Gemini, GPT-4o, Claude, etc.).
- **Playwright** for company-site scraping.
- **Jinja2** + a LaTeX toolchain for resume rendering.
- **pypdf** for PDF post-processing.
- **pyobjc** (Speech + AVFoundation) for native macOS speech.
- **pytest** for the test suite.

## Status & caveats

InternApplier is single-user, local-only, and macOS-only today. The autofill
extension is Firefox-only (Manifest v2). There's no auto-update mechanism —
`git pull` and re-run. Contributions and bug reports are welcome; the
sub-package READMEs are the right starting point for anyone digging into the
internals.
