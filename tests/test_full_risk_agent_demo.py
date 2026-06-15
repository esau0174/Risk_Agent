from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from src.workflow import AgentRunResult


def _load_demo_module():
    demo_path = Path("examples/run_full_risk_agent_demo.py")
    spec = importlib.util.spec_from_file_location("run_full_risk_agent_demo", demo_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _agent_result() -> AgentRunResult:
    return AgentRunResult(
        user_report="Combined Executive Summary\nMarket Risk and Credit Risk",
        execution_trace=[
            {
                "step_number": 1,
                "tool_name": "load_portfolio_file",
                "status": "success",
                "input_summary": "Market data file.",
                "output_summary": "Loaded holdings.",
                "error": None,
                "workflow": "market_risk",
            }
        ],
        validation_result={"passed": True},
        raw_outputs={"market_risk": {}, "credit_risk": {}},
    )


def test_full_demo_prints_only_user_report_by_default(monkeypatch, capsys):
    module = _load_demo_module()
    result = _agent_result()
    monkeypatch.setattr(module, "run_full_risk_agent_workflow", lambda **kwargs: result)

    module.main([])

    assert capsys.readouterr().out.strip() == result.user_report


def test_full_demo_optionally_saves_execution_trace(monkeypatch, tmp_path):
    module = _load_demo_module()
    result = _agent_result()
    trace_path = tmp_path / "full_demo_trace.json"
    monkeypatch.setattr(module, "run_full_risk_agent_workflow", lambda **kwargs: result)

    module.main(["--trace-file", str(trace_path)])

    assert json.loads(trace_path.read_text(encoding="utf-8")) == result.execution_trace
