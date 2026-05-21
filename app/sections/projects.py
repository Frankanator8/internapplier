from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout
from .base import (
    CardPage, BulletsWidget, ChipsWidget, make_field, make_line_edit,
    add_remove_footer, attach_fields,
)


class ProjectsPage(CardPage):
    section_title = "Projects"
    add_label = "+ Add Project"

    def add_entry(self, data: dict | None = None):
        data = data or {}
        card = self._make_card()
        vbox = QVBoxLayout(card)
        vbox.setContentsMargins(20, 18, 20, 16)
        vbox.setSpacing(12)

        name = make_line_edit("My Awesome Project")
        url = make_line_edit("https://github.com/…  (optional)")
        start = make_line_edit("Jun 2024")
        end = make_line_edit("Aug 2024")

        name.setText(data.get("name", ""))
        url.setText(data.get("url", ""))
        start.setText(data.get("start", ""))
        end.setText(data.get("end", ""))

        row1 = QHBoxLayout()
        row1.setSpacing(16)
        row1.addLayout(make_field("Project Name", name), 2)
        row1.addLayout(make_field("URL", url), 2)
        vbox.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(16)
        row2.addLayout(make_field("Start Date", start))
        row2.addLayout(make_field("End Date", end))
        row2.addStretch(2)
        vbox.addLayout(row2)

        bullets = BulletsWidget(
            data.get("bullets", []),
            get_context=lambda: {"type": "project", "name": name.text()},
        )
        vbox.addWidget(bullets)

        skills = ChipsWidget(
            data.get("skills", []),
            on_add=lambda s: self.on_skill_added and self.on_skill_added(s),
            get_common_skills=self.get_common_skills,
        )
        vbox.addWidget(skills)

        add_remove_footer(vbox, lambda: self._remove_card(card))

        attach_fields(card, {
            "name": name, "url": url, "start": start, "end": end,
            "bullets": bullets, "skills": skills,
        })
        self._cards_layout.addWidget(card)
