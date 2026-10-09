"""Profile import flows (LinkedIn export ZIP, resume PDF).

Shared by the main window, which merges into the live profile editors, and
the onboarding wizard, which writes straight to disk. Each caller decides
what to do with the data; this module owns picking, parsing, the AI read
and the review dialog.
"""
from __future__ import annotations

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtWidgets import QDialog, QFileDialog, QMessageBox, QWidget

from api import ai_provider, linkedin_import, resume_pdf_import

from .dialogs.import_review import ImportReviewDialog
from .theme import current_palette
from .ui.workers import Worker, WorkerPool

_LINKEDIN_SECTIONS = ("experience", "projects", "education", "awards", "skills", "general_info")


class ResumePdfImportWorker(Worker):
    """Read a resume PDF, then ask the AI to structure it.

    There is deliberately no cancel: the long leg is a single blocking
    ``requests.post`` with no interrupt, so callers disable their entry points
    for the duration and the pool joins the thread on teardown instead.
    """

    def __init__(self, pdf_path: str):
        super().__init__()
        self._pdf_path = pdf_path

    def work(self) -> dict:
        self.progress.emit("Reading PDF…")
        text = resume_pdf_import.extract_text(self._pdf_path)
        self.progress.emit(f"Extracted {len(text):,} characters — asking AI to structure it…")
        return resume_pdf_import.parse_text(text)

    def error_message(self, exc: Exception) -> str:
        if isinstance(exc, (resume_pdf_import.ResumePdfError, ValueError)):
            return str(exc)  # Both carry messages written for the user.
        return super().error_message(exc)


class ProfileImporter(QObject):
    """Runs the import flows on behalf of ``parent``.

    ``progress`` carries status text ("" when idle); ``busy_changed`` brackets
    the off-thread PDF read; ``pdf_ready`` delivers the reviewed, non-empty
    selection; ``cancelled`` fires when the user backs out of the review.
    """

    progress = pyqtSignal(str)
    busy_changed = pyqtSignal(bool)
    pdf_ready = pyqtSignal(dict)
    cancelled = pyqtSignal()

    def __init__(self, parent: QWidget, missing_key_hint: str):
        super().__init__(parent)
        self._parent = parent
        self._missing_key_hint = missing_key_hint
        self._pool = WorkerPool(self)

    def shutdown(self) -> None:
        self._pool.shutdown()

    # ── LinkedIn ────────────────────────────────────────────────
    def pick_linkedin(self) -> dict | None:
        """Pick and parse a LinkedIn export; None if cancelled, failed or empty."""
        zip_path, _ = QFileDialog.getOpenFileName(
            self._parent, "Select your LinkedIn data archive", "", "ZIP archives (*.zip)",
        )
        if not zip_path:
            return None
        try:
            data = linkedin_import.parse_zip(zip_path)
        except Exception as e:
            QMessageBox.critical(
                self._parent, "Import failed",
                f"Could not parse the archive:\n\n{e}\n\n"
                "Make sure this is the ZIP you got from LinkedIn → "
                "Settings → Data Privacy → Get a copy of your data.",
            )
            return None
        if not any(data.get(k) for k in _LINKEDIN_SECTIONS):
            QMessageBox.warning(
                self._parent, "Nothing to import",
                "The archive parsed successfully but contained no resume data.\n\n"
                "Make sure your LinkedIn export included Profile, Positions, "
                "Projects, Education, and Skills.",
            )
            return None
        return data

    # ── Resume PDF ──────────────────────────────────────────────
    def start_pdf(self) -> None:
        """Pick a PDF and read it off-thread; the review dialog follows."""
        if self._pool.busy:
            return
        if not (ai_provider.get_openrouter_api_key() or "").strip():
            QMessageBox.warning(
                self._parent, "API key required",
                f"Reading a resume PDF uses the AI.\n\n{self._missing_key_hint}",
            )
            return
        pdf_path, _ = QFileDialog.getOpenFileName(
            self._parent, "Select your resume PDF", "", "PDF files (*.pdf)",
        )
        if not pdf_path:
            return

        self.busy_changed.emit(True)
        self._pool.start(
            ResumePdfImportWorker(pdf_path),
            progress=self.progress,
            finished=self._on_pdf_read,
            error=self._on_pdf_error,
        )

    def _on_pdf_error(self, msg: str) -> None:
        self.busy_changed.emit(False)
        self.progress.emit("")
        QMessageBox.critical(self._parent, "Import failed", msg)

    def _on_pdf_read(self, data: dict) -> None:
        self.busy_changed.emit(False)
        self.progress.emit("")
        if resume_pdf_import.is_empty(data):
            QMessageBox.warning(
                self._parent, "Nothing to import",
                "The PDF was read successfully but the AI found no resume "
                "content in it.\n\nDouble-check you picked the right file.",
            )
            return
        dlg = ImportReviewDialog(data, self._parent)
        accepted = dlg.accepted_data() if dlg.exec() == QDialog.DialogCode.Accepted else {}
        if resume_pdf_import.is_empty(accepted):
            self.cancelled.emit()
            return
        self.pdf_ready.emit(accepted)


