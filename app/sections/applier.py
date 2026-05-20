from __future__ import annotations

import logging
from typing import Callable

from PyQt6.QtCore import QObject, QThread, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QFont, QGuiApplication, QTextCursor
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMessageBox, QPlainTextEdit, QScrollArea, QSizePolicy, QSplitter,
    QStackedWidget, QTextEdit, QVBoxLayout, QWidget,
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineSettings

from .base import _label, _primary_btn, _secondary_btn

logger = logging.getLogger(__name__)


class _ResearchWorker(QObject):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, company_name: str, url: str):
        super().__init__()
        self._company_name = company_name
        self._url = url

    def run(self):
        from api.ai_provider import get_provider
        from api.web_scraper import SiteBlockedError, fetch_company_pages
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
    stream = pyqtSignal(str, str)  # (stage, chunk)

    def __init__(self, profile: dict, jd: str, company_name: str, url: str, research_cache: dict):
        super().__init__()
        self._profile = profile
        self._jd = jd
        self._company = company_name
        self._url = url
        self._cache = research_cache or {}

    def run(self):
        from api.ai_provider import get_provider
        from api.generate_resume import ResumeGenerator
        logger.info("_GenerateResumeWorker.run — company=%r jd=%r", self._company, self._jd[:80])
        try:
            new_research = False
            research = _research_from_cache(self._cache, self._company)
            if research is not None:
                self.progress.emit(f"Using cached research for {self._company!r}…")
            elif self._company and self._url:
                from api.web_scraper import fetch_company_pages
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

            self.progress.emit("Generating LaTeX (this can take a minute)…")
            latex_result = gen.generate_latex(
                company=self._company or None,
                progress_cb=self.progress.emit,
                stream_cb=self.stream.emit,
            )

            pdf_path = latex_result.get("pdf")
            logger.info(
                "_GenerateResumeWorker.run — success, fill=%s",
                latex_result.get("fill"),
            )
            self.finished.emit({
                "research": research,
                "new_research": new_research,
                "latex": latex_result.get("latex", ""),
                "pdf": str(pdf_path) if pdf_path else "",
                "fill": latex_result.get("fill"),
                "grade": latex_result.get("grade"),
                "attempts": latex_result.get("attempts") or [],
                "chosen_attempt": latex_result.get("chosen_attempt"),
            })
        except Exception as exc:
            logger.exception("_GenerateResumeWorker.run — failed")
            self.error.emit(str(exc))


