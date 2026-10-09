from __future__ import annotations

from typing import Callable

from PyQt6.QtWidgets import QStatusBar

from app.ui.sidebar_stack import SidebarStack

from .ai_model_page import AiModelSettings
from .general_page import GeneralSettings
from .prompts_page import PromptsSettings
from .resume_page import ResumeSettings
from .token_usage_page import TokenUsageSettings


class SettingsPage(SidebarStack):
    def __init__(self, status_bar: QStatusBar, on_heatmap_thresholds_changed: Callable[[], None]):
        super().__init__()
        self.add_page("⚙️  General", GeneralSettings(status_bar, on_heatmap_thresholds_changed))
        self.add_page("🤖  AI Model", AiModelSettings(status_bar))
        self.add_page("📄  Resume", ResumeSettings(status_bar))
        self.add_page("📝  System Prompts", PromptsSettings(status_bar))
        self.add_page("📊  Token Usage", TokenUsageSettings(status_bar))
