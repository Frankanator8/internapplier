from .registry import REGISTRY, ToolError, ToolRegistry
from . import profile_tools  # noqa: F401  (registers tools on import)
from . import page_tools  # noqa: F401


def get_tool_schemas() -> list[dict]:
    return REGISTRY.schemas()


def call_tool(name: str, tool_input: dict, context: dict) -> dict:
    return REGISTRY.call(name, tool_input, context)


__all__ = [
    "REGISTRY",
    "ToolError",
    "ToolRegistry",
    "get_tool_schemas",
    "call_tool",
]
