"""Compatibility wrapper for src.core.tool_registry. New code should import from src.core.tool_registry."""

from src.core.tool_registry import (
    RiskTool,
    get_tool,
    list_registered_tools,
    list_tools_by_module,
)

__all__ = [
    "RiskTool",
    "get_tool",
    "list_registered_tools",
    "list_tools_by_module",
]
