from __future__ import annotations

from src.core.tool_executor import ToolExecutor
from src.regulatory_risk.readiness import assess_regulatory_readiness
from src.validators.regulatory import validate_regulatory_readiness_report


def test_assess_regulatory_readiness_reports_missing_fields():
    result = assess_regulatory_readiness({"trade_type": "swap"})

    assert result["sa_ccr"]["status"] == "WARNING"
    assert "notional" in result["sa_ccr"]["missing_required_fields"]
    assert result["simm_regim"]["status"] == "WARNING"
    assert "risk_factor_sensitivities" in result["missing_inputs"]
    assert result["regulatory_capital_calculation"] == "Not performed"


def test_assess_regulatory_readiness_can_be_ready_when_required_inputs_exist():
    result = assess_regulatory_readiness(
        {
            "trade_type": "swap",
            "notional": 1_000_000,
            "maturity": 5,
            "asset_class": "rates",
            "supervisory_category": "interest_rate",
            "risk_factor_sensitivities": {"USD": 1000},
            "margin_class": "rates",
            "product_class": "rates_fx",
            "risk_factor_type": "delta",
            "currency": "USD",
        }
    )

    assert result["sa_ccr"]["status"] == "READY"
    assert result["simm_regim"]["status"] == "READY"
    assert result["overall_status"] == "READY"
    assert result["missing_inputs"] == []


def test_regulatory_readiness_is_registered_tool():
    result = ToolExecutor().execute("assess_regulatory_readiness", {})

    assert result.status == "success"
    assert result.output["overall_status"] == "WARNING"
    assert result.metadata["module"] == "regulatory_risk"


def test_regulatory_validation_requires_missing_inputs_to_be_reported():
    readiness = assess_regulatory_readiness({})

    result = validate_regulatory_readiness_report(
        "Regulatory Risk\nMissing inputs: trade_type",
        readiness,
    )

    assert result.passed is False
    assert "Regulatory missing inputs must be reported clearly." in result.errors


def test_regulatory_validation_rejects_fabricated_capital_or_margin_numbers():
    readiness = assess_regulatory_readiness({})
    report = (
        "Regulatory Risk\n"
        f"Missing inputs: {', '.join(readiness['missing_inputs'])}\n"
        "Regulatory capital calculation: USD 123,000"
    )

    result = validate_regulatory_readiness_report(report, readiness)

    assert result.passed is False
    assert (
        "Report must not contain unsupported regulatory capital or margin numbers."
        in result.errors
    )
