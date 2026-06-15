from __future__ import annotations

from collections.abc import Sequence

import pandas as pd
import yfinance as yf


def download_price_data(
    tickers: str | Sequence[str],
    start_date: str,
    end_date: str | None = None,
) -> pd.DataFrame:
    """Download adjusted close prices for one or more tickers."""
    if isinstance(tickers, str):
        ticker_list = [tickers]
    else:
        ticker_list = list(tickers)

    if not ticker_list:
        raise ValueError("At least one ticker is required.")

    data = yf.download(
        ticker_list if len(ticker_list) > 1 else ticker_list[0],
        start=start_date,
        end=end_date,
        auto_adjust=False,
        progress=False,
    )

    if data.empty:
        raise ValueError(
            f"No market data returned for tickers {ticker_list} from {start_date} to {end_date}."
        )

    if isinstance(data.columns, pd.MultiIndex):
        if "Adj Close" not in data.columns.get_level_values(0):
            raise ValueError("Downloaded data does not include adjusted close prices.")
        prices = data["Adj Close"]
    else:
        if "Adj Close" not in data.columns:
            raise ValueError("Downloaded data does not include adjusted close prices.")
        prices = data[["Adj Close"]].rename(columns={"Adj Close": ticker_list[0]})

    prices = prices.dropna(how="all")

    if prices.empty:
        raise ValueError(
            f"No adjusted close price data available for tickers {ticker_list}."
        )

    prices.columns = [str(column) for column in prices.columns]
    return prices
