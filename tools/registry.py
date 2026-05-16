from typing import Any, Callable


ToolFn = Callable[[dict, dict], dict]


class ToolError(Exception):
    pass


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolFn] = {}
        self._schemas: dict[str, dict] = {}

    def register(self, schema: dict, fn: ToolFn) -> None:
        name = schema["name"]
        if name in self._tools:
            raise ValueError(f"Tool already registered: {name}")
        self._tools[name] = fn
        self._schemas[name] = schema

    def schemas(self) -> list[dict]:
        return list(self._schemas.values())

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def call(self, name: str, tool_input: dict, context: dict) -> dict:
        if name not in self._tools:
            raise ToolError(f"Unknown tool: {name}")
        return self._tools[name](tool_input or {}, context)


REGISTRY = ToolRegistry()


def tool(schema: dict) -> Callable[[ToolFn], ToolFn]:
    def decorator(fn: ToolFn) -> ToolFn:
        REGISTRY.register(schema, fn)
        return fn

    return decorator
