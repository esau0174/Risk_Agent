from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.tool_registry import RiskTool, list_registered_tools


@dataclass
class ToolResult:
    tool_name: str
    status: str
    output: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ToolExecutor:
    """Execute registered risk tools by name and return structured results."""

    def __init__(self, tools: list[RiskTool] | None = None) -> None:
        registered_tools = tools if tools is not None else list_registered_tools()
        self._tools = {tool.name: tool for tool in registered_tools}

    def execute(self, tool_name: str, *args, **kwargs) -> ToolResult:
        tool = self._tools.get(tool_name)
        if tool is None:
            available_tools = ", ".join(self._tools)
            return ToolResult(
                tool_name=tool_name,
                status="failed",
                error=(
                    f"Unknown risk tool '{tool_name}'. "
                    f"Available tools: {available_tools}."
                ),
                metadata={"requested_tool": tool_name},
            )

        metadata = {"callable_name": tool.callable_name}
        try:
            output = tool.callable(*args, **kwargs)
        except Exception as exc:
            return ToolResult(
                tool_name=tool_name,
                status="failed",
                error=f"{type(exc).__name__}: {exc}",
                metadata=metadata,
            )

        return ToolResult(
            tool_name=tool_name,
            status="success",
            output=output,
            metadata=metadata,
        )
