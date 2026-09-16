from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication

from api import app_settings

from .style import PALETTE, build_stylesheet

_applied_mode: str | None = None


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


def current_palette() -> dict[str, str]:
    mode = _applied_mode or current_effective_theme(app_settings.get_theme_preference())
    return PALETTE.get(mode, PALETTE["light"])


def _build_palette(colors: dict[str, str]) -> QPalette:
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor(colors["bg"]))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(colors["text"]))
    pal.setColor(QPalette.ColorRole.Base, QColor(colors["surface_input"]))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor(colors["surface_alt"]))
    pal.setColor(QPalette.ColorRole.Text, QColor(colors["text"]))
    pal.setColor(QPalette.ColorRole.Button, QColor(colors["surface_card"]))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(colors["text"]))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(colors["accent"]))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(colors["on_accent"]))
    pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(colors["placeholder"]))
    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor(colors["surface_card"]))
    pal.setColor(QPalette.ColorRole.ToolTipText, QColor(colors["text"]))
    pal.setColor(QPalette.ColorRole.Link, QColor(colors["link"]))
    pal.setColor(QPalette.ColorRole.BrightText, QColor(colors["status_error"]))
    return pal


def apply_theme(app: QApplication, mode: str) -> None:
    global _applied_mode
    effective = current_effective_theme(mode)
    _applied_mode = effective
    colors = PALETTE.get(effective, PALETTE["light"])
    app.setPalette(_build_palette(colors))
    app.setStyleSheet(build_stylesheet(effective))
    for widget in app.topLevelWidgets():
        widget.update()


def install_system_listener(app: QApplication) -> None:
    hints = app.styleHints()
    signal = getattr(hints, "colorSchemeChanged", None)
    if signal is None:
        return

    def _on_change(_scheme) -> None:
        if app_settings.get_theme_preference() == "system":
            apply_theme(app, "system")

    signal.connect(_on_change)
