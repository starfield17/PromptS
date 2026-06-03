#!/usr/bin/env python
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import pandas as pd
import typer
from rich.console import Console

from ensemble_research.analysis.consensus import detect_consensus as detect_consensus_payload
from ensemble_research.analysis.entities import extract_entities_from_file, extract_entities_from_records
from ensemble_research.analysis.event_study import run_event_study
from ensemble_research.analysis.scoring import score_value_chain
from ensemble_research.analysis.trigger import classify_trigger
from ensemble_research.analysis.value_chain import build_value_chain as build_value_chain_artifact
from ensemble_research.analysis.watchlist import generate_watchlist as generate_watchlist_artifact
from ensemble_research.config import load_settings, parse_csv, now_utc
from ensemble_research.io import read_json, read_table, write_json, write_table
from ensemble_research.models import (
    EntityPack,
    RunManifest,
    SourcePack,
    StructuredError,
    Thesis,
    ValueChain,
)
from ensemble_research.rendering.markdown import build_memo, render_memo
from ensemble_research.sources import akshare_adapter, sec, tushare_adapter, yfinance_adapter
from ensemble_research.sources.news import ingest_news as ingest_news_source


app = typer.Typer(help="Ensemble Buy-side Research data pipeline")
console = Console()


def _status(path: Path) -> None:
    console.print(f"[green]wrote[/green] {path}")


def _is_cn_ticker(ticker: str) -> bool:
    upper = ticker.upper()
    return upper.endswith((".SS", ".SZ", ".HK")) or (upper.isdigit() and len(upper) == 6)


@app.command("ingest-news")
def ingest_news(
    query: str = typer.Option(..., help="Search query or research direction."),
    regions: str = typer.Option("US,CN", help="Comma-separated regions."),
    out: Path = typer.Option(..., help="Output JSON path."),
    start_date: Optional[str] = typer.Option(None),
    end_date: Optional[str] = typer.Option(None),
    fetch_text: bool = typer.Option(False, help="Fetch article bodies when URLs are available."),
) -> None:
    settings = load_settings()
    pack = ingest_news_source(query=query, regions=parse_csv(regions), settings=settings, start_date=start_date, end_date=end_date, fetch_text=fetch_text)
    _status(write_json(out, pack))


@app.command("ingest-filings")
def ingest_filings(
    tickers: str = typer.Option(..., help="Comma-separated tickers."),
    out: Path = typer.Option(..., help="Output JSON path."),
    limit: int = typer.Option(12, help="Recent SEC filings per ticker."),
) -> None:
    settings = load_settings()
    rows: list[dict[str, object]] = []
    sources = []
    errors: list[StructuredError] = []
    for ticker in parse_csv(tickers):
        submissions, error = sec.fetch_submissions(ticker, settings.sec_user_agent, settings.request_timeout)
        if error:
            errors.append(error)
            continue
        if submissions:
            recent = sec.extract_recent_filings(submissions, ticker, limit=limit)
            rows.extend(recent)
            sources.extend(sec.source_from_filing(row) for row in recent)
    payload = {
        "schema_version": "0.1.0",
        "generated_at": now_utc(),
        "filings": rows,
        "sources": [source.model_dump(exclude_none=True) for source in sources],
        "errors": [error.model_dump(exclude_none=True) for error in errors],
    }
    _status(write_json(out, payload))


