from __future__ import annotations

import pytest

from src.credit_risk.counterparty_risk import calculate_pfe_metrics
from src.portfolio_loader import ExposureProfile, ExposureProfileRow
from src.core.tool_executor import ToolExecutor


def test_legacy_counterparty_risk_import_remains_compatible():
    from src.counterparty_risk import calculate_pfe_metrics as legacy_calculate

    assert legacy_calculate is calculate_pfe_metrics


def _exposure_profile() -> ExposureProfile:
    return ExposureProfile(
        exposures=[
            ExposureProfileRow("NS-001", 0.0, 100.0, 150.0, 180.0),
            ExposureProfileRow("NS-001", 1.0, 140.0, 220.0, 280.0),
            ExposureProfileRow("NS-002", 0.0, 80.0, 120.0, 160.0),
            ExposureProfileRow("NS-002", 2.0, 120.0, 200.0, 260.0),
        ]
    )


def test_calculate_pfe_metrics_returns_all_profile_metrics():
    metrics = calculate_pfe_metrics(_exposure_profile())

    assert metrics["peak_pfe_95"] == 220.0
    assert metrics["time_of_peak_pfe_95"] == 1.0
    assert metrics["peak_pfe_99"] == 280.0
    assert metrics["time_of_peak_pfe_99"] == 1.0
    assert metrics["average_expected_exposure"] == pytest.approx(110.0)
    assert metrics["epe"] == pytest.approx(110.0)
    assert metrics["max_expected_exposure"] == 140.0
    assert metrics["total_expected_exposure_by_netting_set"] == {
        "NS-001": 240.0,
        "NS-002": 200.0,
    }
    assert metrics["largest_netting_set_by_peak_pfe"] == "NS-001"
    assert metrics["largest_netting_set_peak_pfe_95"] == 220.0


def test_calculate_pfe_metrics_omits_unavailable_pfe_99_values():
    profile = ExposureProfile(
        exposures=[
            ExposureProfileRow("NS-001", 0.0, 100.0, 150.0),
            ExposureProfileRow("NS-001", 1.0, 120.0, 180.0),
        ]
    )

    metrics = calculate_pfe_metrics(profile)

    assert metrics["peak_pfe_99"] is None
    assert metrics["time_of_peak_pfe_99"] is None


def test_calculate_pfe_metrics_is_executable_through_tool_executor():
    result = ToolExecutor().execute("calculate_pfe_metrics", _exposure_profile())

    assert result.status == "success"
    assert result.output["peak_pfe_95"] == 220.0
    assert result.metadata["callable_name"] == (
        "src.counterparty_risk.calculate_pfe_metrics"
    )


def test_calculate_pfe_metrics_rejects_empty_profile():
    with pytest.raises(ValueError, match="must contain at least one row"):
        calculate_pfe_metrics(ExposureProfile(exposures=[]))
