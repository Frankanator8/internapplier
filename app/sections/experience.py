from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QFrame, QLabel,
)
from PyQt6.QtCore import Qt

from .base import (
    BulletsWidget, ChipsWidget, CardPage,
    make_field, make_line_edit, _primary_btn, _label,
)


class ExperiencePage(QWidget):
    section_title = "Experience"

    on_skill_added = None
    get_common_skills = None

    _GROUPS = (
        ("relevant", "Relevant Experience", "+ Add Relevant"),
        ("other", "Leadership / Other Experience", "+ Add Leadership / Other"),
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 16)
        outer.setSpacing(14)

        outer.addWidget(_label(self.section_title, "section-title"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        container_layout = QVBoxLayout(container)
        container_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        container_layout.setContentsMargins(0, 0, 0, 16)
        container_layout.setSpacing(20)
        scroll.setWidget(container)

        self._group_layouts: dict[str, QVBoxLayout] = {}
        for key, title, add_label in self._GROUPS:
            header_row = QHBoxLayout()
            subtitle = QLabel(title)
            subtitle.setStyleSheet(
                "font-size: 14px; font-weight: 600; color: #0a66c2;"
            )
            header_row.addWidget(subtitle)
            header_row.addStretch()
            add_btn = _primary_btn(add_label)
            add_btn.setStyleSheet(
                "QPushButton { background: #0a66c2; color: white; border: none;"
                " border-radius: 16px; padding: 7px 18px; font-weight: bold; font-size: 13px; }"
                "QPushButton:hover { background: #004182; }"
                "QPushButton:pressed { background: #003272; }"
            )
            add_btn.clicked.connect(lambda _checked=False, k=key: self.add_entry(category=k))
            header_row.addWidget(add_btn)
            container_layout.addLayout(header_row)

            cards_layout = QVBoxLayout()
            cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
            cards_layout.setSpacing(14)
            container_layout.addLayout(cards_layout)
            self._group_layouts[key] = cards_layout

    def _make_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        return card

    def _make_remove_btn(self, card: QFrame):
        return CardPage._make_remove_btn(self, card)

    def _remove_card(self, card: QFrame):
        category = card.property("_category") or "relevant"
        layout = self._group_layouts.get(category) or self._group_layouts["relevant"]
        layout.removeWidget(card)
        card.deleteLater()

    def add_entry(self, data: dict | None = None, category: str = "relevant"):
        data = data or {}
        category = data.get("category", category)
        if category not in self._group_layouts:
            category = "relevant"

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

        row1 = QHBoxLayout()
        row1.setSpacing(16)
        row1.addLayout(make_field("Company", company), 3)
        row1.addLayout(make_field("Title / Role", title), 3)
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
                "type": "experience",
                "company": company.text(),
                "role": title.text(),
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

        card.setProperty("_company", company)
        card.setProperty("_title", title)
        card.setProperty("_start", start)
        card.setProperty("_end", end)
        card.setProperty("_bullets", bullets)
        card.setProperty("_skills", skills)
        card.setProperty("_category", category)

        self._group_layouts[category].addWidget(card)

    def clear(self):
        for layout in self._group_layouts.values():
            while layout.count():
                item = layout.takeAt(0)
                w = item.widget()
                if w is not None:
                    w.deleteLater()

    def get_data(self) -> list[dict]:
        result = []
        for key, layout in self._group_layouts.items():
            for i in range(layout.count()):
                card = layout.itemAt(i).widget()
                if card is None:
                    continue
                result.append({
                    "company": card.property("_company").text(),
                    "title": card.property("_title").text(),
                    "start": card.property("_start").text(),
                    "end": card.property("_end").text(),
                    "bullets": card.property("_bullets").get_bullets(),
                    "skills": card.property("_skills").get_items(),
                    "category": key,
                })
        return result
