from __future__ import annotations

import logging

from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QMainWindow, QSizePolicy, QStatusBar, QTabWidget, QToolBar, QWidget

from api import data_store, linkedin_import, resume_pdf_import

from .context import AppContext, ResearchCache
from .importers import (
    ProfileImporter, ask_experience_category, ask_merge_mode, confirm_linkedin_instructions,
)
from .sections.applications import TrackerPage
from .sections.applications.heatmap import ApplicationsHeatmap
from .sections.applier import ApplierPage
from .sections.interviews import InterviewsPage
from .sections.leetcode import LeetcodePage
from .sections.profile import ProfilePage
from .sections.settings import SettingsPage
from .ui.widgets import label, repolish
from .ui.workers import WorkerPool

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """App shell: toolbar, tabs, and loading/saving the profile file.

    Tabs share state through one ``AppContext``; this class owns the data
    that is persisted together (profile, applications, research, questions).
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("I*ternship - Job Application Assistant")

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self._heatmap = ApplicationsHeatmap()
        self._importer = ProfileImporter(self, "Add an OpenRouter API key in Settings → AI Model, then try again.")
        self._importer.progress.connect(self._show_progress)
        self._importer.busy_changed.connect(lambda busy: self._import_pdf_action.setEnabled(not busy))
        self._importer.pdf_ready.connect(self._apply_pdf_import)
        self._importer.cancelled.connect(lambda: self.status_bar.showMessage("Import cancelled.", 3000))
        self._build_toolbar()

        self._research = ResearchCache(self)
        ctx = AppContext(
            get_profile=lambda: self._profile.get_data(),
            get_applications=lambda: self._tracker.get_data(),
            set_application_interviews=lambda row, value: self._tracker.set_interview_questions(row, value),
            research=self._research,
            save=self._save,
            status_bar=self.status_bar,
        )

        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        self.setCentralWidget(tabs)
        self._profile = ProfilePage()
        self._tracker = TrackerPage(ctx)
        self._interviews = InterviewsPage(ctx)
        for page, title in (
            (self._tracker, "📋  Applications"),
            (ApplierPage(ctx), "✦  Applier"),
            (self._interviews, "🎤  Interviews"),
            (LeetcodePage(), "🧠  Knowledge"),
            (self._profile, "💼  Profile"),
            (SettingsPage(self.status_bar, self._heatmap.reload_thresholds), "⚙️  Settings"),
        ):
            tabs.addTab(page, title)

        self._load()
        self.resize(1100, 750)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        self.addToolBar(toolbar)
        toolbar.addWidget(label("  I*ternship", "app-brand"))
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)
        toolbar.addWidget(self._heatmap)

        def action(text: str, shortcut: str, slot) -> QAction:
            act = QAction(text, self)
            act.setShortcut(shortcut)
            act.triggered.connect(slot)
            toolbar.addAction(act)
            return act

        action("Import from LinkedIn", "Ctrl+I", self._import_linkedin)
        self._import_pdf_action = action("Import from Resume PDF", "Ctrl+Shift+I", self._importer.start_pdf)
        save_btn = toolbar.widgetForAction(action("Save", "Ctrl+S", self._save))
        if save_btn is not None:
            save_btn.setObjectName("primary")
            repolish(save_btn)
        action("Refresh", "Ctrl+R", self._refresh_applications)

    # ── Persistence ─────────────────────────────────────────────
    def _load(self) -> None:
        data = data_store.load()
        self._profile.load(data)
        self._tracker.load(data.get("applications"))
        self._research.load(data.get("research_cache"))
        self._interviews.load(data.get("interview_questions"), data_store.load_interview_template())
        self._refresh_heatmap()

    def _save(self) -> None:
        self._interviews.commit_pending()
        data_store.save({
            **self._profile.get_data(),
            "applications": self._tracker.get_data(),
            "research_cache": self._research.to_dict(),
            "interview_questions": self._interviews.get_questions_data(),
        })
        data_store.save_interview_template(self._interviews.get_template_data())
        self.status_bar.showMessage("✓  Saved successfully.", 3000)
        self._refresh_heatmap()

    def _refresh_applications(self) -> None:
        """Re-read applications from disk (the browser extension writes there directly)."""
        on_disk = data_store.load().get("applications") or []
        self._tracker.load(on_disk)
        self.status_bar.showMessage(f"✓  Refreshed applications ({len(on_disk)} entries).", 3000)
        self._refresh_heatmap()

    def _refresh_heatmap(self) -> None:
        self._heatmap.set_applications(self._tracker.get_data())

    # ── Importing ───────────────────────────────────────────────
    def _show_progress(self, message: str) -> None:
        if message:
            self.status_bar.showMessage(message)
        else:
            self.status_bar.clearMessage()

    def _merge_mode(self, title: str, summary: str) -> str | None:
        """Replace into an empty profile; otherwise ask (None = cancelled)."""
        return ask_merge_mode(self, title, summary) if self._profile.has_data() else "replace"

    def _import_linkedin(self) -> None:
        if not confirm_linkedin_instructions(self):
            return
        data = self._importer.pick_linkedin()
        if data is None:
            return
        summary = linkedin_import.summarize(data)
        mode = self._merge_mode("Import LinkedIn data", summary)
        if mode is None:
            return
        if data["experience"]:
            category = ask_experience_category(self, len(data["experience"]))
            for entry in data["experience"]:
                entry["category"] = category
        # Nothing is persisted here — the user still saves, as with any edit.
        self._profile.apply_import(data, mode)
        self.status_bar.showMessage(f"✓  Imported from LinkedIn — {summary}", 5000)

    def _apply_pdf_import(self, accepted: dict) -> None:
        summary = resume_pdf_import.summarize(accepted)
        mode = self._merge_mode("Import resume PDF", summary)
        if mode is None:
            self.status_bar.showMessage("Import cancelled.", 3000)
            return
        self._profile.apply_import(accepted, mode)
        self.status_bar.showMessage(f"✓  Imported from resume PDF — {summary}", 5000)

    # ── Shutdown ────────────────────────────────────────────────
    def closeEvent(self, event):  # noqa: N802 (Qt API)
        try:
            self._interviews.flush_active_chat()
        except Exception:
            logger.exception("Saving the active interview chat failed")
        self._save()
        # Join every worker thread before the event loop is torn down.
        for pool in self.findChildren(WorkerPool):
            pool.shutdown()
        event.accept()
