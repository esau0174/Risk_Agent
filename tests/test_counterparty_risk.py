from __future__ import annotations

import pytest

from src.credit_risk.counterparty_risk import calculate_pfe_metrics
from src.core.tool_executor import ToolExecutor
from src.data.portfolio_loader import ExposureProfile, ExposureProfileRow


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
    assert metrics["configured_limit"] is None
    assert metrics["limit_utilization"] is None
    assert metrics["limit_status"] == "WARNING"
    assert metrics["limit_warning"] == "No credit limit configured for netting set NS-001."


def test_calculate_pfe_metrics_returns_limit_utilization_for_largest_netting_set():
    metrics = calculate_pfe_metrics(
        _exposure_profile(),
        credit_limits={"NS-001": 275.0, "NS-002": 100.0},
    )

    assert metrics["configured_limit"] == 275.0
    assert metrics["limit_utilization"] == pytest.approx(0.8)
    assert metrics["limit_status"] == "PASSED"
    assert metrics["limit_warning"] is None


def test_calculate_pfe_metrics_marks_limit_breach():
    metrics = calculate_pfe_metrics(_exposure_profile(), credit_limits={"NS-001": 200.0})

    assert metrics["limit_utilization"] == pytest.approx(1.1)
    assert metrics["limit_status"] == "BREACHED"


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
