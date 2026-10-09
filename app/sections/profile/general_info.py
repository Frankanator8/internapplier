from __future__ import annotations

from typing import Union

from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QWidget

from api.constants import COMBO_FIELDS, LINE_FIELDS
from app.ui.widgets import field, group_card, line_edit, page_layout, scroll_area, section_header

YES_NO = ["", "No", "Yes"]

# A field is (key, label, placeholder) for a line edit, or (key, label, options)
# for a combo. Each group is a titled card of rows.
_Field = tuple[str, str, Union[str, list[str]]]
_LAYOUT: list[tuple[str, list[list[_Field]]]] = [
    ("Identity", [
        [("first_name", "First Name", "Jane"), ("last_name", "Last Name", "Doe")],
        [("preferred_name", "Preferred Name", "Optional"),
         ("pronouns", "Pronouns", "she/her, he/him, they/them…")],
    ]),
    ("Contact", [
        [("email", "Email", "jane@example.com"), ("phone", "Phone", "+1 (555) 555-5555")],
        [("address1", "Address Line 1", "123 Main St")],
        [("address2", "Address Line 2", "Apt 4B (optional)")],
        [("city", "City", "Berkeley"), ("state", "State / Province", "CA"),
         ("postal_code", "Postal Code", "94704"), ("country", "Country", "United States")],
        [("linkedin", "LinkedIn URL", "https://linkedin.com/in/…")],
        [("website", "Portfolio / Website", "https://yoursite.com"),
         ("github", "GitHub URL", "https://github.com/…")],
    ]),
    ("Work Authorization & Status", [
        [("employment_status", "Current Employment Status",
          ["", "Student", "Employed", "Unemployed", "Self-employed", "Other"]),
         ("work_authorization", "US Work Authorization",
          ["", "US Citizen", "Permanent Resident", "Visa Holder", "Require Sponsorship", "Other"])],
        [("require_sponsorship", "Require Visa Sponsorship?", YES_NO),
         ("willing_to_relocate", "Willing to Relocate?", ["", "Yes", "No", "Open to discussion"])],
        [("earliest_start_date", "Earliest Start Date", "e.g., June 2026 or Immediately"),
         ("desired_salary", "Desired Salary", "e.g., $90,000 / year or $35 / hour")],
    ]),
    ("EEO / Voluntary Self-Identification (Optional)", [
        [("gender", "Gender", ["", "Female", "Male", "Non-binary", "Other", "Prefer not to say"]),
         ("ethnicity", "Race / Ethnicity", [
             "",
             "American Indian or Alaska Native",
             "Asian",
             "Black or African American",
             "Hispanic or Latino",
             "Native Hawaiian or Other Pacific Islander",
             "White",
             "Two or More Races",
             "Other",
             "Prefer not to say",
         ])],
        [("veteran_status", "Veteran Status",
          ["", "I am not a veteran", "I am a veteran", "Prefer not to say"]),
         ("disability_status", "Disability Status",
          ["", "No, I do not have a disability", "Yes, I have a disability", "Prefer not to say"])],
        [("date_of_birth", "Date of Birth", "YYYY-MM-DD (optional)")],
    ]),
]


class GeneralInfoPage(QWidget):
    """Contact, work-authorization and EEO fields — a flat dict of strings."""

    def __init__(self, parent=None):
        super().__init__(parent)
        outer = page_layout(self)
        outer.addLayout(section_header("General Info"))
        scroll, layout = scroll_area()
        outer.addWidget(scroll)

        self._lines = {}
        self._combos = {}
        for title, rows in _LAYOUT:
            frame, vbox = group_card(title)
            for fields in rows:
                row = QHBoxLayout()
                row.setSpacing(16)
                for key, label_text, spec in fields:
                    if isinstance(spec, list):
                        widget = self._combos[key] = QComboBox()
                        widget.addItems(spec)
                    else:
                        widget = self._lines[key] = line_edit(spec)
                    row.addLayout(field(label_text, widget))
                vbox.addLayout(row)
            layout.addWidget(frame)

        assert set(self._lines) == set(LINE_FIELDS) and set(self._combos) == set(COMBO_FIELDS)

    # ── Profile section interface ───────────────────────────────
    def load(self, data: dict | None) -> None:
        data = data or {}
        for key, edit in self._lines.items():
            edit.setText(data.get(key, ""))
        for key, combo in self._combos.items():
            # Unknown values fall back to the blank option.
            combo.setCurrentIndex(max(combo.findText(data.get(key, "")), 0))

    def merge(self, imported: dict | None, mode: str) -> None:
        """Overlay imported values; ``append`` only fills fields that are blank.

        Never clears: even in replace mode, fields the import lacks are kept.
        """
        if not imported:
            return
        current = self.get_data()
        if mode == "replace":
            merged = {**current, **imported}
        else:
            merged = {**imported, **{k: v for k, v in current.items() if v}}
        self.load(merged)

    def clear(self) -> None:
        self.load({})

    def has_data(self) -> bool:
        return any(self.get_data().values())

    def get_data(self) -> dict:
        data = {key: self._lines[key].text() for key in LINE_FIELDS}
        data.update({key: self._combos[key].currentText() for key in COMBO_FIELDS})
        return data
