from __future__ import annotations

import importlib.util
from pathlib import Path


def test_market_risk_demo_uses_shared_formatting_and_result_sections():
    demo_path = Path("examples/run_llm_agent_demo.py")
    source = demo_path.read_text(encoding="utf-8")

    assert "from examples.demo_utils import" in source
    assert "print_input_summary" in source
    assert "print_registered_tools_by_module" in source
    assert "print_workflow_plan" in source
    assert "print_execution_trace" in source
    assert "print_methodology_notes" in source
    assert "print_validation_result" in source
    assert 'print("Market Risk Results")' in source
    assert 'print("Stress Test Results")' in source

    spec = importlib.util.spec_from_file_location("run_llm_agent_demo", demo_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert callable(module.main)
