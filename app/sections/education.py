from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout
from .base import CardPage, BulletsWidget, ChipsWidget, CoursesWidget, make_field, make_line_edit


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

        skills = ChipsWidget(
            data.get("skills", []),
            on_add=lambda s: self.on_skill_added and self.on_skill_added(s),
            get_common_skills=self.get_common_skills,
        )
        vbox.addWidget(skills)

        courses = CoursesWidget(
            data.get("courses", []),
            get_common_skills=self.get_common_skills,
        )
        vbox.addWidget(courses)

        footer = QHBoxLayout()
        footer.addStretch()
        footer.addWidget(self._make_remove_btn(card))
        vbox.addLayout(footer)

        card.setProperty("_school", school)
        card.setProperty("_degree", degree)
        card.setProperty("_start", start)
        card.setProperty("_end", end)
        card.setProperty("_gpa", gpa)
        card.setProperty("_bullets", bullets)
        card.setProperty("_skills", skills)
        card.setProperty("_courses", courses)

        self._cards_layout.addWidget(card)

    def get_data(self) -> list[dict]:
        result = []
        for i in range(self._cards_layout.count()):
            card = self._cards_layout.itemAt(i).widget()
            if card is None:
                continue
            result.append({
                "school": card.property("_school").text(),
                "degree": card.property("_degree").text(),
                "start": card.property("_start").text(),
                "end": card.property("_end").text(),
                "gpa": card.property("_gpa").text(),
                "bullets": card.property("_bullets").get_bullets(),
                "skills": card.property("_skills").get_items(),
                "courses": card.property("_courses").get_courses(),
            })
        return result
