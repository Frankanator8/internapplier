from __future__ import annotations

import logging
from typing import Callable

from PyQt6.QtCore import QObject, QThread, Qt, pyqtSignal
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QScrollArea, QSizePolicy, QSplitter, QStackedWidget, QTextEdit, QVBoxLayout,
    QWidget,
)

from .base import _label, _primary_btn, _secondary_btn

logger = logging.getLogger(__name__)


class _TailorWorker(QObject):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, profile: dict, jd: str):
        super().__init__()
        self._profile = profile
        self._jd = jd

    def run(self):
        from app.ai_provider import get_provider
        logger.info("_TailorWorker.run — jd=%r", self._jd[:80])
        try:
            metadata: list[tuple[str, str, str]] = []
            bullets: list[str] = []
            for section_key, entry_name_key in (
                ("experience", "company"),
                ("projects", "name"),
                ("education", "school"),
            ):
                for entry in self._profile.get(section_key, []):
                    entry_name = entry.get(entry_name_key, "")
                    for bullet in entry.get("bullets", []):
                        metadata.append((section_key, entry_name, bullet))
                        bullets.append(bullet)

            self.progress.emit(f"Sending {len(bullets)} bullets to AI…")
            tailored = get_provider().tailor_resume(bullets, self._jd)
            result = [
                {"section": sec, "entry": entry, "original": orig, "tailored": new}
                for (sec, entry, orig), new in zip(metadata, tailored)
            ]
            logger.info("_TailorWorker.run — success, %d items", len(result))
            self.finished.emit(result)
        except Exception as exc:
            logger.exception("_TailorWorker.run — failed")
            self.error.emit(str(exc))


class _ResearchWorker(QObject):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, company_name: str, url: str):
        super().__init__()
        self._company_name = company_name
        self._url = url

    def run(self):
        from app.ai_provider import get_provider
        from app.web_scraper import SiteBlockedError, fetch_company_pages
        logger.info("_ResearchWorker.run — company=%r url=%r", self._company_name, self._url)
        try:
            self.progress.emit(f"Fetching pages from {self._url}…")
            text = fetch_company_pages(self._url)
            logger.debug("_ResearchWorker.run — scraped %d chars", len(text))
            self.progress.emit(f"Scraped {len(text):,} chars — asking AI to analyze…")
            result = get_provider().research_company(self._company_name, text)
            logger.info("_ResearchWorker.run — success")
            self.finished.emit(result)
        except SiteBlockedError:
            logger.exception("_ResearchWorker.run — site blocked")
            self.error.emit(
                "This site appears to block automated tools — try a different URL "
                "or scrape manually."
            )
        except Exception as exc:
            logger.exception("_ResearchWorker.run — failed")
            self.error.emit(str(exc))


def _research_from_cache(cache: dict, company: str) -> dict | None:
    if not company or not cache:
        return None
    entry = cache.get(company)
    if entry is None:
        for k, v in cache.items():
            if k.lower() == company.lower():
                entry = v
                break
    if entry is None:
        return None
    if isinstance(entry, dict) and "result" in entry and isinstance(entry["result"], dict):
        return entry["result"]
    if isinstance(entry, dict) and {"summary", "core_values", "recent_projects"} & entry.keys():
        return entry
    return None


class _GenerateResumeWorker(QObject):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, profile: dict, jd: str, company_name: str, url: str, research_cache: dict):
        super().__init__()
        self._profile = profile
        self._jd = jd
        self._company = company_name
        self._url = url
        self._cache = research_cache or {}

    def run(self):
        from app.ai_provider import get_provider
        from app.generate_resume import ResumeGenerator
        logger.info("_GenerateResumeWorker.run — company=%r jd=%r", self._company, self._jd[:80])
        try:
            new_research = False
            research = _research_from_cache(self._cache, self._company)
            if research is not None:
                self.progress.emit(f"Using cached research for {self._company!r}…")
            elif self._company and self._url:
                from app.web_scraper import fetch_company_pages
                self.progress.emit(f"Scraping {self._url}…")
                text = fetch_company_pages(self._url)
                self.progress.emit(f"Scraped {len(text):,} chars — analyzing…")
                research = get_provider().research_company(self._company, text)
                new_research = True
            else:
                research = {
                    "summary": f"{self._company or 'the target company'} is the target company.",
                    "core_values": [],
                    "recent_projects": [],
                }

            gen = ResumeGenerator(self._profile, self._jd, research)

            self.progress.emit("Selecting courses…")
            courses = gen.select_courses(10)

            self.progress.emit("Scoring entries…")
            scored = gen.score_entries()

            logger.info(
                "_GenerateResumeWorker.run — success, courses=%d sections=%s",
                len(courses), {k: len(v) for k, v in scored.items()},
            )
            self.finished.emit({
                "research": research,
                "courses": courses,
                "scored": scored,
                "new_research": new_research,
            })
        except Exception as exc:
            logger.exception("_GenerateResumeWorker.run — failed")
            self.error.emit(str(exc))


