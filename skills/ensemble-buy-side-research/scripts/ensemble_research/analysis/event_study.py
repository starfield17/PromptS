from __future__ import annotations

from datetime import timedelta
from typing import Any

import pandas as pd


WINDOWS = [(-1, 1), (0, 5), (0, 20), (0, 60)]


def run_event_study(events: list[dict[str, Any]], prices: pd.DataFrame) -> pd.DataFrame:
    if prices.empty or not events:
        return pd.DataFrame(columns=["event_id", "ticker", "event_date", "window", "return"])
    frame = prices.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    rows: list[dict[str, Any]] = []
    for event in events:
        event_date = pd.to_datetime(event.get("date") or event.get("event_date"))
        tickers = event.get("tickers") or event.get("ticker") or []
        if isinstance(tickers, str):
            tickers = [tickers]
        for ticker in tickers:
            sub = frame[frame["ticker"] == ticker].sort_values("date")
            if sub.empty:
                continue
            for start_offset, end_offset in WINDOWS:
                start_date = event_date + timedelta(days=start_offset)
                end_date = event_date + timedelta(days=end_offset)
                before = sub[sub["date"] <= start_date].tail(1)
                after = sub[sub["date"] <= end_date].tail(1)
                if before.empty or after.empty:
                    continue
                start_close = float(before.iloc[0]["close"])
                end_close = float(after.iloc[0]["close"])
                if start_close:
                    rows.append(
                        {
                            "event_id": event.get("id") or event.get("title") or "event",
                            "ticker": ticker,
                            "event_date": event_date.date().isoformat(),
                            "window": f"{start_offset},{end_offset}",
                            "return": end_close / start_close - 1,
                        }
                    )
    return pd.DataFrame(rows)
