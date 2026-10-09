"""Drag-and-drop resume builder: palette of profile items → canvas of sections."""
from .canvas import AUTOSCROLL_MARGIN, BuilderCanvas, BuilderScroll
from .model import default_section_title, palette_groups
from .palette import BuilderPalette

__all__ = [
    "AUTOSCROLL_MARGIN", "BuilderCanvas", "BuilderPalette", "BuilderScroll",
    "default_section_title", "palette_groups",
]
