from __future__ import annotations

from pathlib import Path


def test_streamlit_app_uses_public_workflow_api_without_analytics_duplication():
    source = Path("apps/streamlit_app.py").read_text(encoding="utf-8")

    assert "from riskflow_agent import run_agent_workflow" in source
    assert "run_agent_workflow(" in source
    assert "download_price_data" not in source
    assert "calculate_pfe_metrics(" not in source
    assert "aggregate_greeks(" not in source


def test_streamlit_optional_dependency_group_is_declared():
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")

    assert "ui = [" in pyproject
    assert '"streamlit>=1.30"' in pyproject
