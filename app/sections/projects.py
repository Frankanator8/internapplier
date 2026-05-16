from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout
from .base import CardPage, BulletsWidget, make_field, make_line_edit


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

        name.setText(data.get("name", ""))
        url.setText(data.get("url", ""))

        row1 = QHBoxLayout()
        row1.setSpacing(16)
        row1.addLayout(make_field("Project Name", name), 2)
        row1.addLayout(make_field("URL", url), 2)
        vbox.addLayout(row1)

        bullets = BulletsWidget(
            data.get("bullets", []),
            get_context=lambda: {
                "type": "project",
                "name": name.text(),
            },
        )
        vbox.addWidget(bullets)

        footer = QHBoxLayout()
        footer.addStretch()
        footer.addWidget(self._make_remove_btn(card))
        vbox.addLayout(footer)

        card.setProperty("_name", name)
        card.setProperty("_url", url)
        card.setProperty("_bullets", bullets)

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
                "bullets": card.property("_bullets").get_bullets(),
            })
        return result
