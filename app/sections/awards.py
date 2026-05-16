from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout
from .base import CardPage, BulletsWidget, ChipsWidget, make_field, make_line_edit


class AwardsPage(CardPage):
    section_title = "Awards"
    add_label = "+ Add Award"

    def add_entry(self, data: dict | None = None):
        data = data or {}
        card = self._make_card()
        vbox = QVBoxLayout(card)
        vbox.setContentsMargins(20, 18, 20, 16)
        vbox.setSpacing(12)

        title = make_line_edit("Dean's List")
        issuer = make_line_edit("UC Berkeley")
        date = make_line_edit("May 2025")

        title.setText(data.get("title", ""))
        issuer.setText(data.get("issuer", ""))
        date.setText(data.get("date", ""))

        row1 = QHBoxLayout()
        row1.setSpacing(16)
        row1.addLayout(make_field("Title", title), 3)
        row1.addLayout(make_field("Issuer", issuer), 3)
        row1.addLayout(make_field("Date", date), 2)
        vbox.addLayout(row1)

        bullets = BulletsWidget(
            data.get("bullets", []),
            get_context=lambda: {
                "type": "award",
                "title": title.text(),
                "issuer": issuer.text(),
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

        card.setProperty("_title", title)
        card.setProperty("_issuer", issuer)
        card.setProperty("_date", date)
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
                "title": card.property("_title").text(),
                "issuer": card.property("_issuer").text(),
                "date": card.property("_date").text(),
                "bullets": card.property("_bullets").get_bullets(),
                "skills": card.property("_skills").get_items(),
            })
        return result
