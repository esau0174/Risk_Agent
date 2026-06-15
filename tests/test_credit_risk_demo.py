from __future__ import annotations

import importlib.util
from pathlib import Path


def test_credit_risk_demo_exists_with_expected_title_and_shared_workflow():
    demo_path = Path("examples/run_credit_risk_demo.py")
    source = demo_path.read_text(encoding="utf-8")

    assert demo_path.exists()
    assert "RiskFlow Agent - Credit Risk Workflow Demo" in source
    assert "Counterparty Exposure / PFE Analysis" in source
    assert "Credit Risk Results" in source
    assert "from examples.demo_utils import" in source
    assert "data_file=data_file" in source
    assert "portfolio_file=" not in source
    assert "run_risk_workflow" in source
    assert not Path("examples/run_pfe_demo.py").exists()

    spec = importlib.util.spec_from_file_location("run_credit_risk_demo", demo_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert callable(module.main)
