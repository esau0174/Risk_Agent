from __future__ import annotations

from src.core.tool_executor import ToolExecutor
from src.regulatory_risk.readiness import assess_regulatory_readiness
from src.validators.regulatory import validate_regulatory_readiness_report


def test_assess_regulatory_readiness_reports_missing_fields():
    result = assess_regulatory_readiness({"trade_type": "swap"})

    assert result["sa_ccr"]["status"] == "WARNING"
    assert "trade_notional" in result["sa_ccr"]["missing_trade_level_inputs"]
    assert "netting_agreement_details" in result["sa_ccr"]["missing_trade_level_inputs"]
    assert result["simm_regim"]["status"] == "WARNING"
    assert "risk_class" in result["missing_inputs"]
    assert "product_class" in result["simm_regim"]["missing_inputs"]
    assert result["simm_regim"]["available_inputs"] == []
    assert result["regulatory_capital_calculation"] == "Not performed"


def test_assess_regulatory_readiness_can_be_ready_when_required_inputs_exist():
    result = assess_regulatory_readiness(
        {
            "trade_type": "swap",
            "trade_notional": 1_000_000,
            "maturity": 5,
            "supervisory_category": "interest_rate",
            "netting_agreement_details": "CSA-001",
            "supervisory_factor_category_mapping": {"rates": "interest_rate"},
            "risk_class": "rates",
            "risk_factor": "USD 10Y",
            "bucket": "USD Rates",
            "delta": 1000,
            "gamma": 10,
            "vega": 500,
            "theta": -25,
            "currency": "USD",
            "product_class": "rates_fx",
            "margin_class": "rates",
            "risk_weight_mapping": {"USD 10Y": 1.0},
            "correlation_parameters": {"rates": 0.5},
            "margin_currency": "USD",
        }
    )

    assert result["sa_ccr"]["status"] == "READY"
    assert result["simm_regim"]["status"] == "READY"
    assert result["overall_status"] == "READY"
    assert result["missing_inputs"] == []


def test_sa_ccr_readiness_distinguishes_portfolio_metadata_from_trade_inputs():
    result = assess_regulatory_readiness(
        {
            "portfolio_notional_usd": 10_000_000,
            "portfolio_asset_classes": ["Equity ETF"],
        }
    )

    assert result["sa_ccr"]["status"] == "WARNING"
    assert result["sa_ccr"]["available_portfolio_metadata"] == [
        "portfolio_notional",
        "asset_class",
    ]
    assert "trade_notional" in result["sa_ccr"]["missing_trade_level_inputs"]
    assert "maturity" in result["sa_ccr"]["missing_trade_level_inputs"]
    assert "supervisory_category" in result["sa_ccr"]["missing_trade_level_inputs"]
    assert "netting_agreement_details" in result["sa_ccr"]["missing_trade_level_inputs"]
    assert (
        "supervisory_factor_category_mapping"
        in result["sa_ccr"]["missing_trade_level_inputs"]
    )
    assert "Portfolio-level metadata" in result["sa_ccr"]["guardrail_note"]


def test_assess_regulatory_readiness_uses_supplied_sensitivity_fields():
    result = assess_regulatory_readiness(
        {
            "precomputed_sensitivities": "available",
            "sensitivity_fields": [
                "risk_class",
                "risk_factor",
                "bucket",
                "delta",
                "gamma",
                "vega",
                "theta",
                "currency",
            ],
        }
    )

    assert result["simm_regim"]["status"] == "PARTIAL"
    assert "risk_class" in result["simm_regim"]["available_inputs"]
    assert "delta" in result["simm_regim"]["available_inputs"]
    assert "risk_class" not in result["simm_regim"]["missing_inputs"]
    assert "product_class" in result["simm_regim"]["missing_inputs"]
    assert "margin_class" in result["simm_regim"]["missing_inputs"]
    assert "risk_weight_mapping" in result["simm_regim"]["missing_inputs"]
    assert "correlation_parameters" in result["simm_regim"]["missing_inputs"]
    assert "margin_currency" in result["simm_regim"]["missing_inputs"]
    assert "No SIMM margin amount is generated" in result["simm_regim"]["guardrail_note"]


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
