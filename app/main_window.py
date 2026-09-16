from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QListWidget,
    QStackedWidget, QStatusBar, QToolBar, QListWidgetItem, QLabel,
    QFileDialog, QMessageBox, QTabWidget, QSizePolicy, QDialog,
)
from PyQt6.QtCore import Qt, QObject, QThread
from PyQt6.QtGui import QAction

from api import data_store, linkedin_import, resume_pdf_import
from .import_review_dialog import ImportReviewDialog
from .resume_pdf_worker import ResumePdfImportWorker
from .theme import current_palette
from .sections.general_info import GeneralInfoPage
from .sections.experience import ExperiencePage
from .sections.projects import ProjectsPage
from .sections.education import EducationPage
from .sections.awards import AwardsPage
from .sections.skills import SkillsPage
from .sections.hobbies import HobbiesPage
from .sections.applications import ApplicationsPage
from .sections.applications.heatmap import ApplicationsHeatmap
from .sections.applier import ApplierPage
from .sections.interviews import InterviewsPage
from .sections.settings import SettingsPage

_SIDEBAR_ITEMS = [
    ("👤  General Info", GeneralInfoPage),
    ("💼  Experience", ExperiencePage),
    ("🚀  Projects", ProjectsPage),
    ("🎓  Education", EducationPage),
    ("🏆  Awards", AwardsPage),
    ("🛠  Skills", SkillsPage),
    ("🎯  Hobbies", HobbiesPage),
]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("I*ternship - Job Application Assistant")

        # ── Toolbar ──────────────────────────────────────────────
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        self.addToolBar(toolbar)

        app_label = QLabel("  I*ternship")
        app_label.setObjectName("app-brand")
        app_label.setStyleSheet("padding: 0 8px;")
        toolbar.addWidget(app_label)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)

        self._heatmap = ApplicationsHeatmap()
        toolbar.addWidget(self._heatmap)

        import_action = QAction("Import from LinkedIn", self)
        import_action.setShortcut("Ctrl+I")
        import_action.triggered.connect(self._import_linkedin)
        toolbar.addAction(import_action)

        self._import_pdf_action = QAction("Import from Resume PDF", self)
        self._import_pdf_action.setShortcut("Ctrl+Shift+I")
        self._import_pdf_action.triggered.connect(self._import_resume_pdf)
        toolbar.addAction(self._import_pdf_action)

        self._import_threads: list[QThread] = []
        self._import_workers: list[QObject] = []

        save_action = QAction("Save", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._save)
        toolbar.addAction(save_action)
        save_btn = toolbar.widgetForAction(save_action)
        if save_btn is not None:
            save_btn.setObjectName("primary")
            style = save_btn.style()
            style.unpolish(save_btn)
            style.polish(save_btn)

        refresh_action = QAction("Refresh", self)
        refresh_action.setShortcut("Ctrl+R")
        refresh_action.triggered.connect(self._refresh_applications)
        toolbar.addAction(refresh_action)

        # ── Status bar ────────────────────────────────────────────
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # ── Tab widget ────────────────────────────────────────────
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self.setCentralWidget(self._tabs)

        # ── Tab 0: Profile (sidebar + stacked pages) ──────────────
        profile_widget = QWidget()
        profile_layout = QHBoxLayout(profile_widget)
        profile_layout.setContentsMargins(0, 0, 0, 0)
        profile_layout.setSpacing(0)

        self._sidebar = QListWidget()
        self._sidebar.setObjectName("sidebar")
        self._sidebar.setFixedWidth(200)

        self._stack = QStackedWidget()

        self._general_info_page = GeneralInfoPage()
        self._experience_page = ExperiencePage()
        self._projects_page = ProjectsPage()
        self._education_page = EducationPage()
        self._awards_page = AwardsPage()
        self._skills_page = SkillsPage()
        self._hobbies_page = HobbiesPage()

        for page in (self._experience_page, self._projects_page, self._education_page, self._awards_page):
            page.on_skill_added = self._register_global_skill
            page.get_common_skills = self._get_global_skills

        pages = [
            self._general_info_page,
            self._experience_page,
            self._projects_page,
            self._education_page,
            self._awards_page,
            self._skills_page,
            self._hobbies_page,
        ]
        for (label, _), page in zip(_SIDEBAR_ITEMS, pages):
            item = QListWidgetItem(label)
            item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            self._sidebar.addItem(item)
            self._stack.addWidget(page)

        self._sidebar.currentRowChanged.connect(self._stack.setCurrentIndex)
        self._sidebar.setCurrentRow(0)

        profile_layout.addWidget(self._sidebar)
        profile_layout.addWidget(self._stack, 1)

        self._tabs.addTab(profile_widget, "💼  Profile")

        # ── Tab 1: Applier ────────────────────────────────────────
        self._applier_page = ApplierPage(
            get_profile=self._get_profile_data,
            save_fn=self._save,
        )
        self._tabs.addTab(self._applier_page, "✦  Applier")

        # ── Tab 2: Applications ───────────────────────────────────
        self._applications_page = ApplicationsPage(
            get_profile=self._get_profile_data,
            get_research_cache=self._applier_page.get_research_data,
            save_fn=self._save,
        )
        self._tabs.addTab(self._applications_page, "📋  Applications")

        # ── Tab 3: Interviews ─────────────────────────────────────
        self._interviews_page = InterviewsPage(
            get_profile=self._get_profile_data,
            get_applications=self._applications_page.get_data,
            get_research_cache=self._applier_page.get_research_data,
            set_application_interviews=self._applications_page.set_interview_questions,
        )
        self._tabs.addTab(self._interviews_page, "🎤  Interviews")

        # ── Tab 4: Settings ───────────────────────────────────────
        self._settings_page = SettingsPage(
            status_bar=self.status_bar,
            on_heatmap_thresholds_changed=self._heatmap.reload_thresholds,
        )
        self._tabs.addTab(self._settings_page, "⚙️  Settings")

        self._load()
        self.resize(1100, 750)

    def _register_global_skill(self, skill: str):
        existing = {s.lower() for s in self._skills_page.get_data()}
        if skill.lower() in existing:
            return
        self._skills_page._add_item(skill)

    def _get_global_skills(self) -> list[str]:
        return self._skills_page.get_data()

    def _get_profile_data(self) -> dict:
        return {
            "general_info": self._general_info_page.get_data(),
            "experience": self._experience_page.get_data(),
            "projects": self._projects_page.get_data(),
            "education": self._education_page.get_data(),
            "awards": self._awards_page.get_data(),
            "skills": self._skills_page.get_data(),
            "hobbies": self._hobbies_page.get_data(),
        }

    def _load(self):
        data = data_store.load()
        self._general_info_page.load(data.get("general_info", {}))
        for entry in data.get("experience", []):
            self._experience_page.add_entry(entry)
        for entry in data.get("projects", []):
            self._projects_page.add_entry(entry)
        for entry in data.get("education", []):
            self._education_page.add_entry(entry)
        for entry in data.get("awards", []):
            self._awards_page.add_entry(entry)
        self._skills_page.load(data.get("skills", []))
        self._hobbies_page.load(data.get("hobbies", []))
        for entry in data.get("applications", []):
            self._applications_page.add_entry(entry)
        self._applier_page.load_research_data(data.get("research_cache") or {})
        self._interviews_page.load_questions(
            data.get("interview_questions") if "interview_questions" in data else None
        )
        self._interviews_page.load_template(data_store.load_interview_template())
        self._refresh_heatmap()
        self._applier_page._refresh_builder_palette()

    def _refresh_heatmap(self):
        try:
            self._heatmap.set_applications(self._applications_page.get_data())
        except Exception:
            pass

    def _show_import_instructions(self) -> bool:
        """Show a how-to dialog. Returns True if user wants to proceed to file picker."""
        box = QMessageBox(self)
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
            "unless you choose <i>Replace all</i> on the next screen.</p>"
        )
        proceed_btn = box.addButton("Choose ZIP…", QMessageBox.ButtonRole.AcceptRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(proceed_btn)
        box.exec()
        return box.clickedButton() is proceed_btn

    def _import_linkedin(self):
        if not self._show_import_instructions():
            return

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

        summary = linkedin_import.summarize(data)
        if not any(
            data[k]
            for k in ("experience", "projects", "education", "awards", "skills", "general_info")
        ):
            QMessageBox.warning(
                self, "Nothing to import",
                "The archive parsed successfully but contained no resume data.\n\n"
                "Make sure your LinkedIn export included Profile, Positions, "
                "Projects, Education, and Skills.",
            )
            return

        existing_general = {
            k: v for k, v in self._general_info_page.get_data().items() if v
        }
        has_existing = bool(
            existing_general
            or self._experience_page.get_data()
            or self._projects_page.get_data()
            or self._education_page.get_data()
            or self._awards_page.get_data()
            or self._skills_page.get_data()
        )

        mode = "replace"
        if has_existing:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Question)
            box.setWindowTitle("Import LinkedIn data")
            box.setText(f"Found: {summary}.\n\nHow should we merge with your existing data?")
            replace_btn = box.addButton("Replace all", QMessageBox.ButtonRole.DestructiveRole)
            append_btn = box.addButton("Append", QMessageBox.ButtonRole.AcceptRole)
            cancel_btn = box.addButton(QMessageBox.StandardButton.Cancel)
            box.setDefaultButton(append_btn)
            box.exec()
            clicked = box.clickedButton()
            if clicked is cancel_btn:
                return
            mode = "replace" if clicked is replace_btn else "append"

        import_category = "relevant"
        if data["experience"]:
            cat_box = QMessageBox(self)
            cat_box.setIcon(QMessageBox.Icon.Question)
            cat_box.setWindowTitle("Categorize imported positions")
            cat_box.setText(
                f"Where should the {len(data['experience'])} imported "
                "position(s) go?"
            )
            relevant_btn = cat_box.addButton(
                "Relevant Experience", QMessageBox.ButtonRole.AcceptRole
            )
            other_btn = cat_box.addButton(
                "Leadership / Other", QMessageBox.ButtonRole.AcceptRole
            )
            cat_box.setDefaultButton(relevant_btn)
            cat_box.exec()
            import_category = "other" if cat_box.clickedButton() is other_btn else "relevant"

        for entry in data["experience"]:
            entry["category"] = import_category
        self._apply_imported_to_widgets(data, mode)

        self.status_bar.showMessage(f"✓  Imported from LinkedIn — {summary}", 5000)

    def _apply_imported_to_widgets(self, data: dict, mode: str) -> None:
        """Push an imported profile dict into the live section widgets.

        Shared by every importer. Nothing is persisted here — the user still
        has to Save (or close the window), same as any hand edit.
        Sections absent from ``data`` are left alone even in replace mode.
        """
        for key, page in (
            ("experience", self._experience_page),
            ("projects", self._projects_page),
            ("education", self._education_page),
            ("awards", self._awards_page),
        ):
            if key not in data:
                continue
            if mode == "replace":
                page.clear()
            for entry in data.get(key) or []:
                page.add_entry(entry)

        for key, page in (
            ("skills", self._skills_page),
            ("hobbies", self._hobbies_page),
        ):
            if key not in data:
                continue
            items = data.get(key) or []
            if mode == "replace":
                page.load(items)
            else:
                # Dedupe case-insensitively, matching profile_merge — the list
                # widgets happily accept the same skill twice.
                existing = {s.lower() for s in page.get_data()}
                for item in items:
                    if item.lower() not in existing:
                        page._add_item(item)
                        existing.add(item.lower())

        imported_general = data.get("general_info") or {}
        if imported_general:
            current_general = self._general_info_page.get_data()
            if mode == "replace":
                merged = {**current_general, **imported_general}
            else:
                merged = dict(current_general)
                for k, v in imported_general.items():
                    if not merged.get(k):
                        merged[k] = v
            self._general_info_page.load(merged)

    def _import_resume_pdf(self):
        if self._import_threads:
            return

        from api import ai_provider
        if not (ai_provider.get_openrouter_api_key() or "").strip():
            QMessageBox.warning(
                self, "API key required",
                "Importing a resume PDF uses the AI to read it.\n\n"
                "Add an OpenRouter API key in Settings → AI Model, then try again.",
            )
            return

        pdf_path, _ = QFileDialog.getOpenFileName(
            self, "Select your resume PDF", "", "PDF files (*.pdf)"
        )
        if not pdf_path:
            return

        self._import_pdf_action.setEnabled(False)
        self.status_bar.showMessage("Reading resume PDF…")

        worker = ResumePdfImportWorker(pdf_path)
        thread = QThread(self)
        worker.moveToThread(thread)

        def on_finished(data: dict):
            # Quit first: the review dialog spins a nested event loop, and the
            # worker thread must not still be alive underneath it.
            thread.quit()
            self._import_pdf_action.setEnabled(True)
            self.status_bar.clearMessage()
            self._review_and_apply_pdf_import(data)

        def on_error(msg: str):
            thread.quit()
            self._import_pdf_action.setEnabled(True)
            self.status_bar.clearMessage()
            QMessageBox.critical(self, "Import failed", msg)

        def on_thread_finished():
            if worker in self._import_workers:
                self._import_workers.remove(worker)
            if thread in self._import_threads:
                self._import_threads.remove(thread)

        worker.progress.connect(self.status_bar.showMessage)
        worker.finished.connect(on_finished)
        worker.error.connect(on_error)
        thread.started.connect(worker.run)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(on_thread_finished)
        self._import_threads.append(thread)
        self._import_workers.append(worker)
        thread.start()

    def _review_and_apply_pdf_import(self, data: dict):
        if resume_pdf_import.is_empty(data):
            QMessageBox.warning(
                self, "Nothing to import",
                "The PDF was read successfully but the AI found no resume "
                "content in it.\n\nDouble-check you picked the right file.",
            )
            return

        dlg = ImportReviewDialog(data, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            self.status_bar.showMessage("Import cancelled.", 3000)
            return

        accepted = dlg.accepted_data()
        if resume_pdf_import.is_empty(accepted):
            self.status_bar.showMessage("Import cancelled — nothing selected.", 3000)
            return

        has_existing = bool(
            {k: v for k, v in self._general_info_page.get_data().items() if v}
            or self._experience_page.get_data()
            or self._projects_page.get_data()
            or self._education_page.get_data()
            or self._awards_page.get_data()
            or self._skills_page.get_data()
            or self._hobbies_page.get_data()
        )

        mode = "replace"
        if has_existing:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Question)
            box.setWindowTitle("Import resume PDF")
            box.setText(
                f"Importing: {resume_pdf_import.summarize(accepted)}.\n\n"
                "How should we merge with your existing data?"
            )
            # "Replace sections", not "Replace all": general_info is overlaid
            # rather than cleared, here and in every other importer.
            replace_btn = box.addButton("Replace sections", QMessageBox.ButtonRole.DestructiveRole)
            append_btn = box.addButton("Append", QMessageBox.ButtonRole.AcceptRole)
            cancel_btn = box.addButton(QMessageBox.StandardButton.Cancel)
            box.setDefaultButton(append_btn)
            box.exec()
            clicked = box.clickedButton()
            if clicked is cancel_btn:
                self.status_bar.showMessage("Import cancelled.", 3000)
                return
            mode = "replace" if clicked is replace_btn else "append"

        self._apply_imported_to_widgets(accepted, mode)
        self.status_bar.showMessage(
            f"✓  Imported from resume PDF — {resume_pdf_import.summarize(accepted)}",
            5000,
        )

    def _refresh_applications(self):
        on_disk = data_store.load().get("applications") or []
        self._applications_page.clear()
        for entry in on_disk:
            self._applications_page.add_entry(entry)
        self.status_bar.showMessage(
            f"✓  Refreshed applications ({len(on_disk)} entries).", 3000
        )
        self._refresh_heatmap()

    def _merged_applications(self) -> list[dict]:
        return self._applications_page.get_data()

    def _save(self):
        self._interviews_page.commit_pending()
        data = {
            "general_info": self._general_info_page.get_data(),
            "experience": self._experience_page.get_data(),
            "projects": self._projects_page.get_data(),
            "education": self._education_page.get_data(),
            "awards": self._awards_page.get_data(),
            "skills": self._skills_page.get_data(),
            "hobbies": self._hobbies_page.get_data(),
            "applications": self._merged_applications(),
            "research_cache": self._applier_page.get_research_data(),
            "interview_questions": self._interviews_page.get_questions_data(),
        }
        data_store.save(data)
        data_store.save_interview_template(self._interviews_page.get_template_data())
        self.status_bar.showMessage("✓  Saved successfully.", 3000)
        self._refresh_heatmap()

    def closeEvent(self, event):
        try:
            self._interviews_page.flush_active_chat()
        except Exception:
            pass
        self._save()
        self._shutdown_all_threads()
        event.accept()

    def _shutdown_all_threads(self):
        from .sections._thread_cleanup import shutdown_threads
        from .sections.base import BulletsWidget
        for page in (
            self._applier_page, self._interviews_page, self._applications_page,
            self._settings_page,
        ):
            try:
                page.cleanup_threads()
            except Exception:
                pass
        for bw in self.findChildren(BulletsWidget):
            try:
                shutdown_threads(bw._threads)
            except Exception:
                pass
        try:
            shutdown_threads(self._import_threads)
        except Exception:
            pass
