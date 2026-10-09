from __future__ import annotations

from typing import Callable

from PyQt6.QtWidgets import (
    QApplication, QComboBox, QHBoxLayout, QPlainTextEdit, QSpinBox, QStatusBar,
)

from api import app_settings
from app.theme import apply_theme
from app.ui.widgets import hint, label, set_status

from .common import SettingsCard, SettingsPane

_THEME_OPTIONS = [("System", "system"), ("Light", "light"), ("Dark", "dark")]


class GeneralSettings(SettingsPane):
    def __init__(self, status_bar: QStatusBar, on_heatmap_thresholds_changed: Callable[[], None]):
        super().__init__(status_bar)
        self._on_heatmap_thresholds_changed = on_heatmap_thresholds_changed
        card = SettingsCard("General")
        layout = card.body

        layout.addWidget(label("Appearance"))
        self._theme_combo = QComboBox()
        for label_text, value in _THEME_OPTIONS:
            self._theme_combo.addItem(label_text, value)
        self._theme_combo.setCurrentIndex(max(self._theme_combo.findData(app_settings.get_theme_preference()), 0))
        self._theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        theme_row = QHBoxLayout()
        theme_row.addWidget(self._theme_combo)
        theme_row.addStretch()
        layout.addLayout(theme_row)
        layout.addWidget(hint("Choose Light, Dark, or follow your system setting."))

        layout.addWidget(label("Writing sample"))
        self._writing_sample_edit = QPlainTextEdit()
        self._writing_sample_edit.setMinimumHeight(140)
        self._writing_sample_edit.setPlaceholderText(
            "Paste a paragraph or two you've actually written (a cover-letter "
            "excerpt, a personal-statement passage, a project description in "
            "your own words). The AI mirrors its rhythm and vocabulary when "
            "drafting answers, so they sound like you."
        )
        self._writing_sample_edit.setPlainText(app_settings.get_writing_sample())
        layout.addWidget(self._writing_sample_edit)
        layout.addWidget(hint(
            "Optional. When provided, Answer Question matches this sample's "
            "register and sentence rhythm. Leave blank to skip."
        ))

        layout.addWidget(label("Scraper paths (one per line)"))
        self._scraper_paths_edit = QPlainTextEdit()
        self._scraper_paths_edit.setMinimumHeight(180)
        self._scraper_paths_edit.setPlaceholderText("/about\n/careers\n…")
        self._scraper_paths_edit.setPlainText("\n".join(app_settings.get_scraper_candidate_paths()))
        layout.addWidget(self._scraper_paths_edit)
        layout.addWidget(hint("Relative URL paths the company researcher crawls to gather context."))

        layout.addWidget(label("Heatmap thresholds", "settings-subheading"))
        layout.addWidget(hint(
            "Application count at which each cell darkens to the next shade. "
            "Values must be strictly ascending."
        ))
        self._heatmap_spins: dict[str, list[QSpinBox]] = {}
        for key, row_label, values in (
            ("Daily", "Daily cutoffs", app_settings.get_heatmap_day_thresholds()),
            ("Weekly", "Weekly cutoffs", app_settings.get_heatmap_week_thresholds()),
        ):
            layout.addLayout(self._threshold_row(key, row_label, values))

        row, self._status = self._save_row(self._save)
        layout.addLayout(row)
        self._set_cards(card)

    def _threshold_row(self, key: str, row_label: str, values: list[int]) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        name = label(row_label, "")
        name.setFixedWidth(120)
        row.addWidget(name)
        spins = self._heatmap_spins[key] = []
        for v in values:
            spin = QSpinBox()
            spin.setRange(1, 999)
            spin.setValue(int(v))
            spin.setFixedWidth(70)
            spins.append(spin)
            row.addWidget(spin)
        row.addStretch()
        return row

    def _on_theme_changed(self, _index: int) -> None:
        mode = self._theme_combo.currentData()
        if not isinstance(mode, str):
            return
        app_settings.save_theme_preference(mode)
        app = QApplication.instance()
        if app is not None:
            apply_theme(app, mode)

    def _save(self) -> None:
        values = {key: [s.value() for s in spins] for key, spins in self._heatmap_spins.items()}
        for key, vals in values.items():
            if app_settings.valid_thresholds(vals) is None:
                set_status(self._status, "error", f"✗  {key} cutoffs must be strictly ascending.")
                return

        paths = [
            line.strip()
            for line in self._scraper_paths_edit.toPlainText().splitlines()
            if line.strip()
        ]
        app_settings.save_scraper_candidate_paths(paths)
        app_settings.save_writing_sample(self._writing_sample_edit.toPlainText())
        app_settings.save_heatmap_day_thresholds(values["Daily"])
        app_settings.save_heatmap_week_thresholds(values["Weekly"])
        self._on_heatmap_thresholds_changed()
        self._announce(self._status, "✓  General settings saved.")
