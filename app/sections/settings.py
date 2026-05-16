from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QFrame, QLineEdit, QLabel, QStatusBar,
)
from PyQt6.QtCore import QTimer

from .. import ai_provider
from .base import _label, _primary_btn


class SettingsPage(QWidget):
    def __init__(self, status_bar: QStatusBar | None = None):
        super().__init__()
        self._status_bar = status_bar

        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 40, 40, 40)
        outer.setSpacing(0)

        card = QFrame()
        card.setObjectName("card")
        card.setMaximumWidth(560)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 24, 28, 28)
        card_layout.setSpacing(20)

        title = QLabel("AI Model Settings")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #0a66c2;")
        card_layout.addWidget(title)

        hint = QLabel(
            'Enter any model ID available on <a href="https://openrouter.ai/models">'
            'openrouter.ai/models</a>.'
        )
        hint.setOpenExternalLinks(True)
        hint.setWordWrap(True)
        hint.setStyleSheet("font-size: 12px; color: #666;")
        card_layout.addWidget(hint)

        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(form.labelAlignment())

        config = ai_provider._load_model_config()

        self._fast_edit = QLineEdit()
        self._fast_edit.setText(config.get("fast", ai_provider.DEFAULT_FAST_MODEL))
        self._fast_edit.setPlaceholderText(ai_provider.DEFAULT_FAST_MODEL)
        self._fast_edit.setMinimumWidth(300)

        self._powerful_edit = QLineEdit()
        self._powerful_edit.setText(config.get("powerful", ai_provider.DEFAULT_POWERFUL_MODEL))
        self._powerful_edit.setPlaceholderText(ai_provider.DEFAULT_POWERFUL_MODEL)

        fast_label = _label("Fast model")
        powerful_label = _label("Powerful model")
        form.addRow(fast_label, self._fast_edit)
        form.addRow(powerful_label, self._powerful_edit)
        card_layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        save_btn = _primary_btn("Save", width=100)
        save_btn.clicked.connect(self._save)
        self._inline_status = QLabel("")
        self._inline_status.setStyleSheet("font-size: 12px; color: #057642;")
        btn_row.addWidget(save_btn)
        btn_row.addWidget(self._inline_status)
        btn_row.addStretch()
        card_layout.addLayout(btn_row)

        outer.addWidget(card)
        outer.addStretch()

    def _save(self):
        fast = self._fast_edit.text().strip()
        powerful = self._powerful_edit.text().strip()
        if not fast or not powerful:
            self._inline_status.setStyleSheet("font-size: 12px; color: #b00;")
            self._inline_status.setText("Both fields are required.")
            return

        ai_provider.save_model_config(fast, powerful)

        self._inline_status.setStyleSheet("font-size: 12px; color: #057642;")
        self._inline_status.setText("✓  Saved")
        QTimer.singleShot(3000, lambda: self._inline_status.setText(""))

        if self._status_bar:
            self._status_bar.showMessage("✓  Model settings saved.", 3000)