class ApplierPage(QWidget):
    def __init__(
        self,
        get_profile: Callable[[], dict],
        save_fn: Callable[[], None] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._get_profile = get_profile
        self._save_fn = save_fn
        self._threads: list[QThread] = []
        self._workers: list[QObject] = []
        self._research_last_result: dict = {}
        self._research_cache: dict[str, dict] = {}

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._applier_sidebar = QListWidget()
        self._applier_sidebar.setObjectName("sidebar")
        self._applier_sidebar.setFixedWidth(200)

        for label in ("✦  Tailor Resume", "📄  Generate Resume", "🔍  Research Company"):
            item = QListWidgetItem(label)
            item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            self._applier_sidebar.addItem(item)

        self._applier_stack = QStackedWidget()
        self._applier_stack.addWidget(self._build_tailor_page())
        self._applier_stack.addWidget(self._build_generate_resume_page())
        self._applier_stack.addWidget(self._build_research_page())

        self._applier_sidebar.currentRowChanged.connect(self._applier_stack.setCurrentIndex)
        self._applier_sidebar.setCurrentRow(0)

        outer.addWidget(self._applier_sidebar)
        outer.addWidget(self._applier_stack, 1)

    def _wrap_page(self, title: str, content: QWidget) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 16)
        layout.setSpacing(14)
        layout.addWidget(_label(title, "section-title"))
        layout.addWidget(content, 1)
        return page

    def _build_tailor_page(self) -> QWidget:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # ── Left panel ───────────────────────────────────────────
        left = QWidget()
        left.setMinimumWidth(280)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        left_layout.addWidget(_label("Job Description"))

        self._jd_input = QTextEdit()
        self._jd_input.setObjectName("jd-input")
        self._jd_input.setPlaceholderText("Paste the job description here…")
        left_layout.addWidget(self._jd_input, 1)

        self._tailor_btn = _primary_btn("✦  Tailor My Resume")
        self._tailor_btn.clicked.connect(self._tailor)
        left_layout.addWidget(self._tailor_btn)

        self._tailor_status = QLabel("")
        self._tailor_status.setWordWrap(True)
        self._tailor_status.setStyleSheet("color: #555; font-size: 12px;")
        left_layout.addWidget(self._tailor_status)

        splitter.addWidget(left)

        # ── Right panel ──────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._results_content = QWidget()
        self._results_content.setStyleSheet("background: transparent;")
        self._results_layout = QVBoxLayout(self._results_content)
        self._results_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._results_layout.setSpacing(10)
        self._results_layout.setContentsMargins(12, 0, 4, 16)
        scroll.setWidget(self._results_content)

        splitter.addWidget(scroll)
        splitter.setSizes([400, 560])

        return self._wrap_page("Tailor Resume", splitter)

    def _build_generate_resume_page(self) -> QWidget:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # ── Left: inputs ─────────────────────────────────────────
        left = QWidget()
        left.setMinimumWidth(320)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 8, 0, 0)
        left_layout.setSpacing(10)

        form_row = QHBoxLayout()
        form_row.setSpacing(8)

        name_col = QVBoxLayout()
        name_col.setSpacing(4)
        name_col.addWidget(_label("Company Name *"))
        self._gen_name_input = QLineEdit()
        self._gen_name_input.setPlaceholderText("e.g. Anthropic")
        name_col.addWidget(self._gen_name_input)
        form_row.addLayout(name_col, 1)

        url_col = QVBoxLayout()
        url_col.setSpacing(4)
        url_col.addWidget(_label("Website (optional)"))
        self._gen_url_input = QLineEdit()
        self._gen_url_input.setPlaceholderText("https://www.example.com")
        url_col.addWidget(self._gen_url_input)
        form_row.addLayout(url_col, 2)

        left_layout.addLayout(form_row)

        left_layout.addWidget(_label("Job Description"))
        self._gen_jd_input = QTextEdit()
        self._gen_jd_input.setPlaceholderText("Paste the job description here…")
        left_layout.addWidget(self._gen_jd_input, 1)

        self._gen_btn = _primary_btn("📄  Generate Resume")
        self._gen_btn.clicked.connect(self._generate_resume)
        left_layout.addWidget(self._gen_btn)

        self._gen_status = QLabel("")
        self._gen_status.setWordWrap(True)
        self._gen_status.setStyleSheet("color: #555; font-size: 12px;")
        left_layout.addWidget(self._gen_status)

        splitter.addWidget(left)

        # ── Right: results ───────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._gen_results_content = QWidget()
        self._gen_results_content.setStyleSheet("background: transparent;")
        self._gen_results_layout = QVBoxLayout(self._gen_results_content)
        self._gen_results_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._gen_results_layout.setSpacing(10)
        self._gen_results_layout.setContentsMargins(12, 0, 4, 16)
        scroll.setWidget(self._gen_results_content)

        splitter.addWidget(scroll)
        splitter.setSizes([400, 560])

        return self._wrap_page("Generate Resume", splitter)

    def _build_research_page(self) -> QWidget:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # ── Left: saved companies list ────────────────────────────
        left = QWidget()
        left.setMinimumWidth(160)
        left.setMaximumWidth(240)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 8, 8, 0)
        left_layout.setSpacing(6)

        left_layout.addWidget(_label("Saved Companies"))

        self._company_list = QListWidget()
        self._company_list.setObjectName("company-cache-list")
        self._company_list.itemClicked.connect(self._load_cached_company)
        left_layout.addWidget(self._company_list, 1)

        self._delete_company_btn = _secondary_btn("Delete", 100)
        self._delete_company_btn.clicked.connect(self._delete_cached_company)
        left_layout.addWidget(self._delete_company_btn)

        splitter.addWidget(left)

        # ── Right: research form + results ────────────────────────
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 8, 0, 0)
        right_layout.setSpacing(10)

        form_row = QHBoxLayout()
        form_row.setSpacing(8)

        name_col = QVBoxLayout()
        name_col.setSpacing(4)
        name_col.addWidget(_label("Company Name"))
        self._research_name_input = QLineEdit()
        self._research_name_input.setPlaceholderText("e.g. Anthropic")
        name_col.addWidget(self._research_name_input)
        form_row.addLayout(name_col, 1)

        url_col = QVBoxLayout()
        url_col.setSpacing(4)
        url_col.addWidget(_label("Website URL"))
        self._research_url_input = QLineEdit()
        self._research_url_input.setPlaceholderText("https://www.example.com")
        url_col.addWidget(self._research_url_input)
        form_row.addLayout(url_col, 2)

        right_layout.addLayout(form_row)

        self._research_btn = _primary_btn("🔍  Research Company")
        self._research_btn.clicked.connect(self._research)
        right_layout.addWidget(self._research_btn)

        self._research_status = QLabel("")
        self._research_status.setWordWrap(True)
        self._research_status.setStyleSheet("color: #555; font-size: 12px;")
        right_layout.addWidget(self._research_status)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._research_results_content = QWidget()
        self._research_results_content.setStyleSheet("background: transparent;")
        self._research_results_layout = QVBoxLayout(self._research_results_content)
        self._research_results_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._research_results_layout.setSpacing(10)
        self._research_results_layout.setContentsMargins(4, 0, 4, 16)
        scroll.setWidget(self._research_results_content)
        right_layout.addWidget(scroll, 1)

        splitter.addWidget(right)
        splitter.setSizes([200, 600])

        return self._wrap_page("Research Company", splitter)

    def _research(self):
        name = self._research_name_input.text().strip()
        url = self._research_url_input.text().strip()
        if not name or not url:
            self._research_status.setText("Enter both a company name and a website URL.")
            self._research_status.setStyleSheet("color: #cc3300; font-size: 12px;")
            return

        self._clear_research_results()
        self._research_btn.setEnabled(False)
        self._research_btn.setText("Researching…")
        self._research_status.setStyleSheet("color: #555; font-size: 12px;")
        self._research_status.setText("Starting…")

        worker = _ResearchWorker(name, url)
        thread = QThread(self)
        worker.moveToThread(thread)

        def on_finished(result: dict):
            self._research_btn.setEnabled(True)
            self._research_btn.setText("🔍  Research Company")
            self._research_status.setText("")
            self._research_last_result = result
            self._research_cache[name] = {"url": url, "result": result}
            self._refresh_company_list(select=name)
            self._populate_research_results(result)
            if self._save_fn:
                self._save_fn()
            thread.quit()

        def on_error(msg: str):
            self._research_btn.setEnabled(True)
            self._research_btn.setText("🔍  Research Company")
            self._research_status.setStyleSheet("color: #cc3300; font-size: 12px;")
            self._research_status.setText(f"Error: {msg}")
            thread.quit()

        def on_research_progress(msg: str):
            self._research_status.setStyleSheet("color: #555; font-size: 12px;")
            self._research_status.setText(msg)

        worker.finished.connect(on_finished)
        worker.error.connect(on_error)
        worker.progress.connect(on_research_progress)
        thread.started.connect(worker.run)
        thread.finished.connect(thread.deleteLater)
        self._threads.append(thread)
        self._workers.append(worker)
        thread.finished.connect(lambda: self._workers.remove(worker) if worker in self._workers else None)
        thread.start()

    def _populate_research_results(self, result: dict):
        self._render_research_block(self._research_results_layout, result)

    def _render_research_block(self, layout: QVBoxLayout, result: dict):
        summary = (result.get("summary") or "").strip()
        values = result.get("core_values") or []
        projects = result.get("recent_projects") or []

        if not summary and not values and not projects:
            empty = QLabel("No information could be extracted from the site.")
            empty.setStyleSheet("color: #777; font-size: 13px;")
            layout.addWidget(empty)
            return

        if summary:
            layout.addWidget(self._research_section_header("SUMMARY"))
            layout.addWidget(self._research_text_row(summary))

        if values:
            layout.addWidget(self._research_section_header("CORE VALUES"))
            for v in values:
                layout.addWidget(self._research_text_row(f"• {v}"))

        if projects:
            layout.addWidget(self._research_section_header("RECENT PROJECTS / NEWS"))
            for p in projects:
                layout.addWidget(self._research_text_row(f"• {p}"))

    def _research_section_header(self, text: str) -> QLabel:
        header = QLabel(text)
        header.setObjectName("applier-section-header")
        return header

    def _research_text_row(self, text: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("result-bullet-row")
        row_layout = QVBoxLayout(frame)
        row_layout.setContentsMargins(12, 10, 12, 10)
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("color: #1d1d1d; font-size: 13px;")
        row_layout.addWidget(lbl)
        return frame

    def _clear_research_results(self):
        while self._research_results_layout.count():
            item = self._research_results_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def get_research_data(self) -> dict:
        """Return the full cache dict: {company_name: {url, result}}."""
        return self._research_cache

    def load_research_data(self, cache: dict):
        """Load a full cache dict and populate the company list."""
        if not cache:
            return
        self._research_cache = cache
        self._refresh_company_list()

    def _refresh_company_list(self, select: str | None = None):
        self._company_list.clear()
        for name in sorted(self._research_cache.keys(), key=str.lower):
            self._company_list.addItem(name)
        if select:
            items = self._company_list.findItems(select, Qt.MatchFlag.MatchExactly)
            if items:
                self._company_list.setCurrentItem(items[0])

    def _load_cached_company(self, item: QListWidgetItem):
        name = item.text()
        entry = self._research_cache.get(name)
        if not entry:
            return
        self._research_name_input.setText(name)
        self._research_url_input.setText(entry.get("url", ""))
        result = entry.get("result") or {}
        self._research_last_result = result
        self._clear_research_results()
        if result:
            self._populate_research_results(result)

    def _delete_cached_company(self):
        item = self._company_list.currentItem()
        if not item:
            return
        name = item.text()
        self._research_cache.pop(name, None)
        self._refresh_company_list()
        self._clear_research_results()
        self._research_name_input.clear()
        self._research_url_input.clear()
        self._research_last_result = {}
        if self._save_fn:
            self._save_fn()

    def _tailor(self):
        jd = self._jd_input.toPlainText().strip()
        if not jd:
            return

        profile = self._get_profile()
        self._tailor_btn.setEnabled(False)
        self._tailor_btn.setText("Tailoring…")
        self._tailor_status.setStyleSheet("color: #555; font-size: 12px;")
        self._tailor_status.setText("")
        self._clear_results()

        worker = _TailorWorker(profile, jd)
        thread = QThread(self)
        worker.moveToThread(thread)

        def on_finished(items: list):
            self._tailor_btn.setEnabled(True)
            self._tailor_btn.setText("✦  Tailor My Resume")
            self._tailor_status.setText("")
            self._populate_results(items)
            thread.quit()

        def on_error(msg: str):
            self._tailor_btn.setEnabled(True)
            self._tailor_btn.setText("✦  Tailor My Resume")
            self._tailor_status.setStyleSheet("color: #cc3300; font-size: 12px;")
            self._tailor_status.setText(f"Error: {msg}")
            err_label = QLabel(f"Error: {msg}")
            err_label.setWordWrap(True)
            err_label.setStyleSheet("color: #cc3300; font-size: 13px;")
            self._results_layout.addWidget(err_label)
            thread.quit()

        worker.finished.connect(on_finished)
        worker.error.connect(on_error)
        worker.progress.connect(lambda msg: self._tailor_status.setText(msg))
        thread.started.connect(worker.run)
        thread.finished.connect(thread.deleteLater)
        self._threads.append(thread)
        self._workers.append(worker)
        thread.finished.connect(lambda: self._workers.remove(worker) if worker in self._workers else None)
        thread.start()

    def _populate_results(self, items: list[dict]):
        if not items:
            empty = QLabel("No bullets found in your profile to tailor.")
            empty.setStyleSheet("color: #777; font-size: 13px;")
            self._results_layout.addWidget(empty)
            return

        grouped: dict[str, list[dict]] = {
            "experience": [], "projects": [], "education": []
        }
        for item in items:
            sec = item.get("section", "")
            if sec in grouped:
                grouped[sec].append(item)

        section_names = {
            "experience": "Experience",
            "projects": "Projects",
            "education": "Education",
        }

        for key in ("experience", "projects", "education"):
            section_items = grouped[key]
            if not section_items:
                continue

            header = QLabel(section_names[key].upper())
            header.setObjectName("applier-section-header")
            self._results_layout.addWidget(header)

            for item in section_items:
                row_frame = QFrame()
                row_frame.setObjectName("result-bullet-row")
                row_layout = QVBoxLayout(row_frame)
                row_layout.setContentsMargins(12, 10, 12, 10)
                row_layout.setSpacing(6)

                if item.get("entry"):
                    entry_lbl = QLabel(item["entry"])
                    entry_lbl.setStyleSheet("font-size: 11px; color: #888;")
                    row_layout.addWidget(entry_lbl)

                orig_lbl = QLabel(item.get("original", ""))
                orig_lbl.setWordWrap(True)
                orig_lbl.setStyleSheet("color: #888; font-style: italic; font-size: 12px;")
                row_layout.addWidget(orig_lbl)

                tailored_lbl = QLabel(item.get("tailored", ""))
                tailored_lbl.setWordWrap(True)
                tailored_lbl.setStyleSheet("color: #1d1d1d; font-size: 13px;")
                row_layout.addWidget(tailored_lbl)

                copy_row = QHBoxLayout()
                copy_row.addStretch()
                copy_btn = _secondary_btn("Copy", 70)
                tailored_text = item.get("tailored", "")
                copy_btn.clicked.connect(
                    lambda checked, t=tailored_text: QGuiApplication.clipboard().setText(t)
                )
                copy_row.addWidget(copy_btn)
                row_layout.addLayout(copy_row)

                self._results_layout.addWidget(row_frame)

    def _clear_results(self):
        while self._results_layout.count():
            item = self._results_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _generate_resume(self):
        jd = self._gen_jd_input.toPlainText().strip()
        if not jd:
            self._gen_status.setStyleSheet("color: #cc3300; font-size: 12px;")
            self._gen_status.setText("Paste a job description first.")
            return

        name = self._gen_name_input.text().strip()
        url = self._gen_url_input.text().strip()
        profile = self._get_profile()

        self._clear_generate_results()
        self._gen_btn.setEnabled(False)
        self._gen_btn.setText("Generating…")
        self._gen_status.setStyleSheet("color: #555; font-size: 12px;")
        self._gen_status.setText("Starting…")

        worker = _GenerateResumeWorker(profile, jd, name, url, self._research_cache)
        thread = QThread(self)
        worker.moveToThread(thread)

        def on_finished(payload: dict):
            self._gen_btn.setEnabled(True)
            self._gen_btn.setText("📄  Generate Resume")
            self._gen_status.setText("")
            self._populate_generate_results(payload)
            if payload.get("new_research") and name:
                self._research_cache[name] = {"url": url, "result": payload["research"]}
                self._refresh_company_list()
                if self._save_fn:
                    self._save_fn()
            thread.quit()

        def on_error(msg: str):
            self._gen_btn.setEnabled(True)
            self._gen_btn.setText("📄  Generate Resume")
            self._gen_status.setStyleSheet("color: #cc3300; font-size: 12px;")
            self._gen_status.setText(f"Error: {msg}")
            thread.quit()

        def on_progress(msg: str):
            self._gen_status.setStyleSheet("color: #555; font-size: 12px;")
            self._gen_status.setText(msg)

        worker.finished.connect(on_finished)
        worker.error.connect(on_error)
        worker.progress.connect(on_progress)
        thread.started.connect(worker.run)
        thread.finished.connect(thread.deleteLater)
        self._threads.append(thread)
        self._workers.append(worker)
        thread.finished.connect(lambda: self._workers.remove(worker) if worker in self._workers else None)
        thread.start()

    def _populate_generate_results(self, payload: dict):
        layout = self._gen_results_layout

        research = payload.get("research") or {}
        layout.addWidget(self._research_section_header("COMPANY RESEARCH"))
        self._render_research_block(layout, research)

        courses = payload.get("courses") or []
        layout.addWidget(self._research_section_header("SELECTED COURSES"))
        if courses:
            for c in courses:
                layout.addWidget(self._research_text_row(f"• {c}"))
        else:
            layout.addWidget(self._research_text_row("(none)"))

        scored = payload.get("scored") or {}
        section_titles = [
            ("relevant_experience", "RELEVANT EXPERIENCE", True),
            ("projects", "PROJECTS", True),
            ("awards", "AWARDS", True),
            ("leadership", "LEADERSHIP", False),
        ]
        for key, title, include_relevancy in section_titles:
            rows = scored.get(key, [])
            if not rows:
                continue
            layout.addWidget(self._research_section_header(title))
            for r in rows:
                layout.addWidget(self._ranking_card(r, include_relevancy))

    def _ranking_card(self, row: dict, include_relevancy: bool) -> QFrame:
        frame = QFrame()
        frame.setObjectName("result-bullet-row")
        outer = QVBoxLayout(frame)
        outer.setContentsMargins(12, 10, 12, 10)
        outer.setSpacing(4)

        header = QHBoxLayout()
        title = QLabel(row.get("label", ""))
        title.setWordWrap(True)
        title.setStyleSheet("color: #1d1d1d; font-size: 13px; font-weight: 600;")
        header.addWidget(title, 1)

        score = QLabel(f"{row.get('final_score', 0.0):.3f}")
        score.setStyleSheet("color: #1d1d1d; font-size: 16px; font-weight: 700;")
        header.addWidget(score, 0, Qt.AlignmentFlag.AlignRight)
        outer.addLayout(header)

        ai = row.get("ai") or {}
        parts = [f"impact={ai.get('impact', 0):.1f}", f"prestige={ai.get('prestige', 0):.1f}"]
        if include_relevancy:
            parts.append(f"relevancy={ai.get('relevancy', 0):.1f}")
        parts.append(f"recency={row.get('recency', 0.0):.2f}")
        sub = QLabel("  ".join(parts))
        sub.setStyleSheet("color: #888; font-size: 12px;")
        outer.addWidget(sub)

        return frame

    def _clear_generate_results(self):
        while self._gen_results_layout.count():
            item = self._gen_results_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
