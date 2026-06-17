from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


REQUIRED_SENSITIVITY_COLUMNS = {
    "portfolio_id",
    "book",
    "trade_id",
    "instrument_type",
    "risk_class",
    "risk_factor",
    "bucket",
    "delta",
    "gamma",
    "vega",
    "theta",
    "currency",
}


@dataclass(frozen=True)
class SensitivityRecord:
    portfolio_id: str
    book: str
    trade_id: str
    instrument_type: str
    risk_class: str
    risk_factor: str
    bucket: str
    delta: float
    gamma: float
    vega: float
    theta: float
    currency: str


def load_sensitivity_file(file_path: str | Path) -> list[SensitivityRecord]:
    """Load precomputed Greeks from a CSV file."""
    path = Path(file_path)
    if not path.exists():
        raise ValueError(f"Sensitivity file does not exist: {path}")
    if path.suffix.lower() != ".csv":
        raise ValueError("Sensitivity file must be a CSV file.")

    data = pd.read_csv(path)
    data.columns = [str(column).strip().lower() for column in data.columns]
    missing = sorted(REQUIRED_SENSITIVITY_COLUMNS - set(data.columns))
    if missing:
        raise ValueError(
            "Sensitivity file is missing required columns: "
            + ", ".join(missing)
            + "."
        )
    if data.empty:
        raise ValueError("Sensitivity file must contain at least one row.")

    return [
        SensitivityRecord(
            portfolio_id=_required_text(row["portfolio_id"], "portfolio_id", row_number),
            book=_required_text(row["book"], "book", row_number),
            trade_id=_required_text(row["trade_id"], "trade_id", row_number),
            instrument_type=_required_text(
                row["instrument_type"],
                "instrument_type",
                row_number,
            ),
            risk_class=_required_text(row["risk_class"], "risk_class", row_number),
            risk_factor=_required_text(row["risk_factor"], "risk_factor", row_number),
            bucket=_required_text(row["bucket"], "bucket", row_number),
            delta=_numeric(row["delta"], "delta", row_number),
            gamma=_numeric(row["gamma"], "gamma", row_number),
            vega=_numeric(row["vega"], "vega", row_number),
            theta=_numeric(row["theta"], "theta", row_number),
            currency=_required_text(row["currency"], "currency", row_number).upper(),
        )
        for row_number, (_, row) in enumerate(data.iterrows(), start=1)
    ]


def _required_text(value, field_name: str, row_number: int) -> str:
    if pd.isna(value) or not str(value).strip():
        raise ValueError(f"{field_name} is missing in row {row_number}.")
    return str(value).strip()


def _numeric(value, field_name: str, row_number: int) -> float:
    if pd.isna(value):
        raise ValueError(f"{field_name} is missing in row {row_number}.")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} in row {row_number} must be numeric.") from exc
