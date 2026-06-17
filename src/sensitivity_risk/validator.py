from __future__ import annotations

from src.sensitivity_risk.loader import SensitivityRecord


def validate_sensitivity_file(records: list[SensitivityRecord]) -> list[SensitivityRecord]:
    """Validate supplied precomputed Greeks records and return them unchanged."""
    if not records:
        raise ValueError("Sensitivity file must contain at least one record.")

    trade_ids = set()
    for index, record in enumerate(records, start=1):
        if record.trade_id in trade_ids:
            raise ValueError(f"Duplicate trade_id in sensitivity file: {record.trade_id}.")
        trade_ids.add(record.trade_id)
        for field_name in ("delta", "gamma", "vega", "theta"):
            value = getattr(record, field_name)
            if not isinstance(value, float):
                raise ValueError(f"{field_name} in record {index} must be numeric.")
    return records
