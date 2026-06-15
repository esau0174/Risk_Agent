"""Compatibility wrapper for src.core.tool_executor. New code should import from src.core.tool_executor."""

from src.core.tool_executor import ToolExecutor, ToolResult

__all__ = ["ToolExecutor", "ToolResult"]