@app.command("ingest-financials")
def ingest_financials(
    tickers: str = typer.Option(..., help="Comma-separated tickers."),
    out: Path = typer.Option(..., help="Output Parquet/CSV/JSON path."),
    start_date: Optional[str] = typer.Option(None),
    end_date: Optional[str] = typer.Option(None),
    prices_out: Optional[Path] = typer.Option(None, help="Optional price output path."),
) -> None:
    settings = load_settings()
    all_tickers = parse_csv(tickers)
    cn_tickers = [ticker for ticker in all_tickers if _is_cn_ticker(ticker)]
    global_tickers = [ticker for ticker in all_tickers if ticker not in cn_tickers]
    frames: list[pd.DataFrame] = []
    errors: list[StructuredError] = []

    if global_tickers:
        frame, error = yfinance_adapter.fetch_financials(global_tickers)
        if error:
            errors.append(error)
        if not frame.empty:
            frames.append(frame)
    if cn_tickers:
        frame, error = akshare_adapter.fetch_cn_financials(cn_tickers)
        if error:
            errors.append(error)
        if not frame.empty:
            frames.append(frame)
    financials = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["ticker", "company", "source_id"])
    _status(write_table(out, financials))

    if prices_out:
        price_frames: list[pd.DataFrame] = []
        if global_tickers:
            frame, error = yfinance_adapter.fetch_prices(global_tickers, start=start_date, end=end_date)
            if error:
                errors.append(error)
            if not frame.empty:
                price_frames.append(frame)
        if cn_tickers:
            frame, error = tushare_adapter.fetch_tushare_daily(cn_tickers, settings.tushare_token, start=start_date, end=end_date)
            if error:
                errors.append(error)
            if frame.empty:
                frame, error = akshare_adapter.fetch_cn_prices(cn_tickers, start=start_date, end=end_date)
                if error:
                    errors.append(error)
            if not frame.empty:
                price_frames.append(frame)
        prices = pd.concat(price_frames, ignore_index=True) if price_frames else pd.DataFrame(columns=["ticker", "date", "close", "volume"])
        _status(write_table(prices_out, prices))

    if errors:
        error_path = out.with_suffix(".errors.json")
        write_json(error_path, {"schema_version": "0.1.0", "generated_at": now_utc(), "errors": [error.model_dump(exclude_none=True) for error in errors]})
        _status(error_path)


@app.command("extract-entities")
def extract_entities(
    input: Path = typer.Option(..., help="Input JSON artifact."),
    out: Path = typer.Option(..., help="Output JSON path."),
) -> None:
    pack = extract_entities_from_file(str(input))
    _status(write_json(out, pack))


@app.command("build-value-chain")
def build_value_chain(
    direction: str = typer.Option(...),
    entities: Optional[Path] = typer.Option(None, help="Entity pack JSON."),
    out: Path = typer.Option(...),
) -> None:
    entity_pack = EntityPack.model_validate(read_json(entities)) if entities else EntityPack()
    value_chain = build_value_chain_artifact(direction, entity_pack)
    _status(write_json(out, value_chain))


@app.command("score-profit-pool")
def score_profit_pool(
    value_chain: Path = typer.Option(...),
    out: Path = typer.Option(...),
    financials: Optional[Path] = typer.Option(None),
) -> None:
    chain = ValueChain.model_validate(read_json(value_chain))
    financial_frame = read_table(financials) if financials and financials.exists() else None
    scorecard = score_value_chain(chain, financial_frame)
    _status(write_json(out, scorecard))


@app.command("detect-consensus")
def detect_consensus(
    news: Path = typer.Option(...),
    out: Path = typer.Option(...),
    prices: Optional[Path] = typer.Option(None, help="Reserved for price-action enrichment."),
) -> None:
    payload = read_json(news)
    consensus = detect_consensus_payload(payload)
    _status(write_json(out, consensus))


@app.command("generate-watchlist")
def generate_watchlist(
    out: Path = typer.Option(...),
    thesis: Optional[Path] = typer.Option(None),
    value_chain: Optional[Path] = typer.Option(None),
) -> None:
    thesis_obj = Thesis.model_validate(read_json(thesis)) if thesis and thesis.exists() else None
    value_chain_obj = ValueChain.model_validate(read_json(value_chain)) if value_chain and value_chain.exists() else None
    watchlist = generate_watchlist_artifact(thesis_obj, value_chain_obj)
    _status(write_json(out, watchlist))


