from __future__ import annotations

import logging
import shutil
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout, QListWidgetItem, QMessageBox, QPlainTextEdit,
    QStackedWidget, QWidget,
)

from api.app_settings import get_resume_output_dir
from api.generate_resume.persist import (
    list_generated_resumes, read_tex_sidecar, remove_tex_sidecar, tex_sidecar,
    write_tex_sidecar,
)
from app.ui.latex_preview import LatexPreviewPane, PdfView, compile_with_fill, page_fill_status
from app.ui.widgets import (
    button, confirm, hsplitter, label, list_pane, mono_font, open_path,
    set_status, set_titled_content, status_label, vbox_widget,
)

logger = logging.getLogger(__name__)


class _LatexEdit:
    """State of an in-progress edit of one saved resume's LaTeX source."""

    def __init__(self, path: str, saved_latex: str):
        self.path = path
        self.saved_latex = saved_latex
        self.compiled_latex = ""
        self.compiled_pdf = ""
        self.save_after_compile = False


class LibraryPage(QWidget):
    """Browse saved resume PDFs; edit and recompile their LaTeX source in place."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._edit: _LatexEdit | None = None
        self._suppress_select = False
        # PDFs rewritten in place this session; WebEngine would show them stale.
        self._rewritten: set[str] = set()

        # ── Left: saved resumes ──────────────────────────────────
        left, left_layout, self._list = list_pane(
            "Saved Resumes", name="library-list", margins=(0, 8, 8, 0), width=(180, 260),
        )
        self._list.itemSelectionChanged.connect(self._on_select)
        refresh_btn = button("🔄  Refresh", "secondary")
        refresh_btn.clicked.connect(self.on_shown)
        left_layout.addWidget(refresh_btn)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        for text, slot in (("Reveal", self._reveal), ("Delete", self._delete)):
            btn = button(text, "secondary", 90)
            btn.clicked.connect(slot)
            btn_row.addWidget(btn)
        left_layout.addLayout(btn_row)

        # ── Right: viewer / editor ───────────────────────────────
        right, right_layout = vbox_widget((0, 8, 0, 0), spacing=8)
        header_row = QHBoxLayout()
        header_row.setSpacing(8)
        self._header = label("", "group-subtitle")
        header_row.addWidget(self._header, 1)
        self._edit_btn = button("Edit", "secondary", 80)
        self._edit_btn.clicked.connect(self._enter_edit)
        self._edit_btn.setVisible(False)
        header_row.addWidget(self._edit_btn, 0, Qt.AlignmentFlag.AlignRight)
        self._open_btn = button("Open Externally", "secondary", 140)
        self._open_btn.clicked.connect(lambda: open_path(self._current_path()))
        self._open_btn.setVisible(False)
        header_row.addWidget(self._open_btn, 0, Qt.AlignmentFlag.AlignRight)
        right_layout.addLayout(header_row)

        self._edit_bar = QWidget()
        edit_bar = QHBoxLayout(self._edit_bar)
        edit_bar.setContentsMargins(0, 0, 0, 0)
        edit_bar.setSpacing(8)
        save_btn = button("Save", width=90)
        save_btn.clicked.connect(self._save_edits)
        cancel_btn = button("Cancel", "secondary", 90)
        cancel_btn.clicked.connect(self._cancel_edit)
        self._status = status_label()
        edit_bar.addWidget(save_btn)
        edit_bar.addWidget(cancel_btn)
        edit_bar.addWidget(self._status, 1)
        self._edit_bar.setVisible(False)
        right_layout.addWidget(self._edit_bar)

        self._stack = QStackedWidget()
        self._empty_label = label("No resume selected.\nGenerated PDFs will appear here.", "muted")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._stack.addWidget(self._empty_label)
        self._pdf_view = PdfView()
        self._stack.addWidget(self._pdf_view)

        self._latex_edit = QPlainTextEdit()
        self._latex_edit.setFont(mono_font())
        self._latex_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._preview = LatexPreviewPane(self._latex_edit.toPlainText, compile_with_fill, "")
        self._preview.busy_changed.connect(self._on_compile_busy)
        self._preview.compiled.connect(self._on_compiled)
        self._preview.failed.connect(self._on_compile_failed)
        self._latex_edit.textChanged.connect(lambda: self._edit and self._preview.schedule())
        self._edit_splitter = hsplitter(self._latex_edit, self._preview, sizes=[420, 420])
        self._stack.addWidget(self._edit_splitter)
        right_layout.addWidget(self._stack, 1)

        set_titled_content(self, "Library", hsplitter(left, right, sizes=[220, 700]))

    # ── Listing ─────────────────────────────────────────────────
    def on_shown(self) -> None:
        """Re-read the output folder, keeping the selection (and any edit) if possible."""
        keep_path = self._edit.path if self._edit else self._current_path()
        resumes = list_generated_resumes()

        self._list.blockSignals(True)
        self._list.clear()
        target_row = 0
        for i, (path, text) in enumerate(resumes):
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            self._list.addItem(item)
            if str(path) == keep_path:
                target_row = i
        found = any(str(p) == keep_path for p, _ in resumes)
        if resumes:
            self._list.setCurrentRow(target_row)
        self._list.blockSignals(False)

        if not resumes:
            if self._edit:
                self._exit_edit(reload_view=False)
            self._show_nothing("No resumes yet — generate one from the Generate Resume tab.")
            return
        if self._edit:
            if not found:
                self._exit_edit(reload_view=False)
                self._on_select()
            return
        self._on_select()

    def _current_path(self) -> str | None:
        item = self._list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _select_path(self, path: str) -> None:
        for i in range(self._list.count()):
            if self._list.item(i).data(Qt.ItemDataRole.UserRole) == path:
                self._list.setCurrentRow(i)
                return

    def _show_nothing(self, message: str | None = None) -> None:
        self._header.setText("")
        self._open_btn.setVisible(False)
        self._update_edit_btn(None)
        if message:
            self._empty_label.setText(message)
        self._stack.setCurrentWidget(self._empty_label)

    def _update_edit_btn(self, path: str | None) -> None:
        if self._edit or not path:
            self._edit_btn.setVisible(False)
            return
        self._edit_btn.setVisible(True)
        has_src = tex_sidecar(path).is_file()
        self._edit_btn.setEnabled(has_src)
        self._edit_btn.setToolTip(
            "Edit the LaTeX source and recompile." if has_src else
            "No LaTeX source for this file. Generate or export a new resume "
            "to enable editing."
        )

    def _on_select(self) -> None:
        if self._suppress_select:
            return
        path = self._current_path()
        if self._edit:
            if path == self._edit.path:
                return
            if not self._confirm_discard():
                self._suppress_select = True
                self._select_path(self._edit.path)
                self._suppress_select = False
                return
            self._exit_edit(reload_view=False)

        if not path:
            self._show_nothing()
            return
        self._header.setText(self._list.currentItem().text())
        self._open_btn.setVisible(True)
        self._update_edit_btn(path)
        self._pdf_view.show_pdf(path, bust_cache=path in self._rewritten)
        self._stack.setCurrentWidget(self._pdf_view)

    # ── Editing ─────────────────────────────────────────────────
    def _confirm_discard(self) -> bool:
        dirty = self._edit is not None and self._latex_edit.toPlainText() != self._edit.saved_latex
        return not dirty or confirm(self, "Discard edits", "You have unsaved changes. Discard them?")

    def _enter_edit(self) -> None:
        path = self._current_path()
        if not path:
            return
        latex = read_tex_sidecar(path)
        if latex is None:
            QMessageBox.information(self, "Cannot edit", "No LaTeX source is saved next to this PDF.")
            self._update_edit_btn(path)
            return
        self._edit = _LatexEdit(path, latex)
        self._latex_edit.blockSignals(True)
        self._latex_edit.setPlainText(latex)
        self._latex_edit.blockSignals(False)
        self._edit_bar.setVisible(True)
        self._edit_btn.setVisible(False)
        set_status(self._status, "neutral", "")
        self._stack.setCurrentWidget(self._edit_splitter)
        self._preview.compile_now()

    def _cancel_edit(self) -> None:
        if self._confirm_discard():
            self._exit_edit()

    def _exit_edit(self, *, reload_view: bool = True) -> None:
        self._preview.cancel_pending()
        self._edit = None
        self._edit_bar.setVisible(False)
        if reload_view:
            self._on_select()
        else:
            self._update_edit_btn(self._current_path())

    def _on_compile_busy(self, busy: bool) -> None:
        if busy and self._edit:
            set_status(self._status, "neutral", "Running pdflatex…")

    def _on_compiled(self, result: dict) -> None:
        edit = self._edit
        if edit is None:
            return
        set_status(self._status, *page_fill_status(result["fill"]))
        edit.compiled_latex = result["latex"]
        edit.compiled_pdf = result["pdf"]
        if edit.save_after_compile and self._latex_edit.toPlainText() == result["latex"]:
            edit.save_after_compile = False
            self._write_saved()

    def _on_compile_failed(self, _log: str) -> None:
        edit = self._edit
        if edit is None:
            return
        edit.save_after_compile = False
        edit.compiled_latex = edit.compiled_pdf = ""
        set_status(self._status, "error", "Compile failed")

    def _save_edits(self) -> None:
        edit = self._edit
        if edit is None:
            return
        if (
            self._latex_edit.toPlainText() == edit.compiled_latex
            and edit.compiled_pdf
            and Path(edit.compiled_pdf).exists()
        ):
            self._write_saved()
            return
        edit.save_after_compile = True
        self._preview.compile_now()

    def _write_saved(self) -> None:
        """Copy the last compiled PDF and its source over the saved resume."""
        edit = self._edit
        if edit is None or not edit.compiled_pdf or not edit.compiled_latex:
            return
        src = Path(edit.compiled_pdf)
        if not src.is_file():
            set_status(self._status, "error", "Save failed — compiled PDF is missing.")
            return
        try:
            shutil.copyfile(src, edit.path)
            write_tex_sidecar(edit.path, edit.compiled_latex)
        except OSError as e:
            logger.exception("LibraryPage — save failed")
            set_status(self._status, "error", f"Save failed: {e}")
            return
        edit.saved_latex = edit.compiled_latex
        self._rewritten.add(edit.path)
        set_status(self._status, "ok", "Saved")

    # ── File actions ────────────────────────────────────────────
    def _reveal(self) -> None:
        path = self._current_path()
        open_path(Path(path).parent if path else get_resume_output_dir())

    def _delete(self) -> None:
        path = self._current_path()
        if not path:
            return
        p = Path(path)
        if not confirm(self, "Delete resume", f"Delete {p.name}? This removes the PDF and its source from disk."):
            return
        if self._edit:
            self._exit_edit(reload_view=False)
        self._pdf_view.clear()
        self._preview.view.clear()
        try:
            p.unlink()
        except OSError as e:
            QMessageBox.warning(self, "Delete failed", str(e))
            self.on_shown()
            return
        remove_tex_sidecar(p)
        self._rewritten.discard(path)
        self.on_shown()
