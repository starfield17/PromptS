from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from ..models import StructuredError


def fetch_prices(tickers: list[str], start: str | None = None, end: str | None = None) -> tuple[pd.DataFrame, StructuredError | None]:
    try:
        import yfinance as yf
    except Exception as exc:
        return pd.DataFrame(), StructuredError(module="yfinance.prices", message=f"yfinance unavailable: {exc}", missing_inputs=["yfinance"])

    if not start:
        start = (date.today() - timedelta(days=365)).isoformat()
    try:
        data = yf.download(tickers=tickers, start=start, end=end, progress=False, group_by="ticker", auto_adjust=False)
    except Exception as exc:
        return pd.DataFrame(), StructuredError(module="yfinance.prices", message=str(exc))

    rows: list[dict[str, object]] = []
    if data.empty:
        return pd.DataFrame(), None
    if len(tickers) == 1:
        ticker = tickers[0]
        frame = data.reset_index()
        for _, row in frame.iterrows():
            rows.append({"ticker": ticker, "date": str(row["Date"])[:10], "close": row.get("Close"), "volume": row.get("Volume")})
    else:
        for ticker in tickers:
            if ticker not in data.columns.get_level_values(0):
                continue
            frame = data[ticker].reset_index()
            for _, row in frame.iterrows():
                rows.append({"ticker": ticker, "date": str(row["Date"])[:10], "close": row.get("Close"), "volume": row.get("Volume")})
    return pd.DataFrame(rows), None


def fetch_financials(tickers: list[str]) -> tuple[pd.DataFrame, StructuredError | None]:
    try:
        import yfinance as yf
    except Exception as exc:
        return pd.DataFrame(), StructuredError(module="yfinance.financials", message=f"yfinance unavailable: {exc}", missing_inputs=["yfinance"])

    rows: list[dict[str, object]] = []
    for ticker in tickers:
        try:
            obj = yf.Ticker(ticker)
            info = obj.info or {}
            rows.append(
                {
                    "ticker": ticker,
                    "company": info.get("shortName") or info.get("longName") or ticker,
                    "market_cap": info.get("marketCap"),
                    "revenue": info.get("totalRevenue"),
                    "gross_margin": info.get("grossMargins"),
                    "operating_margin": info.get("operatingMargins"),
                    "capex": None,
                    "source_id": f"database_yfinance_{ticker}",
                }
            )
        except Exception:
            continue
    return pd.DataFrame(rows), None
