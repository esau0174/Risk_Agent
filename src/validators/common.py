"""Shared validation dataclasses and helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ValidationCheck:
    name: str
    passed: bool
    message: str


@dataclass
class ValidationResult:
    passed: bool
    checks: list[ValidationCheck]
    errors: list[str]
    warnings: list[str]


def run_check(
    checks: list[ValidationCheck],
    errors: list[str],
    name: str,
    passed: bool,
    success_message: str,
    failure_message: str,
) -> None:
    message = success_message if passed else failure_message
    checks.append(ValidationCheck(name=name, passed=passed, message=message))
    if not passed:
        errors.append(failure_message)


def get_value(obj, key: str, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)
