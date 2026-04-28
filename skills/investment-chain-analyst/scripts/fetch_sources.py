#!/usr/bin/env python3
"""Fetch public URL/RSS/Atom sources into JSONL using only Python standard libraries.

The script is intended for research source gathering. Do not use it to bypass
paywalls, login walls, robots.txt restrictions, or website terms.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.skip = 0
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self.in_title = False

    def handle_starttag(self, tag: str, attrs) -> None:  # type: ignore[override]
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg", "canvas"}:
            self.skip += 1
        if tag == "title":
            self.in_title = True
        if tag in {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4"}:
            self.text_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:  # type: ignore[override]
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg", "canvas"} and self.skip:
            self.skip -= 1
        if tag == "title":
            self.in_title = False
        if tag in {"p", "div", "li", "tr", "h1", "h2", "h3", "h4"}:
            self.text_parts.append("\n")

    def handle_data(self, data: str) -> None:  # type: ignore[override]
        if self.skip:
            return
        text = data.strip()
        if not text:
            return
        if self.in_title:
            self.title_parts.append(text)
        self.text_parts.append(text + " ")

    def result(self) -> tuple[str, str]:
        title = " ".join(self.title_parts).strip()
        text = "".join(self.text_parts)
        text = html.unescape(text)
        text = re.sub(r"[ \t\r\f\v]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return title, text.strip()


def read_url(url: str, timeout: int, user_agent: str) -> tuple[str, bytes, str]:
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        content_type = resp.headers.get("Content-Type", "")
        final_url = resp.geturl()
        raw = resp.read()
    return final_url, raw, content_type


def extract_page(url: str, timeout: int, user_agent: str) -> dict:
    fetched_at = dt.datetime.now(dt.timezone.utc).isoformat()
    record = {"source_type": "url", "url": url, "fetched_at": fetched_at}
    try:
        final_url, raw, content_type = read_url(url, timeout, user_agent)
        charset = "utf-8"
        match = re.search(r"charset=([^;]+)", content_type, re.I)
        if match:
            charset = match.group(1).strip()
        text_raw = raw.decode(charset, errors="replace")
        parser = TextExtractor()
        parser.feed(text_raw)
        title, text = parser.result()
        record.update({
            "status": "ok",
            "final_url": final_url,
            "content_type": content_type,
            "title": title,
            "text": text,
            "excerpt": text[:500],
        })
    except Exception as exc:  # noqa: BLE001
        record.update({"status": "error", "error": f"{type(exc).__name__}: {exc}"})
    return record


def iter_feed_items(feed_url: str, timeout: int, user_agent: str, max_items: int) -> Iterable[dict]:
    fetched_at = dt.datetime.now(dt.timezone.utc).isoformat()
    try:
        final_url, raw, content_type = read_url(feed_url, timeout, user_agent)
        root = ET.fromstring(raw)
    except Exception as exc:  # noqa: BLE001
        yield {
            "source_type": "rss",
            "feed_url": feed_url,
            "url": feed_url,
            "fetched_at": fetched_at,
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
        }
        return

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    items = root.findall(".//item")
    atom_entries = root.findall(".//atom:entry", ns)
    count = 0
    for item in items:
        if count >= max_items:
            break
        count += 1
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        published = (item.findtext("pubDate") or item.findtext("date") or "").strip()
        description = (item.findtext("description") or "").strip()
        yield {
            "source_type": "rss_item",
            "feed_url": feed_url,
            "url": link or feed_url,
            "title": html.unescape(re.sub(r"<[^>]+>", " ", title)),
            "published": published,
            "fetched_at": fetched_at,
            "text": html.unescape(re.sub(r"<[^>]+>", " ", description)),
            "status": "ok",
        }
    for entry in atom_entries:
        if count >= max_items:
            break
        count += 1
        title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
        published = (entry.findtext("atom:published", default="", namespaces=ns) or entry.findtext("atom:updated", default="", namespaces=ns) or "").strip()
        link = ""
        for link_el in entry.findall("atom:link", ns):
            href = link_el.attrib.get("href")
            if href:
                link = href
                break
        summary = (entry.findtext("atom:summary", default="", namespaces=ns) or "").strip()
        yield {
            "source_type": "atom_entry",
            "feed_url": feed_url,
            "url": link or feed_url,
            "title": html.unescape(re.sub(r"<[^>]+>", " ", title)),
            "published": published,
            "fetched_at": fetched_at,
            "text": html.unescape(re.sub(r"<[^>]+>", " ", summary)),
            "status": "ok",
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch public URLs and RSS/Atom feeds into JSONL.")
    parser.add_argument("--url", action="append", default=[], help="Public URL to fetch. Repeatable.")
    parser.add_argument("--url-file", help="Text file with one URL per line.")
    parser.add_argument("--rss", action="append", default=[], help="RSS/Atom feed URL. Repeatable.")
    parser.add_argument("--out", default="sources.jsonl", help="Output JSONL path.")
    parser.add_argument("--max-items", type=int, default=25, help="Maximum items per feed.")
    parser.add_argument("--timeout", type=int, default=20, help="Request timeout in seconds.")
    parser.add_argument("--sleep", type=float, default=0.5, help="Delay between URL fetches.")
    parser.add_argument("--user-agent", default="investment-chain-analyst/1.0 research contact@example.com")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    urls: list[str] = list(args.url)
    if args.url_file:
        for line in Path(args.url_file).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append(line)
    records: list[dict] = []
    for feed in args.rss:
        records.extend(iter_feed_items(feed, args.timeout, args.user_agent, args.max_items))
    for url in urls:
        records.append(extract_page(url, args.timeout, args.user_agent))
        if args.sleep:
            time.sleep(args.sleep)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"wrote {len(records)} records to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
