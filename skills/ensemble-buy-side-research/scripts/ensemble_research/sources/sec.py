from __future__ import annotations

import time
from typing import Any

import requests

from ..models import Source, StructuredError


SEC_BASE = "https://data.sec.gov"
SEC_ARCHIVES = "https://www.sec.gov/Archives/edgar/data"


def _headers(user_agent: str) -> dict[str, str]:
    return {"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"}


def _get_json(url: str, user_agent: str, timeout: int) -> dict[str, Any]:
    response = requests.get(url, headers=_headers(user_agent), timeout=timeout)
    response.raise_for_status()
    time.sleep(0.12)
    return response.json()


def company_tickers(user_agent: str, timeout: int = 20) -> dict[str, str]:
    payload = _get_json("https://www.sec.gov/files/company_tickers.json", user_agent, timeout)
    mapping: dict[str, str] = {}
    for item in payload.values():
        ticker = str(item.get("ticker", "")).upper()
        cik = str(item.get("cik_str", "")).zfill(10)
        if ticker and cik:
            mapping[ticker] = cik
    return mapping


def ticker_to_cik(ticker: str, user_agent: str, timeout: int = 20) -> str | None:
    return company_tickers(user_agent, timeout).get(ticker.upper())


def fetch_submissions(ticker: str, user_agent: str | None, timeout: int = 20) -> tuple[dict[str, Any] | None, StructuredError | None]:
    if not user_agent:
        return None, StructuredError(module="sec.submissions", message="SEC_USER_AGENT not set", missing_inputs=["SEC_USER_AGENT"])
    try:
        cik = ticker_to_cik(ticker, user_agent, timeout)
        if not cik:
            return None, StructuredError(module="sec.submissions", message=f"No CIK found for ticker {ticker}")
        return _get_json(f"{SEC_BASE}/submissions/CIK{cik}.json", user_agent, timeout), None
    except Exception as exc:
        return None, StructuredError(module="sec.submissions", message=str(exc))


def fetch_companyfacts(ticker: str, user_agent: str | None, timeout: int = 20) -> tuple[dict[str, Any] | None, StructuredError | None]:
    if not user_agent:
        return None, StructuredError(module="sec.companyfacts", message="SEC_USER_AGENT not set", missing_inputs=["SEC_USER_AGENT"])
    try:
        cik = ticker_to_cik(ticker, user_agent, timeout)
        if not cik:
            return None, StructuredError(module="sec.companyfacts", message=f"No CIK found for ticker {ticker}")
        return _get_json(f"{SEC_BASE}/api/xbrl/companyfacts/CIK{cik}.json", user_agent, timeout), None
    except Exception as exc:
        return None, StructuredError(module="sec.companyfacts", message=str(exc))


def extract_recent_filings(submissions: dict[str, Any], ticker: str, limit: int = 12) -> list[dict[str, Any]]:
    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    filing_dates = recent.get("filingDate", [])
    report_dates = recent.get("reportDate", [])
    primary_docs = recent.get("primaryDocument", [])
    company = submissions.get("name") or ticker

    rows: list[dict[str, Any]] = []
    for idx, form in enumerate(forms):
        if form not in {"10-K", "10-Q", "20-F", "6-K", "8-K"}:
            continue
        accession = accessions[idx]
        cik_no_zeros = str(submissions.get("cik", "")).lstrip("0")
        accession_no_dashes = accession.replace("-", "")
        url = f"{SEC_ARCHIVES}/{cik_no_zeros}/{accession_no_dashes}/{primary_docs[idx]}"
        rows.append(
            {
                "company": company,
                "ticker": ticker.upper(),
                "period": report_dates[idx] or filing_dates[idx],
                "form": form,
                "filing_date": filing_dates[idx],
                "accession": accession,
                "url": url,
                "source_id": f"filing_{ticker.upper()}_{report_dates[idx] or filing_dates[idx]}_{form.replace('-', '')}",
            }
        )
        if len(rows) >= limit:
            break
    return rows


def _latest_usd_value(facts: dict[str, Any], tag: str) -> float | None:
    units = facts.get("facts", {}).get("us-gaap", {}).get(tag, {}).get("units", {})
    values = units.get("USD") or units.get("shares") or []
    annual_or_quarter = [v for v in values if v.get("form") in {"10-K", "10-Q", "20-F"} and "val" in v]
    if not annual_or_quarter:
        return None
    latest = sorted(annual_or_quarter, key=lambda v: (v.get("end") or "", v.get("filed") or ""))[-1]
    try:
        return float(latest["val"])
    except Exception:
        return None


def extract_companyfacts_metrics(facts: dict[str, Any], ticker: str) -> dict[str, Any]:
    revenue = _latest_usd_value(facts, "Revenues") or _latest_usd_value(facts, "RevenueFromContractWithCustomerExcludingAssessedTax")
    gross_profit = _latest_usd_value(facts, "GrossProfit")
    operating_income = _latest_usd_value(facts, "OperatingIncomeLoss")
    capex = _latest_usd_value(facts, "PaymentsToAcquirePropertyPlantAndEquipment")
    inventory = _latest_usd_value(facts, "InventoryNet")
    return {
        "ticker": ticker.upper(),
        "company": facts.get("entityName") or ticker.upper(),
        "revenue": revenue,
        "gross_profit": gross_profit,
        "gross_margin": (gross_profit / revenue) if revenue and gross_profit is not None else None,
        "operating_income": operating_income,
        "operating_margin": (operating_income / revenue) if revenue and operating_income is not None else None,
        "capex": capex,
        "inventory": inventory,
        "source_id": f"database_sec_companyfacts_{ticker.upper()}",
    }


def source_from_filing(row: dict[str, Any]) -> Source:
    return Source(
        id=row["source_id"],
        title=f"{row['company']} {row['form']} {row['period']}",
        url=row.get("url"),
        type="filing",
        publisher="SEC EDGAR",
        date=row.get("filing_date"),
        reliability=5,
        relevant_claims=[f"Recent {row['form']} filing metadata for {row['ticker']}"],
    )
