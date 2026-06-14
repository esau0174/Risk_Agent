from __future__ import annotations

from collections import defaultdict

from src.portfolio_loader import ExposureProfile, ExposureProfileRow


def calculate_pfe_metrics(exposure_profile: ExposureProfile) -> dict:
    """Calculate deterministic exposure and PFE profile summary metrics."""
    if not isinstance(exposure_profile, ExposureProfile):
        raise ValueError("exposure_profile must be an ExposureProfile object.")
    if not exposure_profile.exposures:
        raise ValueError("Exposure profile must contain at least one row.")

    exposures = exposure_profile.exposures
    for row in exposures:
        _validate_row(row)

    peak_95_row = max(exposures, key=lambda row: row.pfe_95)
    pfe_99_rows = [row for row in exposures if row.pfe_99 is not None]
    peak_99_row = (
        max(pfe_99_rows, key=lambda row: row.pfe_99)
        if pfe_99_rows
        else None
    )

    total_expected_exposure_by_netting_set: dict[str, float] = defaultdict(float)
    peak_pfe_95_by_netting_set: dict[str, float] = {}
    for row in exposures:
        total_expected_exposure_by_netting_set[row.netting_set] += row.expected_exposure
        peak_pfe_95_by_netting_set[row.netting_set] = max(
            peak_pfe_95_by_netting_set.get(row.netting_set, 0.0),
            row.pfe_95,
        )

    largest_netting_set = max(
        peak_pfe_95_by_netting_set,
        key=peak_pfe_95_by_netting_set.get,
    )
    expected_exposures = [row.expected_exposure for row in exposures]

    return {
        "peak_pfe_95": float(peak_95_row.pfe_95),
        "time_of_peak_pfe_95": float(peak_95_row.time_years),
        "peak_pfe_99": (
            float(peak_99_row.pfe_99) if peak_99_row is not None else None
        ),
        "time_of_peak_pfe_99": (
            float(peak_99_row.time_years) if peak_99_row is not None else None
        ),
        "average_expected_exposure": float(
            sum(expected_exposures) / len(expected_exposures)
        ),
        "epe": float(sum(expected_exposures) / len(expected_exposures)),
        "max_expected_exposure": float(max(expected_exposures)),
        "total_expected_exposure_by_netting_set": {
            netting_set: float(total)
            for netting_set, total in total_expected_exposure_by_netting_set.items()
        },
        "largest_netting_set_by_peak_pfe": largest_netting_set,
        "largest_netting_set_peak_pfe_95": float(
            peak_pfe_95_by_netting_set[largest_netting_set]
        ),
    }


def _validate_row(row: ExposureProfileRow) -> None:
    if not isinstance(row, ExposureProfileRow):
        raise ValueError("Exposure profile rows must be ExposureProfileRow objects.")
