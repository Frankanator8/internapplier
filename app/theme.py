from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from api import ai_provider

from .style import DARK_STYLESHEET, LIGHT_STYLESHEET


def current_effective_theme(mode: str) -> str:
    if mode == "dark":
        return "dark"
    if mode == "light":
        return "light"
    app = QApplication.instance()
    if app is not None:
        try:
            if app.styleHints().colorScheme() == Qt.ColorScheme.Dark:
                return "dark"
        except (AttributeError, RuntimeError):
            pass
    return "light"


def apply_theme(app: QApplication, mode: str) -> None:
    effective = current_effective_theme(mode)
    sheet = DARK_STYLESHEET if effective == "dark" else LIGHT_STYLESHEET
    app.setStyleSheet(sheet)


def install_system_listener(app: QApplication) -> None:
    hints = app.styleHints()
    signal = getattr(hints, "colorSchemeChanged", None)
    if signal is None:
        return

    def _on_change(_scheme) -> None:
        if ai_provider.get_theme_preference() == "system":
            apply_theme(app, "system")

    signal.connect(_on_change)
