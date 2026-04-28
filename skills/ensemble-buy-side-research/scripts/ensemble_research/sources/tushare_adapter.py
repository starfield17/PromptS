from __future__ import annotations

import pandas as pd

from ..models import StructuredError


def fetch_tushare_daily(tickers: list[str], token: str | None, start: str | None = None, end: str | None = None) -> tuple[pd.DataFrame, StructuredError | None]:
    if not token:
        return pd.DataFrame(), StructuredError(module="tushare.daily", message="TUSHARE_TOKEN not set", missing_inputs=["TUSHARE_TOKEN"])
    try:
        import tushare as ts
    except Exception as exc:
        return pd.DataFrame(), StructuredError(module="tushare.daily", message=f"tushare unavailable: {exc}", missing_inputs=["tushare"])

    pro = ts.pro_api(token)
    rows: list[dict[str, object]] = []
    for ticker in tickers:
        ts_code = ticker if "." in ticker else f"{ticker}.SZ"
        try:
            frame = pro.daily(ts_code=ts_code, start_date=(start or "20200101").replace("-", ""), end_date=(end or "20991231").replace("-", ""))
            for _, row in frame.iterrows():
                rows.append({"ticker": ticker, "date": str(row.get("trade_date")), "close": row.get("close"), "volume": row.get("vol")})
        except Exception:
            continue
    return pd.DataFrame(rows), None
