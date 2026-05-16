from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextBrowser, QFrame,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QClipboard, QGuiApplication


class AnalyzeDialog(QDialog):
    def __init__(self, bullet: str, result: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI Analysis")
        self.setMinimumWidth(540)
        self.setMinimumHeight(360)
        self.resize(560, 420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Original bullet quote
        quote_frame = QFrame()
        quote_frame.setObjectName("analyze-quote")
        quote_layout = QVBoxLayout(quote_frame)
        quote_layout.setContentsMargins(12, 10, 12, 10)

        quote_label = QLabel("Original bullet")
        quote_label.setObjectName("analyze-quote-title")
        quote_layout.addWidget(quote_label)

        bullet_label = QLabel(bullet)
        bullet_label.setObjectName("analyze-bullet-text")
        bullet_label.setWordWrap(True)
        quote_layout.addWidget(bullet_label)

        layout.addWidget(quote_frame)

        # AI result
        result_label = QLabel("AI Analysis")
        result_label.setObjectName("analyze-result-title")
        layout.addWidget(result_label)

        self._browser = QTextBrowser()
        self._browser.setObjectName("analyze-browser")
        self._browser.setPlainText(result)
        self._browser.setOpenExternalLinks(False)
        layout.addWidget(self._browser, stretch=1)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        copy_btn = QPushButton("Copy Analysis")
        copy_btn.setObjectName("secondary")
        copy_btn.clicked.connect(self._copy_result)
        btn_row.addWidget(copy_btn)

        close_btn = QPushButton("Close")
        close_btn.setObjectName("primary")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)

        self._result = result

    def _copy_result(self):
        QGuiApplication.clipboard().setText(self._result)