# ── Prompts used by the main window's merge-into-editors path ───
def confirm_linkedin_instructions(parent: QWidget) -> bool:
    """Explain how to export LinkedIn data. True if the user wants to pick the ZIP."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Information)
    box.setWindowTitle("Import from LinkedIn")
    box.setTextFormat(Qt.TextFormat.RichText)
    box.setText("<b>How to export your LinkedIn data</b>")
    box.setInformativeText(
        "<ol style='margin-left:-20px; line-height:160%;'>"
        "<li>Open <b>LinkedIn</b> in your browser and sign in.</li>"
        "<li>Click your photo → <b>Settings &amp; Privacy</b>.</li>"
        "<li>Go to the <b>Data Privacy</b> tab.</li>"
        "<li>Click <b>Get a copy of your data</b>.</li>"
        "<li>Choose <b>Want something in particular?</b> and tick:<br>"
        "&nbsp;&nbsp;• Positions &nbsp;• Projects &nbsp;• Education &nbsp;• Honors &nbsp;• Skills</li>"
        "<li>Click <b>Request archive</b>. LinkedIn emails you a ZIP "
        "within ~10 minutes.</li>"
        "<li>Download the ZIP, then click <b>Choose ZIP…</b> below to import it.</li>"
        "</ol>"
        f"<p style='color:{current_palette()['text_muted']}; margin-top:8px;'>"
        "Tip: you can re-run this any time. Existing data won't be overwritten "
        "unless you choose <i>Replace sections</i> on the next screen.</p>"
    )
    proceed_btn = box.addButton("Choose ZIP…", QMessageBox.ButtonRole.AcceptRole)
    box.addButton(QMessageBox.StandardButton.Cancel)
    box.setDefaultButton(proceed_btn)
    box.exec()
    return box.clickedButton() is proceed_btn


def ask_merge_mode(parent: QWidget, title: str, summary: str) -> str | None:
    """Ask how to merge into existing data: "replace", "append", or None to cancel."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Question)
    box.setWindowTitle(title)
    box.setText(f"Importing: {summary}.\n\nHow should we merge with your existing data?")
    # "Replace sections", not "Replace all": general_info is overlaid rather
    # than cleared, and sections absent from the import are left alone.
    replace_btn = box.addButton("Replace sections", QMessageBox.ButtonRole.DestructiveRole)
    append_btn = box.addButton("Append", QMessageBox.ButtonRole.AcceptRole)
    cancel_btn = box.addButton(QMessageBox.StandardButton.Cancel)
    box.setDefaultButton(append_btn)
    box.exec()
    clicked = box.clickedButton()
    if clicked is cancel_btn:
        return None
    return "replace" if clicked is replace_btn else "append"


def ask_experience_category(parent: QWidget, count: int) -> str:
    """Ask which experience group imported positions belong to."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Question)
    box.setWindowTitle("Categorize imported positions")
    box.setText(f"Where should the {count} imported position(s) go?")
    relevant_btn = box.addButton("Relevant Experience", QMessageBox.ButtonRole.AcceptRole)
    other_btn = box.addButton("Leadership / Other", QMessageBox.ButtonRole.AcceptRole)
    box.setDefaultButton(relevant_btn)
    box.exec()
    return "other" if box.clickedButton() is other_btn else "relevant"
