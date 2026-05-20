from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QFrame, QComboBox,
)
from PyQt6.QtCore import Qt

from .base import _label, make_field, make_line_edit


def _make_combo(options: list[str]) -> QComboBox:
    combo = QComboBox()
    combo.addItems(options)
    return combo


def _group_card(title: str) -> tuple[QFrame, QVBoxLayout]:
    card = QFrame()
    card.setObjectName("card")
    vbox = QVBoxLayout(card)
    vbox.setContentsMargins(20, 18, 20, 18)
    vbox.setSpacing(12)
    heading = _label(title, "section-title")
    heading.setStyleSheet("font-size: 15px;")
    vbox.addWidget(heading)
    return card, vbox


class GeneralInfoPage(QWidget):
    section_title = "General Info"

    EMPLOYMENT_STATUS = ["", "Student", "Employed", "Unemployed", "Self-employed", "Other"]
    WORK_AUTH = ["", "US Citizen", "Permanent Resident", "Visa Holder", "Require Sponsorship", "Other"]
    YES_NO = ["", "No", "Yes"]
    RELOCATE = ["", "Yes", "No", "Open to discussion"]
    GENDER = ["", "Female", "Male", "Non-binary", "Other", "Prefer not to say"]
    ETHNICITY = [
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
    ]
    VETERAN = ["", "I am not a veteran", "I am a veteran", "Prefer not to say"]
    DISABILITY = ["", "No, I do not have a disability", "Yes, I have a disability", "Prefer not to say"]

    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 16)
        outer.setSpacing(14)

        header = QHBoxLayout()
        header.addWidget(_label(self.section_title, "section-title"))
        header.addStretch()
        outer.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setSpacing(14)
        layout.setContentsMargins(0, 0, 0, 16)
        scroll.setWidget(container)

        # ── Identity ─────────────────────────────────────────────
        card, vbox = _group_card("Identity")
        self.first_name = make_line_edit("Jane")
        self.last_name = make_line_edit("Doe")
        self.preferred_name = make_line_edit("Optional")
        self.pronouns = make_line_edit("she/her, he/him, they/them…")

        row = QHBoxLayout(); row.setSpacing(16)
        row.addLayout(make_field("First Name", self.first_name))
        row.addLayout(make_field("Last Name", self.last_name))
        vbox.addLayout(row)

        row = QHBoxLayout(); row.setSpacing(16)
        row.addLayout(make_field("Preferred Name", self.preferred_name))
        row.addLayout(make_field("Pronouns", self.pronouns))
        vbox.addLayout(row)
        layout.addWidget(card)

        # ── Contact ──────────────────────────────────────────────
        card, vbox = _group_card("Contact")
        self.email = make_line_edit("jane@example.com")
        self.phone = make_line_edit("+1 (555) 555-5555")
        self.address1 = make_line_edit("123 Main St")
        self.address2 = make_line_edit("Apt 4B (optional)")
        self.city = make_line_edit("Berkeley")
        self.state = make_line_edit("CA")
        self.postal_code = make_line_edit("94704")
        self.country = make_line_edit("United States")
        self.linkedin = make_line_edit("https://linkedin.com/in/…")
        self.website = make_line_edit("https://yoursite.com")
        self.github = make_line_edit("https://github.com/…")

        row = QHBoxLayout(); row.setSpacing(16)
        row.addLayout(make_field("Email", self.email))
        row.addLayout(make_field("Phone", self.phone))
        vbox.addLayout(row)

        vbox.addLayout(make_field("Address Line 1", self.address1))
        vbox.addLayout(make_field("Address Line 2", self.address2))

        row = QHBoxLayout(); row.setSpacing(16)
        row.addLayout(make_field("City", self.city))
        row.addLayout(make_field("State / Province", self.state))
        row.addLayout(make_field("Postal Code", self.postal_code))
        row.addLayout(make_field("Country", self.country))
        vbox.addLayout(row)

        vbox.addLayout(make_field("LinkedIn URL", self.linkedin))
        row = QHBoxLayout(); row.setSpacing(16)
        row.addLayout(make_field("Portfolio / Website", self.website))
        row.addLayout(make_field("GitHub URL", self.github))
        vbox.addLayout(row)
        layout.addWidget(card)

        # ── Work Authorization & Status ──────────────────────────
        card, vbox = _group_card("Work Authorization & Status")
        self.employment_status = _make_combo(self.EMPLOYMENT_STATUS)
        self.work_authorization = _make_combo(self.WORK_AUTH)
        self.require_sponsorship = _make_combo(self.YES_NO)
        self.willing_to_relocate = _make_combo(self.RELOCATE)
        self.earliest_start_date = make_line_edit("e.g., June 2026 or Immediately")
        self.desired_salary = make_line_edit("e.g., $90,000 / year or $35 / hour")

        row = QHBoxLayout(); row.setSpacing(16)
        row.addLayout(make_field("Current Employment Status", self.employment_status))
        row.addLayout(make_field("US Work Authorization", self.work_authorization))
        vbox.addLayout(row)

        row = QHBoxLayout(); row.setSpacing(16)
        row.addLayout(make_field("Require Visa Sponsorship?", self.require_sponsorship))
        row.addLayout(make_field("Willing to Relocate?", self.willing_to_relocate))
        vbox.addLayout(row)

        row = QHBoxLayout(); row.setSpacing(16)
        row.addLayout(make_field("Earliest Start Date", self.earliest_start_date))
        row.addLayout(make_field("Desired Salary", self.desired_salary))
        vbox.addLayout(row)
        layout.addWidget(card)

        # ── EEO / Voluntary Self-Identification ──────────────────
        card, vbox = _group_card("EEO / Voluntary Self-Identification (Optional)")
        self.gender = _make_combo(self.GENDER)
        self.ethnicity = _make_combo(self.ETHNICITY)
        self.veteran_status = _make_combo(self.VETERAN)
        self.disability_status = _make_combo(self.DISABILITY)
        self.date_of_birth = make_line_edit("YYYY-MM-DD (optional)")

        row = QHBoxLayout(); row.setSpacing(16)
        row.addLayout(make_field("Gender", self.gender))
        row.addLayout(make_field("Race / Ethnicity", self.ethnicity))
        vbox.addLayout(row)

        row = QHBoxLayout(); row.setSpacing(16)
        row.addLayout(make_field("Veteran Status", self.veteran_status))
        row.addLayout(make_field("Disability Status", self.disability_status))
        vbox.addLayout(row)

        vbox.addLayout(make_field("Date of Birth", self.date_of_birth))
        layout.addWidget(card)

    # Mapping of data keys → widget attribute names.
    _LINE_FIELDS = [
        "first_name", "last_name", "preferred_name", "pronouns",
        "email", "phone", "address1", "address2", "city", "state",
        "postal_code", "country", "linkedin", "website", "github",
        "earliest_start_date", "desired_salary", "date_of_birth",
    ]
    _COMBO_FIELDS = [
        "employment_status", "work_authorization", "require_sponsorship",
        "willing_to_relocate", "gender", "ethnicity", "veteran_status",
        "disability_status",
    ]

    def load(self, data: dict | None):
        data = data or {}
        for key in self._LINE_FIELDS:
            getattr(self, key).setText(data.get(key, ""))
        for key in self._COMBO_FIELDS:
            combo: QComboBox = getattr(self, key)
            value = data.get(key, "")
            idx = combo.findText(value)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            else:
                combo.setCurrentIndex(0)

    def get_data(self) -> dict:
        result: dict = {}
        for key in self._LINE_FIELDS:
            result[key] = getattr(self, key).text()
        for key in self._COMBO_FIELDS:
            result[key] = getattr(self, key).currentText()
        return result
