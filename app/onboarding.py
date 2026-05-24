from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPlainTextEdit, QStackedWidget, QVBoxLayout, QWidget,
)

from api import ai_provider, app_settings, linkedin_import
from api.constants import ONBOARDED_FILE

from .sections.base import _label, _primary_btn, _secondary_btn

logger = logging.getLogger(__name__)

_JAKES_URL = "https://www.overleaf.com/latex/templates/jakes-resume/syzfjbzwjncs"
_EXTENSION_DIR = Path(__file__).resolve().parent.parent / "extension"


class OnboardingDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Welcome to I*ternship")
        self.setModal(True)
        self.resize(720, 600)

        self._finished_cleanly = False
        self._linkedin_status = ""

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(32, 28, 32, 24)
        card_layout.setSpacing(18)

        self._step_label = QLabel("")
        self._step_label.setObjectName("hint")
        card_layout.addWidget(self._step_label)

        self._stack = QStackedWidget()
        card_layout.addWidget(self._stack, stretch=1)

        self._stack.addWidget(self._build_welcome())
        self._stack.addWidget(self._build_api_key())
        self._stack.addWidget(self._build_models())
        self._stack.addWidget(self._build_resume_template())
        self._stack.addWidget(self._build_writing_sample())
        self._stack.addWidget(self._build_linkedin())
        self._stack.addWidget(self._build_extension())
        self._stack.addWidget(self._build_done())

        nav = QHBoxLayout()
        nav.setSpacing(12)
        self._back_btn = _secondary_btn("Back", width=100)
        self._back_btn.clicked.connect(self._go_back)
        self._next_btn = _primary_btn("Next", width=120)
        self._next_btn.clicked.connect(self._go_next)
        nav.addStretch()
        nav.addWidget(self._back_btn)
        nav.addWidget(self._next_btn)
        card_layout.addLayout(nav)

        outer.addWidget(card)

        self._update_nav()

    def closeEvent(self, event):
        # Closing via the X button does NOT mark onboarding complete.
        # Onboarding will reappear on next launch until the user clicks Finish.
        super().closeEvent(event)

    # ── Steps ──────────────────────────────────────────────────────────

    def _build_welcome(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(14)

        title = QLabel("Welcome!")
        title.setObjectName("card-title")
        v.addWidget(title)

        body = QLabel(
            "Let's get you set up. This takes about a minute.\n\n"
            "We'll configure:\n"
            "  • Your OpenRouter API key\n"
            "  • Which AI models to use\n"
            "  • A resume template (LaTeX)\n"
            "  • A writing sample (so generated answers sound like you)\n"
            "  • An optional LinkedIn data import\n"
            "  • The Firefox autofill extension (optional)\n\n"
            "All of this can be edited later in Settings."
        )
        body.setWordWrap(True)
        v.addWidget(body)
        v.addStretch()
        return w

    def _build_api_key(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(12)

        title = QLabel("OpenRouter API key")
        title.setObjectName("card-title")
        v.addWidget(title)

        v.addWidget(_label("OpenRouter API key"))
        self._api_key_edit = QLineEdit()
        self._api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_edit.setPlaceholderText("sk-or-...")
        self._api_key_edit.setText(ai_provider.get_openrouter_api_key())

        key_row = QHBoxLayout()
        key_row.setSpacing(8)
        key_row.addWidget(self._api_key_edit)
        self._api_key_reveal = _primary_btn("Show", width=70)
        self._api_key_reveal.clicked.connect(self._toggle_api_key_visible)
        key_row.addWidget(self._api_key_reveal)
        v.addLayout(key_row)

        hint = QLabel(
            "Stored in ~/Library/Application Support/InternApplier/.env and "
            "loaded into the environment as OPENROUTER_API_KEY. "
            "Get one at https://openrouter.ai/keys."
        )
        hint.setWordWrap(True)
        hint.setObjectName("hint")
        v.addWidget(hint)
        v.addStretch()
        return w

    def _build_models(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(12)

        title = QLabel("AI models")
        title.setObjectName("card-title")
        v.addWidget(title)

        hint = QLabel(
            "Three model slots — defaults are fine to start with. "
            "Edit any time in Settings → AI Model."
        )
        hint.setWordWrap(True)
        hint.setObjectName("hint")
        v.addWidget(hint)

        config = ai_provider._load_model_config()

        def _row(label_text: str, default_val: str, used_for: str) -> tuple[QLineEdit, QVBoxLayout]:
            box = QVBoxLayout()
            box.setSpacing(4)
            box.addWidget(_label(label_text))
            edit = QLineEdit()
            edit.setText(config.get(label_text.split()[0].lower(), default_val))
            edit.setPlaceholderText(default_val)
            box.addWidget(edit)
            sub = QLabel(used_for)
            sub.setObjectName("hint")
            sub.setWordWrap(True)
            box.addWidget(sub)
            return edit, box

        self._basic_edit, basic_box = _row(
            "Basic model", ai_provider.DEFAULT_BASIC_MODEL,
            "Used for: bullet analysis, answering questions, interview chat.",
        )
        self._fast_edit, fast_box = _row(
            "Fast model", ai_provider.DEFAULT_FAST_MODEL,
            "Used for: company research, interview grading, resume grading.",
        )
        self._powerful_edit, powerful_box = _row(
            "Powerful model", ai_provider.DEFAULT_POWERFUL_MODEL,
            "Used for: resume generation (needs function-calling support).",
        )
        v.addLayout(basic_box)
        v.addLayout(fast_box)
        v.addLayout(powerful_box)
        v.addStretch()
        return w

    def _build_resume_template(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(12)

        title = QLabel("Resume template")
        title.setObjectName("card-title")
        v.addWidget(title)

        hint = QLabel(
            "Paste a LaTeX resume template — it's used as the structural base "
            f"for every generated resume. Jake's Resume Template ({_JAKES_URL}) "
            "is a popular default. You can skip this and add it later in "
            "Settings → Resume."
        )
        hint.setWordWrap(True)
        hint.setObjectName("hint")
        v.addWidget(hint)

        mono = QFont("Menlo")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        mono.setPointSize(11)
        self._resume_template_edit = QPlainTextEdit()
        self._resume_template_edit.setFont(mono)
        self._resume_template_edit.setPlaceholderText(
            "\\documentclass[letterpaper,11pt]{article}\n% Paste Jake's Resume Template (or your own) here…"
        )
        self._resume_template_edit.setPlainText(ai_provider.get_resume_template())
        v.addWidget(self._resume_template_edit, stretch=1)
        return w

    def _build_writing_sample(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(12)

        title = QLabel("Writing sample")
        title.setObjectName("card-title")
        v.addWidget(title)

        hint = QLabel(
            "Paste 1–3 paragraphs of your own writing (a cover letter, a blog "
            "post, an essay). The AI uses this to match your voice when "
            "generating answers."
        )
        hint.setWordWrap(True)
        hint.setObjectName("hint")
        v.addWidget(hint)

        self._writing_sample_edit = QPlainTextEdit()
        self._writing_sample_edit.setPlaceholderText(
            "Paste a sample of your own writing here…"
        )
        self._writing_sample_edit.setPlainText(app_settings.get_writing_sample())
        v.addWidget(self._writing_sample_edit, stretch=1)
        return w

    def _build_linkedin(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(12)

        title = QLabel("Import from LinkedIn (optional)")
        title.setObjectName("card-title")
        v.addWidget(title)

        hint = QLabel(
            "Optional. Pre-fills your profile from a LinkedIn data export. "
            "Get the ZIP at LinkedIn → Settings → Data Privacy → "
            "Get a copy of your data → request the Profile, Positions, "
            "Projects, Education, Skills, and Honors files.\n\n"
            "You can also skip this and enter everything by hand in the "
            "Profile tab later."
        )
        hint.setWordWrap(True)
        hint.setObjectName("hint")
        v.addWidget(hint)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        choose_btn = _primary_btn("Choose ZIP…", width=140)
        choose_btn.clicked.connect(self._do_linkedin_import)
        btn_row.addWidget(choose_btn)
        btn_row.addStretch()
        v.addLayout(btn_row)

        self._linkedin_status_label = QLabel("")
        self._linkedin_status_label.setObjectName("hint")
        self._linkedin_status_label.setWordWrap(True)
        v.addWidget(self._linkedin_status_label)

        v.addStretch()
        return w

    def _build_extension(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(12)

        title = QLabel("Install the Firefox extension (optional)")
        title.setObjectName("card-title")
        v.addWidget(title)

        body = QLabel(
            "InternApplier ships a Firefox add-on that autofills job application "
            "forms from your local profile. To load it:\n\n"
            "  1. Open Firefox and go to about:debugging\n"
            "  2. Click \"This Firefox\" in the left sidebar\n"
            "  3. Click \"Load Temporary Add-on…\"\n"
            "  4. Select the manifest.json file inside the extension folder shown below\n\n"
            "Note: temporary add-ons are removed when Firefox restarts — you'll "
            "need to load it again next session. You can skip this and install "
            "later."
        )
        body.setWordWrap(True)
        v.addWidget(body)

        path_label = QLabel(str(_EXTENSION_DIR))
        path_label.setObjectName("hint")
        path_label.setWordWrap(True)
        path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        v.addWidget(path_label)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        reveal_btn = _primary_btn("Reveal extension folder", width=200)
        reveal_btn.clicked.connect(self._reveal_extension_folder)
        btn_row.addWidget(reveal_btn)
        btn_row.addStretch()
        v.addLayout(btn_row)

        v.addStretch()
        return w

    def _build_done(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(14)

        title = QLabel("All set!")
        title.setObjectName("card-title")
        v.addWidget(title)

        self._done_summary = QLabel("")
        self._done_summary.setWordWrap(True)
        v.addWidget(self._done_summary)

        tail = QLabel(
            "You can edit any of these later under the Settings tab. "
            "Click Finish to open the app."
        )
        tail.setWordWrap(True)
        tail.setObjectName("hint")
        v.addWidget(tail)
        v.addStretch()
        return w

    # ── Actions ────────────────────────────────────────────────────────

    def _toggle_api_key_visible(self) -> None:
        if self._api_key_edit.echoMode() == QLineEdit.EchoMode.Password:
            self._api_key_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            self._api_key_reveal.setText("Hide")
        else:
            self._api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self._api_key_reveal.setText("Show")

    def _do_linkedin_import(self) -> None:
        zip_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select your LinkedIn data archive",
            "",
            "ZIP archives (*.zip)",
        )
        if not zip_path:
            return
        try:
            data = linkedin_import.parse_zip(zip_path)
        except Exception as e:
            QMessageBox.critical(
                self, "Import failed",
                f"Could not parse the archive:\n\n{e}\n\n"
                "Make sure this is the ZIP you got from LinkedIn → "
                "Settings → Data Privacy → Get a copy of your data.",
            )
            return

        if not any(
            data.get(k)
            for k in ("experience", "projects", "education", "awards", "skills", "general_info")
        ):
            QMessageBox.warning(
                self, "Nothing to import",
                "The archive parsed successfully but contained no resume data.",
            )
            return

        try:
            linkedin_import.apply_to_store(data, mode="replace")
        except Exception as e:
            logger.exception("LinkedIn import to store failed")
            QMessageBox.critical(self, "Import failed", f"Couldn't write profile data:\n\n{e}")
            return

        summary = linkedin_import.summarize(data)
        self._linkedin_status = summary
        self._linkedin_status_label.setText(f"✓  Imported: {summary}")

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

    def _persist_current_step(self) -> None:
        idx = self._stack.currentIndex()
        if idx == 1:  # api key
            ai_provider.save_openrouter_api_key(self._api_key_edit.text())
        elif idx == 2:  # models
            basic = self._basic_edit.text().strip() or ai_provider.DEFAULT_BASIC_MODEL
            fast = self._fast_edit.text().strip() or ai_provider.DEFAULT_FAST_MODEL
            powerful = self._powerful_edit.text().strip() or ai_provider.DEFAULT_POWERFUL_MODEL
            ai_provider.save_model_config(basic, fast, powerful)
        elif idx == 3:  # resume template
            ai_provider.save_resume_template(self._resume_template_edit.toPlainText())
        elif idx == 4:  # writing sample
            app_settings.save_writing_sample(self._writing_sample_edit.toPlainText())
        # idx 5 (linkedin) writes on its own button click.

    def _populate_summary(self) -> None:
        lines = []
        lines.append("✓  API key saved" if ai_provider.get_openrouter_api_key() else "•  API key skipped (add later in Settings)")
        cfg = ai_provider._load_model_config()
        lines.append(
            f"✓  Models — basic: {cfg.get('basic')}, fast: {cfg.get('fast')}, powerful: {cfg.get('powerful')}"
        )
        lines.append("✓  Resume template saved" if ai_provider.get_resume_template().strip() else "•  Resume template skipped")
        lines.append("✓  Writing sample saved" if app_settings.get_writing_sample().strip() else "•  Writing sample skipped")
        lines.append(f"✓  LinkedIn imported: {self._linkedin_status}" if self._linkedin_status else "•  LinkedIn import skipped")
        self._done_summary.setText("\n".join(lines))

    def _go_next(self) -> None:
        idx = self._stack.currentIndex()
        last = self._stack.count() - 1
        self._persist_current_step()
        if idx == last:
            try:
                ONBOARDED_FILE.parent.mkdir(parents=True, exist_ok=True)
                ONBOARDED_FILE.touch()
            except OSError as e:
                logger.warning("Could not write onboarded marker: %s", e)
            self._finished_cleanly = True
            self.accept()
            return
        self._stack.setCurrentIndex(idx + 1)
        if self._stack.currentIndex() == last:
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
