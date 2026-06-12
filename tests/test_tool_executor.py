from src.tool_executor import ToolExecutor
from src.tool_registry import RiskTool


def test_successful_tool_execution_returns_output_and_metadata():
    tool = RiskTool(
        name="add",
        description="Add two numbers.",
        callable_name="tests.add",
        callable=lambda left, right: left + right,
    )
    executor = ToolExecutor([tool])

    result = executor.execute("add", 2, 3)

    assert result.status == "success"
    assert result.output == 5
    assert result.error is None
    assert result.metadata == {"callable_name": "tests.add"}


def test_unknown_tool_name_returns_failed_result():
    executor = ToolExecutor([])

    result = executor.execute("missing_tool")

    assert result.status == "failed"
    assert result.output is None
    assert "Unknown risk tool 'missing_tool'" in result.error


def test_tool_execution_failure_returns_error_details():
    def failing_tool():
        raise ValueError("calculation failed")

    tool = RiskTool(
        name="failing_tool",
        description="Always fails.",
        callable_name="tests.failing_tool",
        callable=failing_tool,
    )
    executor = ToolExecutor([tool])

    result = executor.execute("failing_tool")

    assert result.status == "failed"
    assert result.output is None
    assert result.error == "ValueError: calculation failed"
    assert result.metadata == {"callable_name": "tests.failing_tool"}