@app.command("event-study")
def event_study(
    events: Path = typer.Option(...),
    prices: Path = typer.Option(...),
    out: Path = typer.Option(...),
) -> None:
    event_payload = read_json(events)
    event_rows = event_payload.get("events", event_payload) if isinstance(event_payload, dict) else event_payload
    price_frame = read_table(prices)
    result = run_event_study(event_rows, price_frame)
    _status(write_table(out, result))


@app.command("export-memo")
def export_memo(
    run: Path = typer.Option(..., help="Run directory containing value_chain/consensus/watchlist/scores artifacts."),
    out: Path = typer.Option(...),
    output_format: str = typer.Option("markdown", "--format", help="markdown only in v0.1.0."),
) -> None:
    if output_format != "markdown":
        raise typer.BadParameter("Only markdown export is implemented in v0.1.0")
    manifest_path = run / "run_manifest.json"
    direction = run.name
    if manifest_path.exists():
        manifest = read_json(manifest_path)
        direction = manifest.get("direction", direction)
    value_chain = ValueChain.model_validate(read_json(run / "value_chain.json")) if (run / "value_chain.json").exists() else None
    consensus = detect_consensus_payload({"items": []})
    if (run / "consensus.json").exists():
        from ensemble_research.models import Consensus

        consensus = Consensus.model_validate(read_json(run / "consensus.json"))
    watchlist = None
    if (run / "watchlist.json").exists():
        from ensemble_research.models import Watchlist

        watchlist = Watchlist.model_validate(read_json(run / "watchlist.json"))
    scorecard = None
    if (run / "scores.json").exists():
        from ensemble_research.models import ScoreCard

        scorecard = ScoreCard.model_validate(read_json(run / "scores.json"))
    trigger = {"description": "Source needed", "type": "Unknown"}
    if (run / "news_items.json").exists():
        news = read_json(run / "news_items.json")
        items = news.get("items", [])
        if items:
            trigger = {"description": items[0].get("title", "Source needed"), "type": items[0].get("trigger_type", "Unknown")}
    memo = build_memo(direction, value_chain, consensus, watchlist, scorecard, trigger)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_memo(memo), encoding="utf-8")
    _status(out)


@app.command("validate")
def validate(run: Path = typer.Option(..., help="Run directory to validate.")) -> None:
    issues: list[str] = []
    required = ["value_chain.json", "scores.json", "watchlist.json", "research_memo.md"]
    for name in required:
        if not (run / name).exists():
            issues.append(f"missing {name}")
    for path in run.glob("*.json"):
        try:
            read_json(path)
        except Exception as exc:
            issues.append(f"invalid JSON {path.name}: {exc}")
    if issues:
        for issue in issues:
            console.print(f"[red]issue[/red] {issue}")
        raise typer.Exit(code=1)
    console.print("[green]run artifacts validated[/green]")


