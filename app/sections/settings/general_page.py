from __future__ import annotations

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QSpinBox, QVBoxLayout, QWidget,
)

from api import ai_provider

from ..base import _label, _primary_btn


class GeneralMixin:
    def _build_general_page(self) -> QWidget:
        card = QFrame()
        card.setObjectName("card")
        card.setMaximumWidth(800)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(16)

        title = QLabel("General")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #0a66c2;")
        layout.addWidget(title)

        port_row = QHBoxLayout()
        port_row.setSpacing(12)
        port_row.addWidget(_label("Server port"))
        self._server_port_spin = QSpinBox()
        self._server_port_spin.setMinimum(1)
        self._server_port_spin.setMaximum(65535)
        self._server_port_spin.setValue(ai_provider.get_server_port())
        self._server_port_spin.setFixedWidth(100)
        port_row.addWidget(self._server_port_spin)
        port_row.addStretch()
        layout.addLayout(port_row)

        port_hint = QLabel(
            f"Default: {ai_provider.DEFAULT_SERVER_PORT}. Restart the app for changes to take effect."
        )
        port_hint.setWordWrap(True)
        port_hint.setStyleSheet("font-size: 12px; color: #666;")
        layout.addWidget(port_hint)

        layout.addWidget(_label("Scraper paths (one per line)"))
        self._scraper_paths_edit = QPlainTextEdit()
        self._scraper_paths_edit.setMinimumHeight(180)
        self._scraper_paths_edit.setPlaceholderText("/about\n/careers\n…")
        self._scraper_paths_edit.setPlainText(
            "\n".join(ai_provider.get_scraper_candidate_paths())
        )
        layout.addWidget(self._scraper_paths_edit)

        paths_hint = QLabel(
            "Relative URL paths the company researcher crawls to gather context."
        )
        paths_hint.setWordWrap(True)
        paths_hint.setStyleSheet("font-size: 12px; color: #666;")
        layout.addWidget(paths_hint)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        save_btn = _primary_btn("Save", width=100)
        save_btn.clicked.connect(self._save_general)
        self._general_status = QLabel("")
        self._general_status.setStyleSheet("font-size: 12px; color: #057642;")
        btn_row.addWidget(save_btn)
        btn_row.addWidget(self._general_status)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        return self._wrap_scroll(card)

    def _save_general(self) -> None:
        ai_provider.save_server_port(self._server_port_spin.value())
        paths = [
            line.strip()
            for line in self._scraper_paths_edit.toPlainText().splitlines()
            if line.strip()
        ]
        ai_provider.save_scraper_candidate_paths(paths)
        self._general_status.setStyleSheet("font-size: 12px; color: #057642;")
        self._general_status.setText("✓  Saved")
        QTimer.singleShot(3000, lambda: self._general_status.setText(""))
        if self._status_bar:
            self._status_bar.showMessage("✓  General settings saved.", 3000)
