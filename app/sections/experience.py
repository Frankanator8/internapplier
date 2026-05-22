from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QFrame, QLabel,
)
from PyQt6.QtCore import Qt

from .base import (
    BulletsWidget, ChipsWidget,
    make_field, make_line_edit, _primary_btn, _label,
    make_card_frame, add_remove_footer, attach_fields, read_fields,
    iter_cards, clear_layout,
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
            subtitle.setObjectName("group-subtitle")
            header_row.addWidget(subtitle)
            header_row.addStretch()
            add_btn = _primary_btn(add_label)
            add_btn.clicked.connect(lambda _checked=False, k=key: self.add_entry(category=k))
            header_row.addWidget(add_btn)
            container_layout.addLayout(header_row)

            cards_layout = QVBoxLayout()
            cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
            cards_layout.setSpacing(14)
            container_layout.addLayout(cards_layout)
            self._group_layouts[key] = cards_layout

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

        card = make_card_frame()
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

        add_remove_footer(vbox, lambda: self._remove_card(card))

        attach_fields(card, {
            "company": company,
            "title": title,
            "start": start,
            "end": end,
            "bullets": bullets,
            "skills": skills,
        })
        card.setProperty("_category", category)

        self._group_layouts[category].addWidget(card)

    def clear(self):
        for layout in self._group_layouts.values():
            clear_layout(layout)

    def get_data(self) -> list[dict]:
        result = []
        for key, layout in self._group_layouts.items():
            for card in iter_cards(layout):
                entry = read_fields(card)
                entry["category"] = key
                result.append(entry)
        return result