@app.command("run")
def run_pipeline(
    direction: str = typer.Option(...),
    out: Path = typer.Option(..., help="Run output directory."),
    regions: str = typer.Option("US,CN"),
    tickers: str = typer.Option("", help="Optional comma-separated company tickers."),
    start_date: Optional[str] = typer.Option(None),
    end_date: Optional[str] = typer.Option(None),
    fetch_text: bool = typer.Option(False),
) -> None:
    settings = load_settings()
    out.mkdir(parents=True, exist_ok=True)
    artifacts: dict[str, str] = {}
    errors: list[StructuredError] = []

    run_config = {
        "schema_version": "0.1.0",
        "generated_at": now_utc(),
        "direction": direction,
        "regions": parse_csv(regions),
        "tickers": parse_csv(tickers),
        "start_date": start_date,
        "end_date": end_date,
    }
    write_json(out / "run_config.json", run_config)
    artifacts["run_config"] = "run_config.json"

    news_pack = ingest_news_source(direction, parse_csv(regions), settings, start_date=start_date, end_date=end_date, fetch_text=fetch_text)
    write_json(out / "news_items.json", news_pack)
    artifacts["news"] = "news_items.json"
    errors.extend(news_pack.errors)

    filing_sources = []
    filing_rows: list[dict[str, object]] = []
    all_tickers = parse_csv(tickers)
    if all_tickers:
        for ticker in all_tickers:
            submissions, error = sec.fetch_submissions(ticker, settings.sec_user_agent, settings.request_timeout)
            if error:
                errors.append(error)
                continue
            if submissions:
                recent = sec.extract_recent_filings(submissions, ticker)
                filing_rows.extend(recent)
                filing_sources.extend(sec.source_from_filing(row) for row in recent)
    filings_payload = {
        "schema_version": "0.1.0",
        "generated_at": now_utc(),
        "filings": filing_rows,
        "sources": [source.model_dump(exclude_none=True) for source in filing_sources],
    }
    write_json(out / "filings.json", filings_payload)
    artifacts["filings"] = "filings.json"

    source_pack = SourcePack(sources=news_pack.sources + filing_sources, errors=errors)
    write_json(out / "source_pack.json", source_pack)
    artifacts["source_pack"] = "source_pack.json"

    if all_tickers:
        global_tickers = [ticker for ticker in all_tickers if not _is_cn_ticker(ticker)]
        cn_tickers = [ticker for ticker in all_tickers if _is_cn_ticker(ticker)]
        frames: list[pd.DataFrame] = []
        if global_tickers:
            frame, error = yfinance_adapter.fetch_financials(global_tickers)
            if error:
                errors.append(error)
            if not frame.empty:
                frames.append(frame)
        if cn_tickers:
            frame, error = akshare_adapter.fetch_cn_financials(cn_tickers)
            if error:
                errors.append(error)
            if not frame.empty:
                frames.append(frame)
        financials = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["ticker", "company", "source_id"])
    else:
        financials = pd.DataFrame(columns=["ticker", "company", "source_id"])
    write_table(out / "financials.parquet", financials)
    artifacts["financials"] = "financials.parquet"

    records = []
    records.extend([item.model_dump(exclude_none=True) for item in news_pack.items])
    records.extend(filing_rows)
    entities = extract_entities_from_records(records)
    write_json(out / "entities.json", entities)
    artifacts["entities"] = "entities.json"

    value_chain = build_value_chain_artifact(direction, entities)
    write_json(out / "value_chain.json", value_chain)
    artifacts["value_chain"] = "value_chain.json"

    scorecard = score_value_chain(value_chain, financials)
    write_json(out / "scores.json", scorecard)
    artifacts["scores"] = "scores.json"

    consensus = detect_consensus_payload(news_pack.model_dump(exclude_none=True))
    write_json(out / "consensus.json", consensus)
    artifacts["consensus"] = "consensus.json"

    watchlist = generate_watchlist_artifact(value_chain=value_chain)
    write_json(out / "watchlist.json", watchlist)
    artifacts["watchlist"] = "watchlist.json"

    first_news = news_pack.items[0] if news_pack.items else None
    trigger = {
        "description": first_news.title if first_news else direction,
        "type": first_news.trigger_type if first_news else classify_trigger(direction),
        "why_now": "Source needed",
        "real_variable_changed": "Unclear",
    }
    memo = build_memo(direction, value_chain, consensus, watchlist, scorecard, trigger)
    memo_path = out / "research_memo.md"
    memo_path.write_text(render_memo(memo), encoding="utf-8")
    artifacts["memo"] = "research_memo.md"

    manifest = RunManifest(direction=direction, regions=parse_csv(regions), artifacts=artifacts, errors=errors)
    write_json(out / "run_manifest.json", manifest)
    _status(out / "run_manifest.json")


if __name__ == "__main__":
    app()
