from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout
from .base import CardPage, BulletsWidget, ChipsWidget, make_field, make_line_edit


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
            get_context=lambda: {
                "type": "project",
                "name": name.text(),
            },
        )
        vbox.addWidget(bullets)

        skills = ChipsWidget(
            data.get("skills", []),
            on_add=lambda s: self.on_skill_added and self.on_skill_added(s),
            get_common_skills=self.get_common_skills,
        )
        vbox.addWidget(skills)

        footer = QHBoxLayout()
        footer.addStretch()
        footer.addWidget(self._make_remove_btn(card))
        vbox.addLayout(footer)

        card.setProperty("_name", name)
        card.setProperty("_url", url)
        card.setProperty("_start", start)
        card.setProperty("_end", end)
        card.setProperty("_bullets", bullets)
        card.setProperty("_skills", skills)

        self._cards_layout.addWidget(card)

    def get_data(self) -> list[dict]:
        result = []
        for i in range(self._cards_layout.count()):
            card = self._cards_layout.itemAt(i).widget()
            if card is None:
                continue
            result.append({
                "name": card.property("_name").text(),
                "url": card.property("_url").text(),
                "start": card.property("_start").text(),
                "end": card.property("_end").text(),
                "bullets": card.property("_bullets").get_bullets(),
                "skills": card.property("_skills").get_items(),
            })
        return result
