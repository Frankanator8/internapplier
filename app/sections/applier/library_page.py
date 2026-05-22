from __future__ import annotations

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWebEngineCore import QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMessageBox,
    QScrollArea, QSplitter, QStackedWidget, QVBoxLayout, QWidget,
)

from ..base import _label, _secondary_btn


class LibraryMixin:
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
        self._library_header.setStyleSheet("font-size: 14px; font-weight: 600;")  # color from default QLabel rule
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
        self._library_empty_label.setObjectName("muted")
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
