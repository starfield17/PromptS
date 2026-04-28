from __future__ import annotations

import pandas as pd

from ..models import StructuredError


def fetch_cn_prices(tickers: list[str], start: str | None = None, end: str | None = None) -> tuple[pd.DataFrame, StructuredError | None]:
    try:
        import akshare as ak
    except Exception as exc:
        return pd.DataFrame(), StructuredError(module="akshare.prices", message=f"akshare unavailable: {exc}", missing_inputs=["akshare"])

    rows: list[dict[str, object]] = []
    for ticker in tickers:
        symbol = ticker.split(".")[0]
        try:
            frame = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=(start or "20200101").replace("-", ""), end_date=(end or "20991231").replace("-", ""), adjust="")
            if frame.empty:
                continue
            for _, row in frame.iterrows():
                rows.append({"ticker": ticker, "date": str(row.get("日期"))[:10], "close": row.get("收盘"), "volume": row.get("成交量")})
        except Exception:
            continue
    return pd.DataFrame(rows), None


def fetch_cn_financials(tickers: list[str]) -> tuple[pd.DataFrame, StructuredError | None]:
    try:
        import akshare as ak  # noqa: F401
    except Exception as exc:
        return pd.DataFrame(), StructuredError(module="akshare.financials", message=f"akshare unavailable: {exc}", missing_inputs=["akshare"])

    rows = [{"ticker": ticker, "company": ticker, "source_id": f"database_akshare_{ticker}"} for ticker in tickers]
    return pd.DataFrame(rows), None
