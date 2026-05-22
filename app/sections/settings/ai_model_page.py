from __future__ import annotations

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout, QWidget,
)

from api import ai_provider

from ..base import _label, _primary_btn


class AiModelMixin:
    def _build_ai_model_page(self) -> QWidget:
        card = QFrame()
        card.setObjectName("card")
        card.setMaximumWidth(560)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 24, 28, 28)
        card_layout.setSpacing(20)

        title = QLabel("AI Model Settings")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #0a66c2;")
        card_layout.addWidget(title)

        config = ai_provider._load_model_config()

        self._basic_edit = QLineEdit()
        self._basic_edit.setText(config.get("basic", ai_provider.DEFAULT_BASIC_MODEL))
        self._basic_edit.setPlaceholderText(ai_provider.DEFAULT_BASIC_MODEL)
        self._resize_edit(self._basic_edit, self._basic_edit.text())
        self._basic_edit.textChanged.connect(lambda t: self._resize_edit(self._basic_edit, t))

        self._fast_edit = QLineEdit()
        self._fast_edit.setText(config.get("fast", ai_provider.DEFAULT_FAST_MODEL))
        self._fast_edit.setPlaceholderText(ai_provider.DEFAULT_FAST_MODEL)
        self._resize_edit(self._fast_edit, self._fast_edit.text())
        self._fast_edit.textChanged.connect(lambda t: self._resize_edit(self._fast_edit, t))

        self._powerful_edit = QLineEdit()
        self._powerful_edit.setText(config.get("powerful", ai_provider.DEFAULT_POWERFUL_MODEL))
        self._powerful_edit.setPlaceholderText(ai_provider.DEFAULT_POWERFUL_MODEL)
        self._resize_edit(self._powerful_edit, self._powerful_edit.text())
        self._powerful_edit.textChanged.connect(lambda t: self._resize_edit(self._powerful_edit, t))

        def _sep() -> QFrame:
            s = QFrame()
            s.setFrameShape(QFrame.Shape.HLine)
            s.setStyleSheet("color: #e0e0e0;")
            return s

        card_layout.addWidget(self._build_model_section(
            section_label="Basic model",
            line_edit=self._basic_edit,
            capabilities=["Streaming", "Text generation"],
            used_for=["Bullet analysis", "Answer questions", "Interview chat", "Interview notes"],
        ))

        card_layout.addWidget(_sep())

        card_layout.addWidget(self._build_model_section(
            section_label="Fast model",
            line_edit=self._fast_edit,
            capabilities=["Streaming", "JSON output"],
            used_for=["Company research", "Interview grading"],
        ))

        card_layout.addWidget(_sep())

        card_layout.addWidget(self._build_model_section(
            section_label="Powerful model",
            line_edit=self._powerful_edit,
            capabilities=["Streaming", "Tool / function calling", "Agentic loop (4 rounds)"],
            used_for=["Resume generation", "Resume grading"],
        ))

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        save_btn = _primary_btn("Save", width=100)
        save_btn.clicked.connect(self._save_model_config)
        self._inline_status = QLabel("")
        self._inline_status.setStyleSheet("font-size: 12px; color: #057642;")
        btn_row.addWidget(save_btn)
        btn_row.addWidget(self._inline_status)
        btn_row.addStretch()
        card_layout.addLayout(btn_row)

        return self._wrap_scroll(card)

    def _build_model_section(
        self,
        section_label: str,
        line_edit: QLineEdit,
        capabilities: list[str],
        used_for: list[str],
    ) -> QWidget:
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        layout.addWidget(_label(section_label))

        input_row = QHBoxLayout()
        input_row.setSpacing(0)
        input_row.addWidget(line_edit)
        input_row.addStretch()
        layout.addLayout(input_row)

        cap_row = QHBoxLayout()
        cap_row.setSpacing(6)
        req_label = QLabel("Required:")
        req_label.setStyleSheet("font-size: 11px; color: #555555; font-weight: 600;")
        cap_row.addWidget(req_label)
        for cap in capabilities:
            cap_row.addWidget(self._make_capability_chip(cap))
        cap_row.addStretch()
        layout.addLayout(cap_row)

        used_row = QHBoxLayout()
        used_row.setSpacing(6)
        used_label = QLabel("Used for:")
        used_label.setStyleSheet("font-size: 11px; color: #555555; font-weight: 600;")
        used_row.addWidget(used_label)
        used_val = QLabel(", ".join(used_for))
        used_val.setStyleSheet("font-size: 12px; color: #666;")
        used_row.addWidget(used_val)
        used_row.addStretch()
        layout.addLayout(used_row)

        return container

    @staticmethod
    def _make_capability_chip(text: str) -> QFrame:
        chip = QFrame()
        chip.setStyleSheet(
            "QFrame { background: #e8f0fb; border: none; border-radius: 10px; }"
            "QLabel { color: #0a66c2; font-size: 11px; font-weight: 600;"
            " background: transparent; }"
        )
        layout = QHBoxLayout(chip)
        layout.setContentsMargins(8, 3, 8, 3)
        layout.setSpacing(0)
        layout.addWidget(QLabel(text))
        chip.setFixedHeight(22)
        return chip

    def _save_model_config(self):
        basic = self._basic_edit.text().strip()
        fast = self._fast_edit.text().strip()
        powerful = self._powerful_edit.text().strip()
        if not basic or not fast or not powerful:
            self._inline_status.setStyleSheet("font-size: 12px; color: #b00;")
            self._inline_status.setText("All three models are required.")
            return

        ai_provider.save_model_config(basic, fast, powerful)

        self._inline_status.setStyleSheet("font-size: 12px; color: #057642;")
        self._inline_status.setText("✓  Saved")
        QTimer.singleShot(3000, lambda: self._inline_status.setText(""))

        if self._status_bar:
            self._status_bar.showMessage("✓  Model settings saved.", 3000)
