# InternApplier Localhost API

A small FastAPI server that exposes the saved InternApplier profile (read from
`~/Library/Application Support/InternApplier/resume.json`) over HTTP on
`127.0.0.1:8765`. It is the data source for the Firefox autofill extension in
`../extension/`.

## Install

```
pip install -r requirements.txt
```

(Run from the repo root so `app/` is importable as a sibling of `api/`.)

## Run

```
python -m api.run
```

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness check. Returns `{"ok": true}`. |
| GET | `/profile` | Full `resume.json` dict. |
| GET | `/profile/general_info` | The `general_info` subsection only. |
| GET | `/autofill/fields` | Flat `{key: value}` map of the canonical autofill fields, ready for the content script to consume. |

CORS is restricted to `moz-extension://*` origins (and `null`, which Firefox
sometimes sends from extension contexts). The server binds to `127.0.0.1` only.

## Speech (TTS + STT)

`speech.py` exposes two PyQt6 `QObject` workers backed by macOS built-ins:

- `TextToSpeech` — wraps the `say(1)` command; uses whichever system voice the
  user has selected in System Settings.
- `SpeechToText` — wraps Apple's on-device `SFSpeechRecognizer` +
  `AVAudioEngine` via PyObjC. Fully offline.

The module is macOS-only; on Linux/Windows `is_supported()` returns `False` and
the speak/start methods raise `NotImplementedError`. The pyobjc dependencies in
`requirements.txt` are gated with `sys_platform == "darwin"` markers so install
on other platforms is unaffected.

The first time STT runs, macOS will show two permission prompts — Microphone
and Speech Recognition — attached to whatever process launched Python
(Terminal, iTerm, VS Code, or the bundled `.app`). Approve both to continue.
