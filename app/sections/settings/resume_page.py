from __future__ import annotations

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDoubleSpinBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QPlainTextEdit, QSpinBox, QVBoxLayout, QWidget,
)

from api import ai_provider, app_settings

from ..base import _label, _primary_btn, _secondary_btn, _set_status


class ResumeMixin:
    def _build_resume_page(self) -> QWidget:
        mono = QFont("Menlo")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        mono.setPointSize(11)

        resume_card = QFrame()
        resume_card.setObjectName("card")
        resume_card.setMaximumWidth(800)
        rc_layout = QVBoxLayout(resume_card)
        rc_layout.setContentsMargins(28, 24, 28, 28)
        rc_layout.setSpacing(16)

        resume_title = QLabel("Resume")
        resume_title.setObjectName("card-title")
        rc_layout.addWidget(resume_title)

        resume_hint = QLabel(
            "Default resume template (LaTeX). Used as the structural base when "
            "generating tailored resumes. Leave empty to fall back to the built-in style."
        )
        resume_hint.setWordWrap(True)
        resume_hint.setObjectName("hint")
        rc_layout.addWidget(resume_hint)

        page_cap_row = QHBoxLayout()
        page_cap_row.setSpacing(12)
        page_cap_row.addWidget(_label("Page cap"))
        self._page_cap_spin = QSpinBox()
        self._page_cap_spin.setMinimum(1)
        self._page_cap_spin.setMaximum(99)
        self._page_cap_spin.setValue(ai_provider.get_resume_page_cap())
        self._page_cap_spin.setFixedWidth(80)
        page_cap_row.addWidget(self._page_cap_spin)
        page_cap_row.addStretch()
        rc_layout.addLayout(page_cap_row)

        max_iters_row = QHBoxLayout()
        max_iters_row.setSpacing(12)
        max_iters_row.addWidget(_label("Max iterations"))
        self._max_iters_spin = QSpinBox()
        self._max_iters_spin.setMinimum(1)
        self._max_iters_spin.setMaximum(99)
        self._max_iters_spin.setValue(ai_provider.get_max_generation_attempts())
        self._max_iters_spin.setFixedWidth(80)
        max_iters_row.addWidget(self._max_iters_spin)
        max_iters_row.addStretch()
        rc_layout.addLayout(max_iters_row)

        score_row = QHBoxLayout()
        score_row.setSpacing(12)
        score_row.addWidget(_label("Accept score ≥"))
        self._score_threshold_spin = QDoubleSpinBox()
        self._score_threshold_spin.setMinimum(0.0)
        self._score_threshold_spin.setMaximum(10.0)
        self._score_threshold_spin.setSingleStep(0.1)
        self._score_threshold_spin.setDecimals(2)
        self._score_threshold_spin.setValue(ai_provider.get_resume_score_threshold())
        self._score_threshold_spin.setFixedWidth(80)
        score_row.addWidget(self._score_threshold_spin)
        score_row.addStretch()
        rc_layout.addLayout(score_row)

        output_dir_row = QHBoxLayout()
        output_dir_row.setSpacing(12)
        output_dir_row.addWidget(_label("Output folder"))
        self._output_dir_edit = QLineEdit()
        self._output_dir_edit.setText(str(app_settings.get_resume_output_dir()))
        output_dir_row.addWidget(self._output_dir_edit, stretch=1)
        browse_btn = _secondary_btn("Browse…", width=100)
        browse_btn.clicked.connect(self._browse_output_dir)
        output_dir_row.addWidget(browse_btn)
        rc_layout.addLayout(output_dir_row)

        output_dir_hint = QLabel(
            "Default: ~/Documents/Resumes/. Folder is created automatically."
        )
        output_dir_hint.setWordWrap(True)
        output_dir_hint.setObjectName("hint")
        rc_layout.addWidget(output_dir_hint)

        self._resume_template_edit = QPlainTextEdit()
        self._resume_template_edit.setFont(mono)
        self._resume_template_edit.setMinimumHeight(280)
        self._resume_template_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self._resume_template_edit.setPlaceholderText(
            "Paste a LaTeX resume template here (e.g. Jake's Resume Template)…"
        )
        self._resume_template_edit.setPlainText(ai_provider.get_resume_template())
        rc_layout.addWidget(self._resume_template_edit)

        rt_btn_row = QHBoxLayout()
        rt_btn_row.setSpacing(12)
        rt_save_btn = _primary_btn("Save", width=100)
        rt_save_btn.clicked.connect(self._save_resume_template)
        self._resume_template_status = QLabel("")
        self._resume_template_status.setObjectName("status-ok")
        rt_btn_row.addWidget(rt_save_btn)
        rt_btn_row.addWidget(self._resume_template_status)
        rt_btn_row.addStretch()
        rc_layout.addLayout(rt_btn_row)

        return self._wrap_scroll(resume_card)

    def _browse_output_dir(self) -> None:
        current = self._output_dir_edit.text().strip() or str(app_settings.get_resume_output_dir())
        chosen = QFileDialog.getExistingDirectory(self, "Select resume output folder", current)
        if chosen:
            self._output_dir_edit.setText(chosen)

    def _save_resume_template(self) -> None:
        ai_provider.save_resume_template(self._resume_template_edit.toPlainText())
        ai_provider.save_resume_page_cap(self._page_cap_spin.value())
        ai_provider.save_max_generation_attempts(self._max_iters_spin.value())
        ai_provider.save_resume_score_threshold(self._score_threshold_spin.value())
        app_settings.save_resume_output_dir(self._output_dir_edit.text())
        _set_status(self._resume_template_status, "ok")
        self._resume_template_status.setText("✓  Saved")
        QTimer.singleShot(3000, lambda: self._resume_template_status.setText(""))
        if self._status_bar:
            self._status_bar.showMessage("✓  Resume template saved.", 3000)
