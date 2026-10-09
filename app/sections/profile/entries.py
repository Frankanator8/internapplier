"""Card-based profile editors: experience, projects, education, awards."""
from __future__ import annotations

from .card_page import CardPage, EntryCard
from .widgets import CoursesWidget


class ExperiencePage(CardPage):
    section_title = "Experience"
    groups = (
        ("relevant", "Relevant Experience", "+ Add Relevant"),
        ("other", "Leadership / Other Experience", "+ Add Leadership / Other"),
    )
    rows = (
        (("company", "Company", "Google", 3), ("title", "Title / Role", "Software Engineer Intern", 3)),
        (("start", "Start Date", "Jun 2024", 0), ("end", "End Date", "Aug 2024", 0), 2),
    )

    def add_extras(self, card: EntryCard) -> None:
        self.add_bullets(card, lambda: {
            "type": "experience", "company": card.text("company"), "role": card.text("title"),
        })


class ProjectsPage(CardPage):
    section_title = "Projects"
    add_label = "+ Add Project"
    rows = (
        (("name", "Project Name", "My Awesome Project", 2), ("url", "URL", "https://github.com/…  (optional)", 2)),
        (("start", "Start Date", "Jun 2024", 0), ("end", "End Date", "Aug 2024", 0), 2),
    )

    def add_extras(self, card: EntryCard) -> None:
        self.add_bullets(card, lambda: {"type": "project", "name": card.text("name")})


class EducationPage(CardPage):
    section_title = "Education"
    add_label = "+ Add Education"
    rows = (
        (("school", "School", "University of California, Berkeley", 3), ("degree", "Degree", "B.S. Computer Science", 3)),
        (("start", "Start Date", "Aug 2022", 0), ("end", "End Date", "May 2026", 0), ("gpa", "GPA", "3.9 / 4.0  (optional)", 0)),
    )

    def add_extras(self, card: EntryCard) -> None:
        card.add_widget("courses", CoursesWidget(card.data.get("courses", [])))


class AwardsPage(CardPage):
    section_title = "Awards"
    add_label = "+ Add Award"
    rows = (
        (("title", "Title", "Dean's List", 3), ("issuer", "Issuer", "UC Berkeley", 3), ("date", "Date", "May 2025", 2)),
    )

    def add_extras(self, card: EntryCard) -> None:
        self.add_bullets(card, lambda: {
            "type": "award", "title": card.text("title"), "issuer": card.text("issuer"),
        })