class _QuestionWorker(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(str)
    stream = pyqtSignal(str)

    def __init__(self, question: str, profile: dict, company_name: str, job_description: str, research_cache: dict):
        super().__init__()
        self._question = question
        self._profile = profile
        self._company = company_name
        self._jd = job_description
        self._cache = research_cache or {}

    def run(self):
        from api.ai_provider import get_provider
        logger.info(
            "_QuestionWorker.run — company=%r question=%r jd=%s",
            self._company, self._question[:80],
            f"{len(self._jd)} chars" if self._jd else "none",
        )
        try:
            research = _research_from_cache(self._cache, self._company) if self._company else None
            for chunk in get_provider().answer_question_stream(
                question=self._question,
                profile=self._profile,
                company_research=research,
                company_name=self._company or None,
                job_description=self._jd or None,
            ):
                self.stream.emit(chunk)
            self.finished.emit()
        except Exception as exc:
            logger.exception("_QuestionWorker.run — failed")
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

        for label in ("📄  Generate Resume", "🔍  Research Company", "📚  Library", "❓  Answer Question"):
            item = QListWidgetItem(label)
            item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            self._applier_sidebar.addItem(item)

        self._applier_stack = QStackedWidget()
        self._applier_stack.addWidget(self._build_generate_resume_page())
        self._applier_stack.addWidget(self._build_research_page())
        self._applier_stack.addWidget(self._build_library_page())
        self._applier_stack.addWidget(self._build_answer_question_page())

        self._applier_sidebar.currentRowChanged.connect(self._applier_stack.setCurrentIndex)
        self._applier_sidebar.currentRowChanged.connect(self._on_applier_section_changed)
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

        # ── Right: live stream view + results ────────────────────
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self._gen_stream_view = QPlainTextEdit()
        self._gen_stream_view.setReadOnly(True)
        self._gen_stream_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        mono = QFont("Menlo")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        mono.setPointSize(11)
        self._gen_stream_view.setFont(mono)
        self._gen_stream_view.setStyleSheet(
            "QPlainTextEdit { background: #1d1d1d; color: #e6e6e6;"
            " border: 1px solid #333; padding: 8px; }"
        )
        self._gen_stream_view.setVisible(False)
        self._gen_stream_last_stage: str | None = None
        right_layout.addWidget(self._gen_stream_view, 1)

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
        self._gen_results_scroll = scroll
        right_layout.addWidget(scroll, 1)

        splitter.addWidget(right)
        splitter.setSizes([400, 560])

        return self._wrap_page("Generate Resume", splitter)

    def _on_gen_stream(self, stage: str, chunk: str) -> None:
        if stage != self._gen_stream_last_stage:
            if self._gen_stream_last_stage is not None:
                sep = f"\n\n\n══════ {stage} ══════\n\n"
            else:
                sep = f"══════ {stage} ══════\n\n"
            self._gen_stream_view.moveCursor(QTextCursor.MoveOperation.End)
            self._gen_stream_view.insertPlainText(sep)
            self._gen_stream_last_stage = stage
        self._gen_stream_view.moveCursor(QTextCursor.MoveOperation.End)
        self._gen_stream_view.insertPlainText(chunk)
        sb = self._gen_stream_view.verticalScrollBar()
        sb.setValue(sb.maximum())

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
        self._gen_stream_view.clear()
        self._gen_stream_last_stage = None
        self._gen_stream_view.setVisible(True)
        self._gen_results_scroll.setVisible(False)
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
            self._gen_stream_view.setVisible(False)
            self._gen_results_scroll.setVisible(True)
            self._populate_generate_results(payload)
            if payload.get("new_research") and name:
                self._research_cache[name] = {"url": url, "result": payload["research"]}
                self._refresh_company_list()
                if self._save_fn:
                    self._save_fn()
            self._refresh_library()
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
        worker.stream.connect(self._on_gen_stream)
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

        fill = payload.get("fill")
        grade = payload.get("grade") or {}
        latex = payload.get("latex") or ""
        pdf = payload.get("pdf") or ""
        if latex or fill is not None or grade or pdf:
            layout.addWidget(self._research_section_header("GENERATED RESUME"))
            if fill is None:
                layout.addWidget(self._research_text_row("Pages: (failed to compile)"))
            else:
                layout.addWidget(self._research_text_row(f"Pages: {fill:.2f}"))
            if grade:
                layout.addWidget(self._research_text_row(f"Grade: {grade.get('score', 0):.2f}/10"))
                fb = grade.get("feedback") or ""
                if fb:
                    layout.addWidget(self._research_text_row("Feedback: " + fb))
                drops = grade.get("drops") or []
                if drops:
                    layout.addWidget(self._research_text_row(
                        "Dropped for page-fit: " + "; ".join(drops)
                    ))

            btn_row_frame = QFrame()
            btn_row = QHBoxLayout(btn_row_frame)
            btn_row.setContentsMargins(0, 4, 0, 0)
            btn_row.setSpacing(8)
            if pdf:
                open_btn = _primary_btn("Open PDF")
                open_btn.clicked.connect(
                    lambda checked, p=pdf: QDesktopServices.openUrl(QUrl.fromLocalFile(p))
                )
                btn_row.addWidget(open_btn)
            if latex:
                copy_btn = _secondary_btn("Copy LaTeX", 120)
                copy_btn.clicked.connect(
                    lambda checked, t=latex: QGuiApplication.clipboard().setText(t)
                )
                btn_row.addWidget(copy_btn)
            btn_row.addStretch()
            layout.addWidget(btn_row_frame)

            attempts = payload.get("attempts") or []
            chosen = payload.get("chosen_attempt")
            if len(attempts) > 1:
                layout.addWidget(self._research_section_header("ALL ATTEMPTS"))
                for a in attempts:
                    n = a.get("attempt")
                    a_pdf = a.get("pdf") or ""
                    a_grade = a.get("grade") or {}
                    a_fill = a.get("fill")
                    a_compile_error = a.get("compile_error") or ""
                    score_part = (
                        f"{a_grade.get('score', 0):.2f}/10"
                        if a_grade else "ungraded"
                    )
                    pages_part = (
                        f"{a_fill:.2f}pg" if a_fill is not None else "compile✗"
                    )
                    mark = " ★" if n == chosen else ""
                    label = f"Attempt {n} ({score_part}, {pages_part}){mark}"

                    btn_frame = QFrame()
                    btn_layout = QHBoxLayout(btn_frame)
                    btn_layout.setContentsMargins(0, 0, 0, 0)
                    btn_layout.setSpacing(8)
                    btn = _secondary_btn(label, 0)
                    btn.setEnabled(bool(a_pdf))
                    if a_pdf:
                        btn.clicked.connect(
                            lambda checked, p=a_pdf:
                            QDesktopServices.openUrl(QUrl.fromLocalFile(p))
                        )
                    btn_layout.addWidget(btn)
                    btn_layout.addStretch()
                    layout.addWidget(btn_frame)

                    a_feedback = a_grade.get("feedback") or ""
                    if a_compile_error:
                        layout.addWidget(self._research_text_row(
                            "Compile error: " + a_compile_error
                        ))
                    elif a_feedback:
                        layout.addWidget(self._research_text_row(
                            "Feedback: " + a_feedback
                        ))

    def _clear_generate_results(self):
        while self._gen_results_layout.count():
            item = self._gen_results_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    # ── Library ─────────────────────────────────────────────────
    def _build_library_page(self) -> QWidget:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        left = QWidget()
        left.setMinimumWidth(180)
        left.setMaximumWidth(260)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 8, 8, 0)
        left_layout.setSpacing(6)

        left_layout.addWidget(_label("Saved Resumes"))

        self._library_list = QListWidget()
        self._library_list.setObjectName("library-list")
        self._library_list.itemSelectionChanged.connect(self._on_library_select)
        left_layout.addWidget(self._library_list, 1)

        self._library_refresh_btn = _secondary_btn("🔄  Refresh", 0)
        self._library_refresh_btn.clicked.connect(self._refresh_library)
        left_layout.addWidget(self._library_refresh_btn)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        self._library_reveal_btn = _secondary_btn("Reveal", 90)
        self._library_reveal_btn.clicked.connect(self._reveal_library_item)
        btn_row.addWidget(self._library_reveal_btn)
        self._library_delete_btn = _secondary_btn("Delete", 90)
        self._library_delete_btn.clicked.connect(self._delete_library_item)
        btn_row.addWidget(self._library_delete_btn)
        left_layout.addLayout(btn_row)

        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 8, 0, 0)
        right_layout.setSpacing(8)

        header_row = QHBoxLayout()
        header_row.setSpacing(8)
        self._library_header = QLabel("")
        self._library_header.setStyleSheet("color: #1d1d1d; font-size: 14px; font-weight: 600;")
        header_row.addWidget(self._library_header, 1)
        self._library_open_btn = _secondary_btn("Open Externally", 140)
        self._library_open_btn.clicked.connect(self._open_library_item_external)
        self._library_open_btn.setVisible(False)
        header_row.addWidget(self._library_open_btn, 0, Qt.AlignmentFlag.AlignRight)
        right_layout.addLayout(header_row)

        self._library_preview_stack = QStackedWidget()
        self._library_empty_label = QLabel(
            "No resume selected.\nGenerated PDFs will appear here."
        )
        self._library_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._library_empty_label.setStyleSheet("color: #888; font-size: 13px;")
        self._library_preview_stack.addWidget(self._library_empty_label)

        self._library_pdf_view = QWebEngineView()
        settings = self._library_pdf_view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.PdfViewerEnabled, True)
        self._library_preview_stack.addWidget(self._library_pdf_view)
        right_layout.addWidget(self._library_preview_stack, 1)

        splitter.addWidget(right)
        splitter.setSizes([220, 700])

        return self._wrap_page("Library", splitter)

    # ── Answer Question ─────────────────────────────────────────
    def _build_answer_question_page(self) -> QWidget:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        left = QWidget()
        left.setMinimumWidth(320)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 8, 0, 0)
        left_layout.setSpacing(10)

        left_layout.addWidget(_label("Company (optional)"))
        self._answer_company_input = QLineEdit()
        self._answer_company_input.setPlaceholderText(
            "Match a researched company to tailor the answer"
        )
        left_layout.addWidget(self._answer_company_input)

        left_layout.addWidget(_label("Question"))
        self._answer_question_input = QTextEdit()
        self._answer_question_input.setPlaceholderText(
            "e.g. Why are you interested in this role?"
        )
        left_layout.addWidget(self._answer_question_input, 1)

        left_layout.addWidget(_label("Job Description (optional)"))
        self._answer_jd_input = QTextEdit()
        self._answer_jd_input.setPlaceholderText(
            "Paste the job description to tailor the answer to the role…"
        )
        left_layout.addWidget(self._answer_jd_input, 2)

        self._answer_btn = _primary_btn("❓  Answer Question")
        self._answer_btn.clicked.connect(self._answer_question)
        left_layout.addWidget(self._answer_btn)

        self._answer_status = QLabel("")
        self._answer_status.setWordWrap(True)
        self._answer_status.setStyleSheet("color: #555; font-size: 12px;")
        left_layout.addWidget(self._answer_status)

        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 8, 0, 0)
        right_layout.setSpacing(8)

        self._answer_output = QTextEdit()
        self._answer_output.setReadOnly(True)
        self._answer_output.setPlaceholderText(
            "The generated answer will stream here."
        )
        right_layout.addWidget(self._answer_output, 1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self._answer_copy_btn = _secondary_btn("Copy Answer", 120)
        self._answer_copy_btn.clicked.connect(
            lambda: QGuiApplication.clipboard().setText(
                self._answer_output.toPlainText()
            )
        )
        btn_row.addWidget(self._answer_copy_btn)
        btn_row.addStretch()
        right_layout.addLayout(btn_row)

        splitter.addWidget(right)
        splitter.setSizes([360, 600])

        return self._wrap_page("Answer Question", splitter)

    def _answer_question(self):
        question = self._answer_question_input.toPlainText().strip()
        if not question:
            self._answer_status.setStyleSheet("color: #cc3300; font-size: 12px;")
            self._answer_status.setText("Type a question first.")
            return

        company = self._answer_company_input.text().strip()
        jd = self._answer_jd_input.toPlainText().strip()
        profile = self._get_profile()

        self._answer_output.clear()
        self._answer_btn.setEnabled(False)
        self._answer_btn.setText("Answering…")
        self._answer_status.setStyleSheet("color: #555; font-size: 12px;")
        if company and _research_from_cache(self._research_cache, company):
            self._answer_status.setText(f"Using cached research for {company!r}…")
        elif company:
            self._answer_status.setText(
                f"No cached research for {company!r} — answering from profile only."
            )
        else:
            self._answer_status.setText("Answering from profile…")

        worker = _QuestionWorker(question, profile, company, jd, self._research_cache)
        thread = QThread(self)
        worker.moveToThread(thread)

        def on_finished():
            self._answer_btn.setEnabled(True)
            self._answer_btn.setText("❓  Answer Question")
            self._answer_status.setText("")
            thread.quit()

        def on_error(msg: str):
            self._answer_btn.setEnabled(True)
            self._answer_btn.setText("❓  Answer Question")
            self._answer_status.setStyleSheet("color: #cc3300; font-size: 12px;")
            self._answer_status.setText(f"Error: {msg}")
            thread.quit()

        worker.finished.connect(on_finished)
        worker.error.connect(on_error)
        worker.stream.connect(self._on_answer_chunk)
        thread.started.connect(worker.run)
        thread.finished.connect(thread.deleteLater)
        self._threads.append(thread)
        self._workers.append(worker)
        thread.finished.connect(lambda: self._workers.remove(worker) if worker in self._workers else None)
        thread.start()

    def _on_answer_chunk(self, chunk: str):
        self._answer_output.moveCursor(QTextCursor.MoveOperation.End)
        self._answer_output.insertPlainText(chunk)
        sb = self._answer_output.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_applier_section_changed(self, idx: int):
        if idx == 2:
            self._refresh_library()

    def _refresh_library(self):
        if not hasattr(self, "_library_list"):
            return
        from api.ai_provider import get_resume_output_dir

        prev_path = self._current_library_path()
        out_dir = get_resume_output_dir()
        pdfs: list = []
        if out_dir.exists():
            try:
                pdfs = sorted(
                    out_dir.glob("*.pdf"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
            except OSError:
                pdfs = []

        self._library_list.blockSignals(True)
        self._library_list.clear()
        for p in pdfs:
            stem = p.stem
            if stem.endswith("_resume"):
                stem = stem[: -len("_resume")]
            label = stem.replace("_", " ").replace("-", " ").strip().title() or p.name
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, str(p))
            self._library_list.addItem(item)
        self._library_list.blockSignals(False)

        if not pdfs:
            self._library_header.setText("")
            self._library_open_btn.setVisible(False)
            self._library_empty_label.setText(
                "No resumes yet — generate one from the Generate Resume tab."
            )
            self._library_preview_stack.setCurrentWidget(self._library_empty_label)
            return

        target_row = 0
        if prev_path:
            for i in range(self._library_list.count()):
                if self._library_list.item(i).data(Qt.ItemDataRole.UserRole) == prev_path:
                    target_row = i
                    break
        self._library_list.setCurrentRow(target_row)

    def _current_library_path(self) -> str | None:
        if not hasattr(self, "_library_list"):
            return None
        item = self._library_list.currentItem()
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def _on_library_select(self):
        path = self._current_library_path()
        if not path:
            self._library_header.setText("")
            self._library_open_btn.setVisible(False)
            self._library_preview_stack.setCurrentWidget(self._library_empty_label)
            return
        item = self._library_list.currentItem()
        self._library_header.setText(item.text() if item else "")
        self._library_open_btn.setVisible(True)
        self._library_pdf_view.setUrl(QUrl.fromLocalFile(path))
        self._library_preview_stack.setCurrentWidget(self._library_pdf_view)

    def _open_library_item_external(self):
        path = self._current_library_path()
        if path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _reveal_library_item(self):
        path = self._current_library_path()
        if not path:
            from api.ai_provider import get_resume_output_dir
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(get_resume_output_dir())))
            return
        import pathlib
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(pathlib.Path(path).parent)))

    def _delete_library_item(self):
        path = self._current_library_path()
        if not path:
            return
        import pathlib
        p = pathlib.Path(path)
        confirm = QMessageBox.question(
            self,
            "Delete resume",
            f"Delete {p.name}? This removes the file from disk.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self._library_pdf_view.setUrl(QUrl("about:blank"))
        try:
            p.unlink()
        except OSError as e:
            QMessageBox.warning(self, "Delete failed", str(e))
        self._refresh_library()
