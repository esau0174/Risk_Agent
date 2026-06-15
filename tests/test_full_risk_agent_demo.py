from __future__ import annotations

import importlib.util
from pathlib import Path


def test_full_risk_agent_demo_uses_shared_workflow_and_formatting():
    demo_path = Path("examples/run_full_risk_agent_demo.py")
    source = demo_path.read_text(encoding="utf-8")

    assert "from examples.demo_utils import" in source
    assert source.count("run_risk_workflow(") == 2
    assert 'MARKET_DATA_FILE = "examples/sample_portfolio.csv"' in source
    assert 'CREDIT_DATA_FILE = "examples/sample_exposure_profile.csv"' in source
    assert 'CONFIG_FILE = "examples/sample_risk_config.json"' in source
    assert "data_file=MARKET_DATA_FILE" in source
    assert "data_file=CREDIT_DATA_FILE" in source
    assert "use_llm=False" in source
    assert "Combined Executive Summary" in source
    assert "Active modules covered: Market Risk, Credit Risk" in source
    assert "print_workflow_plan" in source
    assert "print_execution_trace" in source
    assert "print_validation_result" in source

    spec = importlib.util.spec_from_file_location("run_full_risk_agent_demo", demo_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert callable(module.main)
