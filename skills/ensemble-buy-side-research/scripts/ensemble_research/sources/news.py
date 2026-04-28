from __future__ import annotations

import hashlib
import re
from datetime import date
from typing import Iterable
from urllib.parse import quote_plus

import requests

from ..analysis.trigger import classify_trigger
from ..config import Settings, slugify
from ..models import NewsItem, NewsPack, Source, StructuredError
from .web import extract_url


DEFAULT_RSS = [
    "https://www.sec.gov/news/pressreleases.rss",
    "https://www.prnewswire.com/news-releases/news-releases-list.rss",
    "https://feeds.marketwatch.com/marketwatch/topstories/",
]


def _stable_id(title: str, url: str | None = None) -> str:
    raw = f"{title}|{url or ''}".encode("utf-8")
    return f"news_{hashlib.sha1(raw).hexdigest()[:12]}"


def _dedupe(items: Iterable[NewsItem]) -> list[NewsItem]:
    try:
        from rapidfuzz import fuzz
    except Exception:
        fuzz = None

    kept: list[NewsItem] = []
    for item in items:
        duplicate = False
        for existing in kept:
            if item.url and existing.url and item.url == existing.url:
                duplicate = True
                break
            if fuzz is not None and fuzz.token_set_ratio(item.title, existing.title) >= 95:
                duplicate = True
                break
            if fuzz is None and item.title.lower() == existing.title.lower():
                duplicate = True
                break
        if not duplicate:
            kept.append(item)
    return kept


def _from_feed(query: str, feed_url: str, settings: Settings, fetch_text: bool) -> tuple[list[NewsItem], StructuredError | None]:
    try:
        import feedparser
    except Exception as exc:
        return [], StructuredError(module="news.rss", message=f"feedparser unavailable: {exc}", missing_inputs=["feedparser"])

    try:
        parsed = feedparser.parse(feed_url)
    except Exception as exc:
        return [], StructuredError(module="news.rss", message=str(exc))

    query_terms = [part.lower() for part in re.split(r"\W+", query) if len(part) > 2]
    items: list[NewsItem] = []
    for entry in parsed.entries[:80]:
        title = getattr(entry, "title", "")
        summary = getattr(entry, "summary", "")
        haystack = f"{title} {summary}".lower()
        if query_terms and not any(term in haystack for term in query_terms):
            continue
        url = getattr(entry, "link", None)
        text = None
        if fetch_text and url:
            text = extract_url(url, settings.request_timeout).get("text") or None
        item = NewsItem(
            id=_stable_id(title, url),
            title=title,
            url=url,
            publisher=getattr(parsed.feed, "title", None),
            date=getattr(entry, "published", None) or getattr(entry, "updated", None),
            summary=re.sub(r"<[^>]+>", "", summary)[:1000] if summary else None,
            text=text,
            trigger_type=classify_trigger(f"{title}\n{summary}"),
            confidence="medium",
        )
        item.source_id = item.id
        items.append(item)
    return items, None


def _from_gdelt(query: str, start_date: str | None, end_date: str | None, settings: Settings) -> tuple[list[NewsItem], StructuredError | None]:
    params = {
        "query": query,
        "mode": "ArtList",
        "format": "json",
        "maxrecords": 75,
        "sort": "HybridRel",
    }
    if start_date:
        params["startdatetime"] = start_date.replace("-", "") + "000000"
    if end_date:
        params["enddatetime"] = end_date.replace("-", "") + "235959"
    try:
        response = requests.get("https://api.gdeltproject.org/api/v2/doc/doc", params=params, timeout=settings.request_timeout)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        return [], StructuredError(module="news.gdelt", message=str(exc))

    items: list[NewsItem] = []
    for article in payload.get("articles", []):
        title = article.get("title") or ""
        url = article.get("url")
        item = NewsItem(
            id=_stable_id(title, url),
            title=title,
            url=url,
            publisher=article.get("sourceCountry") or article.get("domain"),
            date=article.get("seendate"),
            summary=article.get("title"),
            trigger_type=classify_trigger(title),
            confidence="medium",
        )
        item.source_id = item.id
        items.append(item)
    return items, None


def _from_newsapi(query: str, start_date: str | None, end_date: str | None, settings: Settings) -> tuple[list[NewsItem], StructuredError | None]:
    if not settings.newsapi_key:
        return [], StructuredError(module="news.newsapi", message="NEWSAPI_KEY not set", missing_inputs=["NEWSAPI_KEY"])
    params = {
        "q": query,
        "apiKey": settings.newsapi_key,
        "language": "en",
        "sortBy": "relevancy",
        "pageSize": 75,
    }
    if start_date:
        params["from"] = start_date
    if end_date:
        params["to"] = end_date
    try:
        response = requests.get("https://newsapi.org/v2/everything", params=params, timeout=settings.request_timeout)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        return [], StructuredError(module="news.newsapi", message=str(exc))

    items: list[NewsItem] = []
    for article in payload.get("articles", []):
        title = article.get("title") or ""
        url = article.get("url")
        text = article.get("content") or article.get("description")
        item = NewsItem(
            id=_stable_id(title, url),
            title=title,
            url=url,
            publisher=(article.get("source") or {}).get("name"),
            date=article.get("publishedAt"),
            summary=article.get("description"),
            text=text,
            trigger_type=classify_trigger(f"{title}\n{text or ''}"),
            confidence="medium",
        )
        item.source_id = item.id
        items.append(item)
    return items, None


def ingest_news(
    query: str,
    regions: list[str],
    settings: Settings,
    start_date: str | None = None,
    end_date: str | None = None,
    rss_urls: list[str] | None = None,
    fetch_text: bool = False,
) -> NewsPack:
    items: list[NewsItem] = []
    errors: list[StructuredError] = []

    gdelt_items, error = _from_gdelt(query, start_date, end_date, settings)
    items.extend(gdelt_items)
    if error:
        errors.append(error)

    if settings.newsapi_key:
        newsapi_items, error = _from_newsapi(query, start_date, end_date, settings)
        items.extend(newsapi_items)
        if error:
            errors.append(error)

    for feed in rss_urls or DEFAULT_RSS:
        feed_items, error = _from_feed(query, feed, settings, fetch_text)
        items.extend(feed_items)
        if error:
            errors.append(error)

    items = _dedupe(items)
    sources = [
        Source(
            id=item.id,
            title=item.title,
            url=item.url,
            type="news",
            publisher=item.publisher,
            date=item.date,
            reliability=4 if item.publisher else 3,
            relevant_claims=[item.summary] if item.summary else [],
            notes=f"Trigger type: {item.trigger_type}",
        )
        for item in items
    ]

    return NewsPack(query=query, items=items, sources=sources, errors=errors)


def manual_news_item(title: str, query: str) -> NewsItem:
    item = NewsItem(
        id=f"news_{date.today().isoformat().replace('-', '')}_{slugify(title)}",
        title=title,
        summary=title,
        trigger_type=classify_trigger(title),
        confidence="low",
    )
    item.source_id = item.id
    return item
