from __future__ import annotations

import html
import logging
import os
import tempfile
from typing import Callable

from PyQt6.QtCore import QObject, QThread, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QGuiApplication
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QScrollArea,
    QSizePolicy, QSplitter, QTabWidget, QTextEdit, QVBoxLayout, QWidget,
)

from .base import _label, _primary_btn, _secondary_btn

logger = logging.getLogger(__name__)


class _TailorWorker(QObject):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, profile: dict, jd: str):
        super().__init__()
        self._profile = profile
        self._jd = jd

    def run(self):
        from app.ai_provider import get_provider
        logger.info("_TailorWorker.run — jd=%r", self._jd[:80])
        try:
            result = get_provider().tailor_resume(self._profile, self._jd)
            logger.info("_TailorWorker.run — success, %d items", len(result))
            self.finished.emit(result)
        except Exception as exc:
            logger.exception("_TailorWorker.run — failed")
            self.error.emit(str(exc))


class _ResearchWorker(QObject):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, company_name: str, url: str):
        super().__init__()
        self._company_name = company_name
        self._url = url

    def run(self):
        from app.ai_provider import get_provider
        from app.web_scraper import SiteBlockedError, fetch_company_pages
        logger.info("_ResearchWorker.run — company=%r url=%r", self._company_name, self._url)
        try:
            text = fetch_company_pages(self._url)
            logger.debug("_ResearchWorker.run — scraped %d chars", len(text))
            result = get_provider(tier="fast").research_company(self._company_name, text)
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


class _GenerateResumeWorker(QObject):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, profile: dict, jd: str):
        super().__init__()
        self._profile = profile
        self._jd = jd

    def run(self):
        from app.ai_provider import get_provider
        logger.info("_GenerateResumeWorker.run — jd=%r", self._jd[:80])
        try:
            tex = get_provider().generate_resume(self._profile, self._jd)
            logger.info("_GenerateResumeWorker.run — success, LaTeX length=%d", len(tex))
            self.finished.emit(tex)
        except Exception as exc:
            logger.exception("_GenerateResumeWorker.run — failed")
            self.error.emit(str(exc))


