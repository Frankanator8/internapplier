from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout
from .base import (
    CardPage, BulletsWidget, CoursesWidget, make_field, make_line_edit,
    add_remove_footer, attach_fields,
)


class EducationPage(CardPage):
    section_title = "Education"
    add_label = "+ Add Education"

    def add_entry(self, data: dict | None = None):
        data = data or {}
        card = self._make_card()
        vbox = QVBoxLayout(card)
        vbox.setContentsMargins(20, 18, 20, 16)
        vbox.setSpacing(12)

        school = make_line_edit("University of California, Berkeley")
        degree = make_line_edit("B.S. Computer Science")
        start = make_line_edit("Aug 2022")
        end = make_line_edit("May 2026")
        gpa = make_line_edit("3.9 / 4.0  (optional)")

        school.setText(data.get("school", ""))
        degree.setText(data.get("degree", ""))
        start.setText(data.get("start", ""))
        end.setText(data.get("end", ""))
        gpa.setText(data.get("gpa", ""))

        row1 = QHBoxLayout()
        row1.setSpacing(16)
        row1.addLayout(make_field("School", school), 3)
        row1.addLayout(make_field("Degree", degree), 3)
        vbox.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(16)
        row2.addLayout(make_field("Start Date", start))
        row2.addLayout(make_field("End Date", end))
        row2.addLayout(make_field("GPA", gpa))
        vbox.addLayout(row2)

        bullets = BulletsWidget(
            data.get("bullets", []),
            get_context=lambda: {
                "type": "education",
                "school": school.text(),
                "degree": degree.text(),
            },
        )
        vbox.addWidget(bullets)

        courses = CoursesWidget(
            data.get("courses", []),
            get_common_skills=self.get_common_skills,
        )
        vbox.addWidget(courses)

        add_remove_footer(vbox, lambda: self._remove_card(card))

        attach_fields(card, {
            "school": school, "degree": degree,
            "start": start, "end": end, "gpa": gpa,
            "bullets": bullets, "courses": courses,
        })
        self._cards_layout.addWidget(card)
