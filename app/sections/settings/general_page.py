from __future__ import annotations

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QFrame, QHBoxLayout, QLabel, QPlainTextEdit,
    QSpinBox, QVBoxLayout, QWidget,
)

from api import ai_provider

from app.theme import apply_theme

from ..base import _label, _primary_btn

_THEME_OPTIONS = [("System", "system"), ("Light", "light"), ("Dark", "dark")]


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

        layout.addWidget(_label("Appearance"))
        self._theme_combo = QComboBox()
        for label_text, value in _THEME_OPTIONS:
            self._theme_combo.addItem(label_text, value)
        current_pref = ai_provider.get_theme_preference()
        for i, (_, value) in enumerate(_THEME_OPTIONS):
            if value == current_pref:
                self._theme_combo.setCurrentIndex(i)
                break
        self._theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        theme_row = QHBoxLayout()
        theme_row.addWidget(self._theme_combo)
        theme_row.addStretch()
        layout.addLayout(theme_row)

        theme_hint = QLabel(
            "Choose Light, Dark, or follow your system setting."
        )
        theme_hint.setWordWrap(True)
        theme_hint.setStyleSheet("font-size: 12px; color: #666;")
        layout.addWidget(theme_hint)

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

        heatmap_title = QLabel("Heatmap thresholds")
        heatmap_title.setStyleSheet("font-size: 14px; font-weight: bold; margin-top: 12px;")
        layout.addWidget(heatmap_title)

        heatmap_hint = QLabel(
            "Application count at which each cell darkens to the next shade. "
            "Values must be strictly ascending."
        )
        heatmap_hint.setWordWrap(True)
        heatmap_hint.setStyleSheet("font-size: 12px; color: #666;")
        layout.addWidget(heatmap_hint)

        day_values = ai_provider.get_heatmap_day_thresholds()
        week_values = ai_provider.get_heatmap_week_thresholds()
        self._heatmap_day_spins: list[QSpinBox] = []
        self._heatmap_week_spins: list[QSpinBox] = []

        def _row(label_text: str, values: list[int], target: list[QSpinBox]) -> QHBoxLayout:
            row = QHBoxLayout()
            row.setSpacing(8)
            row_label = QLabel(label_text)
            row_label.setFixedWidth(120)
            row.addWidget(row_label)
            for v in values:
                spin = QSpinBox()
                spin.setRange(1, 999)
                spin.setValue(int(v))
                spin.setFixedWidth(70)
                target.append(spin)
                row.addWidget(spin)
            row.addStretch()
            return row

        layout.addLayout(_row("Daily cutoffs", day_values, self._heatmap_day_spins))
        layout.addLayout(_row("Weekly cutoffs", week_values, self._heatmap_week_spins))

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

    def _on_theme_changed(self, _index: int) -> None:
        mode = self._theme_combo.currentData()
        if not isinstance(mode, str):
            return
        ai_provider.save_theme_preference(mode)
        app = QApplication.instance()
        if app is not None:
            apply_theme(app, mode)

    def _save_general(self) -> None:
        day_vals = [s.value() for s in self._heatmap_day_spins]
        week_vals = [s.value() for s in self._heatmap_week_spins]
        for vals, name in ((day_vals, "Daily"), (week_vals, "Weekly")):
            if not all(vals[i] < vals[i + 1] for i in range(len(vals) - 1)):
                self._general_status.setStyleSheet("font-size: 12px; color: #b00020;")
                self._general_status.setText(f"✗  {name} cutoffs must be strictly ascending.")
                return

        paths = [
            line.strip()
            for line in self._scraper_paths_edit.toPlainText().splitlines()
            if line.strip()
        ]
        ai_provider.save_scraper_candidate_paths(paths)
        ai_provider.save_heatmap_day_thresholds(day_vals)
        ai_provider.save_heatmap_week_thresholds(week_vals)

        cb = getattr(self, "_on_heatmap_thresholds_changed", None)
        if callable(cb):
            try:
                cb()
            except Exception:
                pass

        self._general_status.setStyleSheet("font-size: 12px; color: #057642;")
        self._general_status.setText("✓  Saved")
        QTimer.singleShot(3000, lambda: self._general_status.setText(""))
        if self._status_bar:
            self._status_bar.showMessage("✓  General settings saved.", 3000)
