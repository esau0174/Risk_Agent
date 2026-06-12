from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.portfolio import validate_weights


REQUIRED_COLUMNS = {"ticker", "weight"}


def load_portfolio_file(file_path: str | Path) -> dict:
    """Load and validate a portfolio from CSV, Excel, or JSON."""
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
    missing_columns = REQUIRED_COLUMNS - set(data.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Portfolio file is missing required columns: {missing}.")

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


def _read_json(path: Path) -> pd.DataFrame:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Portfolio JSON is invalid: {exc.msg}.") from exc

    if isinstance(payload, dict) and "portfolio" in payload:
        payload = payload["portfolio"]

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
