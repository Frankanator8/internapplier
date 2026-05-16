from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout
from .base import CardPage, BulletsWidget, make_field, make_line_edit, _danger_btn


class ExperiencePage(CardPage):
    section_title = "Experience"
    add_label = "+ Add Experience"

    def add_entry(self, data: dict | None = None):
        data = data or {}
        card = self._make_card()
        vbox = QVBoxLayout(card)
        vbox.setContentsMargins(20, 18, 20, 16)
        vbox.setSpacing(12)

        company = make_line_edit("Google")
        title = make_line_edit("Software Engineer Intern")
        start = make_line_edit("Jun 2024")
        end = make_line_edit("Aug 2024")

        company.setText(data.get("company", ""))
        title.setText(data.get("title", ""))
        start.setText(data.get("start", ""))
        end.setText(data.get("end", ""))

        # Row 1: company + title
        row1 = QHBoxLayout()
        row1.setSpacing(16)
        row1.addLayout(make_field("Company", company), 3)
        row1.addLayout(make_field("Title / Role", title), 3)
        vbox.addLayout(row1)

        # Row 2: dates
        row2 = QHBoxLayout()
        row2.setSpacing(16)
        row2.addLayout(make_field("Start Date", start))
        row2.addLayout(make_field("End Date", end))
        row2.addStretch(2)
        vbox.addLayout(row2)

        bullets = BulletsWidget(
            data.get("bullets", []),
            get_context=lambda: {
                "type": "experience",
                "company": company.text(),
                "role": title.text(),
            },
        )
        vbox.addWidget(bullets)

        footer = QHBoxLayout()
        footer.addStretch()
        footer.addWidget(self._make_remove_btn(card))
        vbox.addLayout(footer)

        card.setProperty("_company", company)
        card.setProperty("_title", title)
        card.setProperty("_start", start)
        card.setProperty("_end", end)
        card.setProperty("_bullets", bullets)

        self._cards_layout.addWidget(card)

    def get_data(self) -> list[dict]:
        result = []
        for i in range(self._cards_layout.count()):
            card = self._cards_layout.itemAt(i).widget()
            if card is None:
                continue
            result.append({
                "company": card.property("_company").text(),
                "title": card.property("_title").text(),
                "start": card.property("_start").text(),
                "end": card.property("_end").text(),
                "bullets": card.property("_bullets").get_bullets(),
            })
        return result