class ApplierPage(QWidget):
    def __init__(self, get_profile: Callable[[], dict], parent=None):
        super().__init__(parent)
        self._get_profile = get_profile
        self._threads: list[QThread] = []
        self._workers: list[QObject] = []
        self._research_last_result: dict = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 16)
        outer.setSpacing(14)

        outer.addWidget(_label("Applier", "section-title"))

        tabs = QTabWidget()
        tabs.addTab(self._build_tailor_tab(), "✦  Tailor Resume")
        tabs.addTab(self._build_research_tab(), "🔍  Research Company")
        outer.addWidget(tabs, 1)

    def _build_tailor_tab(self) -> QWidget:
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

        self._pdf_btn = _secondary_btn("Open in Overleaf", 200)
        self._pdf_btn.clicked.connect(self._generate_pdf)
        left_layout.addWidget(self._pdf_btn)

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

        return splitter

    def _build_research_tab(self) -> QWidget:
        wrap = QWidget()
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(10)

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

        layout.addLayout(form_row)

        self._research_btn = _primary_btn("🔍  Research Company")
        self._research_btn.clicked.connect(self._research)
        layout.addWidget(self._research_btn)

        self._research_status = QLabel("")
        self._research_status.setWordWrap(True)
        self._research_status.setStyleSheet("color: #555; font-size: 12px;")
        layout.addWidget(self._research_status)

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
        layout.addWidget(scroll, 1)

        return wrap

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
        self._research_status.setText(
            f"Launching headless browser and fetching pages from {url}…"
        )

        worker = _ResearchWorker(name, url)
        thread = QThread(self)
        worker.moveToThread(thread)

        def on_finished(result: dict):
            self._research_btn.setEnabled(True)
            self._research_btn.setText("🔍  Research Company")
            self._research_status.setText("")
            self._research_last_result = result
            self._populate_research_results(result)
            thread.quit()

        def on_error(msg: str):
            self._research_btn.setEnabled(True)
            self._research_btn.setText("🔍  Research Company")
            self._research_status.setStyleSheet("color: #cc3300; font-size: 12px;")
            self._research_status.setText(f"Error: {msg}")
            thread.quit()

        worker.finished.connect(on_finished)
        worker.error.connect(on_error)
        thread.started.connect(worker.run)
        thread.finished.connect(thread.deleteLater)
        self._threads.append(thread)
        self._workers.append(worker)
        thread.finished.connect(lambda: self._workers.remove(worker) if worker in self._workers else None)
        thread.start()

    def _populate_research_results(self, result: dict):
        summary = (result.get("summary") or "").strip()
        values = result.get("core_values") or []
        projects = result.get("recent_projects") or []

        if not summary and not values and not projects:
            empty = QLabel("No information could be extracted from the site.")
            empty.setStyleSheet("color: #777; font-size: 13px;")
            self._research_results_layout.addWidget(empty)
            return

        if summary:
            self._research_results_layout.addWidget(
                self._research_section_header("SUMMARY")
            )
            self._research_results_layout.addWidget(
                self._research_text_row(summary)
            )

        if values:
            self._research_results_layout.addWidget(
                self._research_section_header("CORE VALUES")
            )
            for v in values:
                self._research_results_layout.addWidget(
                    self._research_text_row(f"• {v}")
                )

        if projects:
            self._research_results_layout.addWidget(
                self._research_section_header("RECENT PROJECTS / NEWS")
            )
            for p in projects:
                self._research_results_layout.addWidget(
                    self._research_text_row(f"• {p}")
                )

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
        return {
            "company_name": self._research_name_input.text().strip(),
            "url": self._research_url_input.text().strip(),
            "result": self._research_last_result or {},
        }

    def load_research_data(self, data: dict):
        if not data:
            return
        self._research_name_input.setText(data.get("company_name", ""))
        self._research_url_input.setText(data.get("url", ""))
        result = data.get("result") or {}
        self._research_last_result = result
        self._clear_research_results()
        if result:
            self._populate_research_results(result)

    def _tailor(self):
        jd = self._jd_input.toPlainText().strip()
        if not jd:
            return

        profile = self._get_profile()
        self._tailor_btn.setEnabled(False)
        self._tailor_btn.setText("Tailoring…")
        self._clear_results()

        worker = _TailorWorker(profile, jd)
        thread = QThread(self)
        worker.moveToThread(thread)

        def on_finished(items: list):
            self._tailor_btn.setEnabled(True)
            self._tailor_btn.setText("✦  Tailor My Resume")
            self._populate_results(items)
            thread.quit()

        def on_error(msg: str):
            self._tailor_btn.setEnabled(True)
            self._tailor_btn.setText("✦  Tailor My Resume")
            err_label = QLabel(f"Error: {msg}")
            err_label.setWordWrap(True)
            err_label.setStyleSheet("color: #cc3300; font-size: 13px;")
            self._results_layout.addWidget(err_label)
            thread.quit()

        worker.finished.connect(on_finished)
        worker.error.connect(on_error)
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

    def _generate_pdf(self):
        jd = self._jd_input.toPlainText().strip()
        if not jd:
            return

        profile = self._get_profile()
        self._pdf_btn.setEnabled(False)
        self._pdf_btn.setText("Opening Overleaf…")

        worker = _GenerateResumeWorker(profile, jd)
        thread = QThread(self)
        worker.moveToThread(thread)

        def on_finished(tex: str):
            self._pdf_btn.setEnabled(True)
            self._pdf_btn.setText("Open in Overleaf")
            thread.quit()
            self._open_in_overleaf(tex)

        def on_error(msg: str):
            self._pdf_btn.setEnabled(True)
            self._pdf_btn.setText("Open in Overleaf")
            err_label = QLabel(f"Error: {msg}")
            err_label.setWordWrap(True)
            err_label.setStyleSheet("color: #cc3300; font-size: 13px;")
            self._results_layout.addWidget(err_label)
            thread.quit()

        worker.finished.connect(on_finished)
        worker.error.connect(on_error)
        thread.started.connect(worker.run)
        thread.finished.connect(thread.deleteLater)
        self._threads.append(thread)
        self._workers.append(worker)
        thread.finished.connect(lambda: self._workers.remove(worker) if worker in self._workers else None)
        thread.start()

    def _open_in_overleaf(self, tex: str):
        escaped = html.escape(tex, quote=True)
        page = (
            "<!doctype html><html><body>"
            "<form id='f' action='https://www.overleaf.com/docs' method='post'>"
            f"<input type='hidden' name='snip' value=\"{escaped}\">"
            "<input type='hidden' name='snip_name' value='resume.tex'>"
            "<input type='hidden' name='engine' value='pdflatex'>"
            "</form>"
            "<script>document.getElementById('f').submit();</script>"
            "</body></html>"
        )
        fd, path = tempfile.mkstemp(suffix=".html", prefix="overleaf_")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(page)
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _clear_results(self):
        while self._results_layout.count():
            item = self._results_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
