from __future__ import annotations

from app.ui.sidebar_stack import SidebarStack

from .entries import AwardsPage, EducationPage, ExperiencePage, ProjectsPage
from .general_info import GeneralInfoPage
from .string_list import StringListPage


class ProfilePage(SidebarStack):
    """The Profile tab: one editor per resume section, keyed by data_store key.

    Every editor implements ``load / get_data / merge / clear / has_data``, so
    the rest of the app treats the profile as one dict.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._editors = {
            "general_info": self.add_page("👤  General Info", GeneralInfoPage()),
            "experience": self.add_page("💼  Experience", ExperiencePage()),
            "projects": self.add_page("🚀  Projects", ProjectsPage()),
            "education": self.add_page("🎓  Education", EducationPage()),
            "awards": self.add_page("🏆  Awards", AwardsPage()),
            "skills": self.add_page("🛠  Skills", StringListPage("Skills", "skill")),
            "hobbies": self.add_page("🎯  Hobbies", StringListPage("Hobbies", "hobby")),
        }

    def keys(self) -> list[str]:
        return list(self._editors)

    def load(self, data: dict) -> None:
        for key, editor in self._editors.items():
            editor.load(data.get(key))

    def get_data(self) -> dict:
        return {key: editor.get_data() for key, editor in self._editors.items()}

    def has_data(self) -> bool:
        return any(editor.has_data() for editor in self._editors.values())

    def apply_import(self, data: dict, mode: str) -> None:
        """Push an imported profile dict into the editors (nothing is persisted).

        Sections absent from ``data`` are left alone even in replace mode.
        """
        for key, editor in self._editors.items():
            if key in data:
                editor.merge(data[key], mode)
