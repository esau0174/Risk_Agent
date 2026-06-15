from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src.data.portfolio import validate_weights


MARKET_PORTFOLIO_COLUMNS = {"ticker", "weight"}
EXPOSURE_PROFILE_COLUMNS = {
    "netting_set",
    "time_years",
    "expected_exposure",
    "pfe_95",
}


@dataclass(frozen=True)
class ExposureProfileRow:
    netting_set: str
    time_years: float
    expected_exposure: float
    pfe_95: float
    pfe_99: float | None = None
    currency: str | None = None
    counterparty: str | None = None


@dataclass(frozen=True)
class ExposureProfile:
    exposures: list[ExposureProfileRow]


def load_portfolio_file(file_path: str | Path) -> dict | ExposureProfile:
    """Load market holdings or a counterparty exposure profile."""
    path = Path(file_path)
    if not path.exists():
        raise ValueError(f"Portfolio file does not exist: {path}")

    suffix = path.suffix.lower()
    if suffix == ".csv":
        data = pd.read_csv(path)
    elif suffix == ".xlsx":
        data = pd.read_excel(path)
    elif suffix == ".json":
        data = _read_json(path)
    else:
        raise ValueError(
            f"Unsupported portfolio file format '{suffix}'. Use CSV, XLSX, or JSON."
        )

    data = _normalize_columns(data)
    schema = detect_file_schema(data.columns)
    if schema == "exposure_profile":
        return _load_exposure_profile(data)

    return _load_market_portfolio(data)


def detect_file_schema(columns) -> str:
    """Classify normalized columns as market holdings or an exposure profile."""
    column_set = {str(column).strip().lower() for column in columns}
    if EXPOSURE_PROFILE_COLUMNS.issubset(column_set):
        return "exposure_profile"
    if MARKET_PORTFOLIO_COLUMNS.issubset(column_set):
        return "market_portfolio"

    if column_set & EXPOSURE_PROFILE_COLUMNS:
        missing = ", ".join(sorted(EXPOSURE_PROFILE_COLUMNS - column_set))
        raise ValueError(f"Exposure profile file is missing required columns: {missing}.")

    missing = ", ".join(sorted(MARKET_PORTFOLIO_COLUMNS - column_set))
    raise ValueError(f"Portfolio file is missing required columns: {missing}.")


def _load_market_portfolio(data: pd.DataFrame) -> dict:
    if data.empty:
        raise ValueError("Portfolio file must contain at least one holding.")

    tickers = [_normalize_ticker(value, row) for row, value in enumerate(data["ticker"], 1)]
    weights = [_normalize_weight(value, row) for row, value in enumerate(data["weight"], 1)]

    try:
        validated_weights = validate_weights(tickers, weights)
    except ValueError as exc:
        raise ValueError(f"Invalid portfolio weights: {exc}") from exc

    return {
        "tickers": tickers,
        "weights": validated_weights.tolist(),
    }


def _load_exposure_profile(data: pd.DataFrame) -> ExposureProfile:
    if data.empty:
        raise ValueError("Exposure profile file must contain at least one row.")

    exposures = []
    for row_number, (_, row) in enumerate(data.iterrows(), start=1):
        pfe_95 = _non_negative_number(row["pfe_95"], "pfe_95", row_number)
        pfe_99 = _optional_non_negative_number(
            row.get("pfe_99"),
            "pfe_99",
            row_number,
        )
        if pfe_99 is not None and pfe_99 < pfe_95:
            raise ValueError(
                f"pfe_99 in row {row_number} must be greater than or equal to pfe_95."
            )

        exposures.append(
            ExposureProfileRow(
                netting_set=_required_text(row["netting_set"], "netting_set", row_number),
                time_years=_non_negative_number(
                    row["time_years"],
                    "time_years",
                    row_number,
                ),
                expected_exposure=_non_negative_number(
                    row["expected_exposure"],
                    "expected_exposure",
                    row_number,
                ),
                pfe_95=pfe_95,
                pfe_99=pfe_99,
                currency=_optional_text(row.get("currency")),
                counterparty=_optional_text(row.get("counterparty")),
            )
        )

    return ExposureProfile(exposures=exposures)


def _read_json(path: Path) -> pd.DataFrame:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Portfolio JSON is invalid: {exc.msg}.") from exc

    if isinstance(payload, dict):
        if "portfolio" in payload:
            payload = payload["portfolio"]
        elif "exposure_profile" in payload:
            payload = payload["exposure_profile"]

    try:
        return pd.DataFrame(payload)
    except (TypeError, ValueError) as exc:
        raise ValueError("Portfolio JSON must contain records or column arrays.") from exc


def _normalize_columns(data: pd.DataFrame) -> pd.DataFrame:
    normalized = data.copy()
    normalized.columns = [str(column).strip().lower() for column in normalized.columns]
    return normalized


def _normalize_ticker(value, row: int) -> str:
    if pd.isna(value):
        raise ValueError(f"Ticker is missing in row {row}.")

    ticker = str(value).strip().upper()
    if not ticker:
        raise ValueError(f"Ticker is missing in row {row}.")

    return ticker


def _normalize_weight(value, row: int) -> float:
    if pd.isna(value):
        raise ValueError(f"Weight is missing in row {row}.")

    is_percentage = isinstance(value, str) and value.strip().endswith("%")
    raw_value = value.strip().removesuffix("%").strip() if isinstance(value, str) else value

    try:
        weight = float(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Weight in row {row} must be numeric or a percentage.") from exc

    if is_percentage or abs(weight) > 1:
        weight /= 100

    return weight


def _required_text(value, field_name: str, row: int) -> str:
    if pd.isna(value) or not str(value).strip():
        raise ValueError(f"{field_name} is missing in row {row}.")
    return str(value).strip()


def _optional_text(value) -> str | None:
    if value is None or pd.isna(value) or not str(value).strip():
        return None
    return str(value).strip()


def _non_negative_number(value, field_name: str, row: int) -> float:
    if pd.isna(value):
        raise ValueError(f"{field_name} is missing in row {row}.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} in row {row} must be numeric.") from exc
    if not math.isfinite(number):
        raise ValueError(f"{field_name} in row {row} must be numeric.")
    if number < 0:
        raise ValueError(f"{field_name} in row {row} must be non-negative.")
    return number


def _optional_non_negative_number(value, field_name: str, row: int) -> float | None:
    if value is None or pd.isna(value) or (isinstance(value, str) and not value.strip()):
        return None
    return _non_negative_number(value, field_name, row)
