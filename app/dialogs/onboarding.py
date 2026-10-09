from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QLineEdit, QMessageBox, QPlainTextEdit,
    QStackedWidget, QVBoxLayout, QWidget,
)

from api import ai_provider, app_settings, linkedin_import, resume_pdf_import
from api.constants import ONBOARDED_FILE
from app.importers import ProfileImporter
from app.ui.widgets import SecretEdit, button, card, field, hint, label, line_edit, mono_font

logger = logging.getLogger(__name__)

_JAKES_URL = "https://www.overleaf.com/latex/templates/jakes-resume/syzfjbzwjncs"
_EXTENSION_DIR = Path(__file__).resolve().parents[2] / "extension"


def _step(title: str, hint_text: str = "", spacing: int = 12) -> tuple[QWidget, QVBoxLayout]:
    w = QWidget()
    v = QVBoxLayout(w)
    v.setSpacing(spacing)
    v.addWidget(label(title, "card-title"))
    if hint_text:
        v.addWidget(hint(hint_text))
    return w, v


def _body(text: str) -> QWidget:
    return label(text, "", wrap=True)


class OnboardingDialog(QDialog):
    """First-run wizard. Each step saves itself when the user clicks Next."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Welcome to I*ternship")
        self.setModal(True)
        self.resize(720, 600)

        self._import_summary = ""
        self._importer = ProfileImporter(self, "Go back to step 2 and add your OpenRouter API key first.")
        self._importer.progress.connect(lambda msg: self._import_status_label.setText(msg))
        self._importer.busy_changed.connect(self._set_import_busy)
        self._importer.pdf_ready.connect(self._save_pdf_import)
        self._importer.cancelled.connect(lambda: self._import_status_label.setText(""))

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        frame = card()
        card_layout = QVBoxLayout(frame)
        card_layout.setContentsMargins(32, 28, 32, 24)
        card_layout.setSpacing(18)

        self._step_label = label("", "hint")
        card_layout.addWidget(self._step_label)

        # (page builder, persist-on-Next) — the import step saves on its own buttons.
        steps: list[tuple[Callable[[], QWidget], Callable[[], None] | None]] = [
            (self._build_welcome, None),
            (self._build_api_key, lambda: ai_provider.save_openrouter_api_key(self._api_key_edit.text())),
            (self._build_models, self._save_models),
            (self._build_resume_template,
             lambda: ai_provider.save_resume_template(self._resume_template_edit.toPlainText())),
            (self._build_writing_sample,
             lambda: app_settings.save_writing_sample(self._writing_sample_edit.toPlainText())),
            (self._build_import, None),
            (self._build_extension, None),
            (self._build_done, None),
        ]
        self._stack = QStackedWidget()
        self._persist: list[Callable[[], None] | None] = []
        for build, persist in steps:
            self._stack.addWidget(build())
            self._persist.append(persist)
        card_layout.addWidget(self._stack, stretch=1)

        nav = QHBoxLayout()
        nav.setSpacing(12)
        self._back_btn = button("Back", "secondary", 100)
        self._back_btn.clicked.connect(self._go_back)
        self._next_btn = button("Next", width=120)
        self._next_btn.clicked.connect(self._go_next)
        nav.addStretch()
        nav.addWidget(self._back_btn)
        nav.addWidget(self._next_btn)
        card_layout.addLayout(nav)

        outer.addWidget(frame)
        self._update_nav()

    # Closing via the X button does NOT mark onboarding complete; it will
    # reappear on next launch until the user clicks Finish.
    #
    # main.py calls ``OnboardingDialog().exec()`` without keeping a reference,
    # so the dialog is collected the moment exec() returns — and a QThread
    # parented to a destroyed widget crashes. accept() does not deliver a
    # QCloseEvent, so every exit path joins the import thread.
    def closeEvent(self, event):  # noqa: N802 (Qt API)
        self._importer.shutdown()
        super().closeEvent(event)

    def reject(self):
        self._importer.shutdown()
        super().reject()

    def accept(self):
        self._importer.shutdown()
        super().accept()

    # ── Steps ──────────────────────────────────────────────────────────

    def _build_welcome(self) -> QWidget:
        w, v = _step("Welcome!", spacing=14)
        v.addWidget(_body(
            "Let's get you set up. This takes about a minute.\n\n"
            "We'll configure:\n"
            "  • Your OpenRouter API key\n"
            "  • Which AI models to use\n"
            "  • A resume template (LaTeX)\n"
            "  • A writing sample (so generated answers sound like you)\n"
            "  • An optional profile import (resume PDF or LinkedIn export)\n"
            "  • The Firefox autofill extension (optional)\n\n"
            "All of this can be edited later in Settings."
        ))
        v.addStretch()
        return w

    def _build_api_key(self) -> QWidget:
        w, v = _step("OpenRouter API key")
        v.addWidget(label("OpenRouter API key"))
        self._api_key_edit = SecretEdit(ai_provider.get_openrouter_api_key(), "sk-or-...")
        v.addWidget(self._api_key_edit)

        v.addWidget(hint(
            "Stored in ~/Library/Application Support/InternApplier/.env and "
            "loaded into the environment as OPENROUTER_API_KEY. "
            "Get one at https://openrouter.ai/keys."
        ))
        v.addStretch()
        return w

    def _build_models(self) -> QWidget:
        w, v = _step(
            "AI models",
            "Three model slots — defaults are fine to start with. "
            "Edit any time in Settings → AI Model.",
        )
        config = ai_provider.get_model_config()
        self._model_edits: dict[str, QLineEdit] = {}
        for slot, default, used_for in (
            ("basic", ai_provider.DEFAULT_BASIC_MODEL,
             "Used for: bullet analysis, answering questions, interview chat."),
            ("fast", ai_provider.DEFAULT_FAST_MODEL,
             "Used for: company research, interview grading, resume grading."),
            ("powerful", ai_provider.DEFAULT_POWERFUL_MODEL,
             "Used for: resume generation (needs function-calling support)."),
        ):
            edit = self._model_edits[slot] = line_edit(default, config.get(slot, default))
            box = field(f"{slot.capitalize()} model", edit)
            box.setSpacing(4)
            box.addWidget(hint(used_for))
            v.addLayout(box)
        v.addStretch()
        return w

    def _save_models(self) -> None:
        ai_provider.save_model_config(*(
            self._model_edits[slot].text().strip() or default
            for slot, default in (
                ("basic", ai_provider.DEFAULT_BASIC_MODEL),
                ("fast", ai_provider.DEFAULT_FAST_MODEL),
                ("powerful", ai_provider.DEFAULT_POWERFUL_MODEL),
            )
        ))

    def _build_resume_template(self) -> QWidget:
        w, v = _step(
            "Resume template",
            "Paste a LaTeX resume template — it's used as the structural base "
            f"for every generated resume. Jake's Resume Template ({_JAKES_URL}) "
            "is a popular default. You can skip this and add it later in "
            "Settings → Resume.",
        )
        self._resume_template_edit = QPlainTextEdit()
        self._resume_template_edit.setFont(mono_font())
        self._resume_template_edit.setPlaceholderText(
            "\\documentclass[letterpaper,11pt]{article}\n% Paste Jake's Resume Template (or your own) here…"
        )
        self._resume_template_edit.setPlainText(ai_provider.get_resume_template())
        v.addWidget(self._resume_template_edit, stretch=1)
        return w

    def _build_writing_sample(self) -> QWidget:
        w, v = _step(
            "Writing sample",
            "Paste 1–3 paragraphs of your own writing (a cover letter, a blog "
            "post, an essay). The AI uses this to match your voice when "
            "generating answers.",
        )
        self._writing_sample_edit = QPlainTextEdit()
        self._writing_sample_edit.setPlaceholderText("Paste a sample of your own writing here…")
        self._writing_sample_edit.setPlainText(app_settings.get_writing_sample())
        v.addWidget(self._writing_sample_edit, stretch=1)
        return w

    def _build_import(self) -> QWidget:
        w, v = _step(
            "Import your profile (optional)",
            "Two ways to pre-fill your profile — use either, both, or neither.\n\n"
            "Resume PDF: pick an existing resume and the AI reads it into "
            "your profile. You get to review everything it found before it's "
            "saved. Needs the API key from step 2.\n\n"
            "LinkedIn export: get the ZIP at LinkedIn → Settings → Data "
            "Privacy → Get a copy of your data → request the Profile, "
            "Positions, Projects, Education, Skills, and Honors files.\n\n"
            "You can also skip this and enter everything by hand in the "
            "Profile tab later.",
        )
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        self._import_pdf_btn = button("Choose resume PDF…", width=180)
        self._import_pdf_btn.clicked.connect(self._importer.start_pdf)
        btn_row.addWidget(self._import_pdf_btn)
        self._import_zip_btn = button("Choose ZIP…", "secondary", 140)
        self._import_zip_btn.clicked.connect(self._do_linkedin_import)
        btn_row.addWidget(self._import_zip_btn)
        btn_row.addStretch()
        v.addLayout(btn_row)

        self._import_status_label = hint("")
        v.addWidget(self._import_status_label)
        v.addStretch()
        return w

    def _build_extension(self) -> QWidget:
        w, v = _step("Install the Firefox extension (optional)")
        v.addWidget(_body(
            "InternApplier ships a Firefox add-on that autofills job application "
            "forms from your local profile. To load it:\n\n"
            "  1. Open Firefox and go to about:debugging\n"
            "  2. Click \"This Firefox\" in the left sidebar\n"
            "  3. Click \"Load Temporary Add-on…\"\n"
            "  4. Select the manifest.json file inside the extension folder shown below\n\n"
            "Note: temporary add-ons are removed when Firefox restarts — you'll "
            "need to load it again next session. You can skip this and install "
            "later."
        ))
        path_label = hint(str(_EXTENSION_DIR))
        path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        v.addWidget(path_label)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        reveal_btn = button("Reveal extension folder", width=200)
        reveal_btn.clicked.connect(self._reveal_extension_folder)
        btn_row.addWidget(reveal_btn)
        btn_row.addStretch()
        v.addLayout(btn_row)
        v.addStretch()
        return w

    def _build_done(self) -> QWidget:
        w, v = _step("All set!", spacing=14)
        self._done_summary = _body("")
        v.addWidget(self._done_summary)
        v.addWidget(hint(
            "You can edit any of these later under the Settings tab. "
            "Click Finish to open the app."
        ))
        v.addStretch()
        return w

    # ── Actions ────────────────────────────────────────────────────────

    def _set_import_busy(self, busy: bool) -> None:
        for btn in (self._import_pdf_btn, self._import_zip_btn, self._next_btn):
            btn.setEnabled(not busy)

    def _do_linkedin_import(self) -> None:
        data = self._importer.pick_linkedin()
        if data is None:
            return
        # Append, not replace: the user may have already imported a resume PDF
        # on this same step.
        self._save_import(linkedin_import.apply_to_store, data, linkedin_import.summarize(data))

    def _save_pdf_import(self, accepted: dict) -> None:
        self._save_import(resume_pdf_import.apply_to_store, accepted, resume_pdf_import.summarize(accepted))

    def _save_import(self, apply_to_store: Callable[..., None], data: dict, summary: str) -> None:
        try:
            apply_to_store(data, mode="append")
        except Exception as e:
            logger.exception("Profile import to store failed")
            self._import_status_label.setText("")
            QMessageBox.critical(self, "Import failed", f"Couldn't write profile data:\n\n{e}")
            return
        self._import_summary = summary
        self._import_status_label.setText(f"✓  Imported: {summary}")

    def _reveal_extension_folder(self) -> None:
        path = _EXTENSION_DIR
        if not path.exists():
            QMessageBox.warning(
                self, "Folder not found",
                f"Couldn't find the extension folder at:\n\n{path}",
            )
            return
        try:
            subprocess.run(["open", "-R", str(path / "manifest.json")], check=False)
        except OSError as e:
            logger.warning("Failed to reveal extension folder: %s", e)

    def _populate_summary(self) -> None:
        cfg = ai_provider.get_model_config()
        self._done_summary.setText("\n".join([
            "✓  API key saved" if ai_provider.get_openrouter_api_key()
            else "•  API key skipped (add later in Settings)",
            f"✓  Models — basic: {cfg.get('basic')}, fast: {cfg.get('fast')}, powerful: {cfg.get('powerful')}",
            "✓  Resume template saved" if ai_provider.get_resume_template().strip()
            else "•  Resume template skipped",
            "✓  Writing sample saved" if app_settings.get_writing_sample().strip()
            else "•  Writing sample skipped",
            f"✓  Profile imported: {self._import_summary}" if self._import_summary
            else "•  Profile import skipped",
        ]))

    def _go_next(self) -> None:
        idx = self._stack.currentIndex()
        last = self._stack.count() - 1
        persist = self._persist[idx]
        if persist is not None:
            persist()
        if idx == last:
            try:
                ONBOARDED_FILE.parent.mkdir(parents=True, exist_ok=True)
                ONBOARDED_FILE.touch()
            except OSError as e:
                logger.warning("Could not write onboarded marker: %s", e)
            self.accept()
            return
        self._stack.setCurrentIndex(idx + 1)
        if idx + 1 == last:
            self._populate_summary()
        self._update_nav()

    def _go_back(self) -> None:
        idx = self._stack.currentIndex()
        if idx > 0:
            self._stack.setCurrentIndex(idx - 1)
            self._update_nav()

    def _update_nav(self) -> None:
        idx = self._stack.currentIndex()
        last = self._stack.count() - 1
        self._step_label.setText(f"Step {idx + 1} of {last + 1}")
        self._back_btn.setEnabled(idx > 0)
        self._next_btn.setText("Finish" if idx == last else "Next")
