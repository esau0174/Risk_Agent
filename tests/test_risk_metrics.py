import numpy as np
import pandas as pd
import pytest

from src.risk_metrics import (
    annualized_volatility,
    correlation_matrix,
    expected_shortfall,
    historical_var,
    max_drawdown,
)


def test_annualized_volatility_scales_daily_standard_deviation():
    returns = pd.Series([0.01, 0.02, -0.01, 0.00])

    result = annualized_volatility(returns)

    assert result == returns.std() * np.sqrt(252)


def test_historical_var_returns_positive_loss_magnitude():
    returns = pd.Series([-0.10, -0.05, 0.00, 0.02, 0.04])

    result = historical_var(returns, confidence_level=0.80)

    assert result > 0
    assert result == pytest.approx(0.06)


def test_expected_shortfall_returns_positive_average_tail_loss():
    returns = pd.Series([-0.10, -0.05, 0.00, 0.02, 0.04])

    result = expected_shortfall(returns, confidence_level=0.80)

    assert result > 0
    assert result == pytest.approx(0.10)


def test_max_drawdown_returns_positive_loss_magnitude():
    cumulative_returns = pd.Series([0.00, 0.10, 0.05, -0.10, 0.00])

    result = max_drawdown(cumulative_returns)

    assert result > 0
    assert result == pytest.approx(0.18181818181818188)


def test_correlation_matrix_matches_pandas_corr():
    asset_returns = pd.DataFrame(
        {
            "SPY": [0.01, 0.02, -0.01],
            "QQQ": [0.02, 0.04, -0.02],
        }
    )

    result = correlation_matrix(asset_returns)

    pd.testing.assert_frame_equal(result, asset_returns.corr())
