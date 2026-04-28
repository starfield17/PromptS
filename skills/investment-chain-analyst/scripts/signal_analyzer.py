#!/usr/bin/env python3
"""Analyze a CSV/JSONL collection of research snippets, filings, transcripts, or notes.

Outputs CSV tables and a markdown summary: top terms, keyword hits, timeline,
capitalized entities, and source index. Uses only Python standard libraries.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

STOPWORDS = {
    "the", "and", "for", "that", "with", "this", "from", "are", "was", "were", "will", "have", "has",
    "had", "not", "but", "you", "your", "they", "their", "our", "out", "its", "into", "about", "over",
    "more", "than", "also", "can", "may", "per", "use", "using", "used", "company", "market", "said",
    "year", "quarter", "revenue", "growth", "million", "billion", "inc", "corp", "ltd",
}


def load_records(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        records = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(json.loads(line))
        return records
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def normalize_date(value: Any) -> str:
    if not value:
        return "unknown"
    text = str(value).strip()
    patterns = [
        r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})",
        r"(20\d{2})[-/](\d{1,2})",
        r"(20\d{2})",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            if len(m.groups()) >= 2:
                return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}"
            return m.group(1)
    return "unknown"


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9_+.-]{2,}|[\u4e00-\u9fff]{2,}", text)
    out = []
    for word in words:
        w = word.lower()
        if w not in STOPWORDS and len(w) >= 2:
            out.append(w)
    return out


def capitalized_entities(text: str) -> list[str]:
    candidates = re.findall(r"\b(?:[A-Z][A-Za-z0-9&.-]+(?:\s+|/|,\s*)){0,4}[A-Z][A-Za-z0-9&.-]+\b", text)
    cleaned = []
    for c in candidates:
        c = re.sub(r"\s+", " ", c).strip(" ,/")
        if len(c) >= 3 and c.lower() not in STOPWORDS:
            cleaned.append(c)
    return cleaned


def parse_keywords(values: list[str]) -> list[str]:
    kws = []
    for value in values:
        for part in re.split(r"[,;\n]", value):
            part = part.strip()
            if part:
                kws.append(part)
    return kws


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze research-source signals from CSV/JSONL.")
    parser.add_argument("--input", required=True, help="Input CSV or JSONL file.")
    parser.add_argument("--out-dir", default="analysis_out", help="Output directory.")
    parser.add_argument("--text-field", default="text", help="Text field name. Falls back to title+excerpt if absent.")
    parser.add_argument("--date-field", default="published", help="Date field name.")
    parser.add_argument("--group-field", default="", help="Optional grouping field, e.g. source or company.")
    parser.add_argument("--keyword", action="append", default=[], help="Keyword or comma-separated list. Repeatable.")
    parser.add_argument("--top-n", type=int, default=40)
    args = parser.parse_args()

    records = load_records(Path(args.input))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    keywords = parse_keywords(args.keyword)

    term_counts: Counter[str] = Counter()
    entity_counts: Counter[str] = Counter()
    timeline: Counter[tuple[str, str]] = Counter()
    keyword_hits: list[dict[str, Any]] = []
    index_rows: list[dict[str, Any]] = []

    for idx, rec in enumerate(records, 1):
        text = str(rec.get(args.text_field) or " ".join(str(rec.get(k, "")) for k in ["title", "excerpt", "summary", "description"]))
        title = str(rec.get("title") or rec.get("headline") or "")
        url = str(rec.get("url") or rec.get("source") or "")
        date_bucket = normalize_date(rec.get(args.date_field) or rec.get("date") or rec.get("fetched_at"))
        group = str(rec.get(args.group_field, "all")) if args.group_field else "all"
        words = tokenize(title + "\n" + text)
        term_counts.update(words)
        entity_counts.update(capitalized_entities(title + "\n" + text))
        timeline[(date_bucket, group)] += 1
        for kw in keywords:
            count = len(re.findall(re.escape(kw), title + "\n" + text, flags=re.I))
            if count:
                keyword_hits.append({"record_id": idx, "keyword": kw, "count": count, "date_bucket": date_bucket, "title": title, "url": url})
        index_rows.append({"record_id": idx, "date_bucket": date_bucket, "title": title, "url": url, "chars": len(text)})

    top_terms = [{"term": term, "count": count} for term, count in term_counts.most_common(args.top_n)]
    top_entities = [{"entity": ent, "count": count} for ent, count in entity_counts.most_common(args.top_n)]
    timeline_rows = [{"date_bucket": d, "group": g, "records": c} for (d, g), c in sorted(timeline.items())]

    write_csv(out_dir / "top_terms.csv", top_terms, ["term", "count"])
    write_csv(out_dir / "top_entities.csv", top_entities, ["entity", "count"])
    write_csv(out_dir / "timeline.csv", timeline_rows, ["date_bucket", "group", "records"])
    write_csv(out_dir / "keyword_hits.csv", keyword_hits, ["record_id", "keyword", "count", "date_bucket", "title", "url"])
    write_csv(out_dir / "records_index.csv", index_rows, ["record_id", "date_bucket", "title", "url", "chars"])

    summary = [
        "# Signal Analysis Summary",
        "",
        f"Records analyzed: {len(records)}",
        "",
        "## Top terms",
        "",
    ]
    summary.extend(f"- {row['term']}: {row['count']}" for row in top_terms[:20])
    summary.extend(["", "## Top entities", ""])
    summary.extend(f"- {row['entity']}: {row['count']}" for row in top_entities[:20])
    if keywords:
        summary.extend(["", "## Keyword hit counts", ""])
        kw_counts = Counter(hit["keyword"] for hit in keyword_hits)
        summary.extend(f"- {kw}: {kw_counts.get(kw, 0)}" for kw in keywords)
    summary.extend(["", "## Generated files", "", "- top_terms.csv", "- top_entities.csv", "- timeline.csv", "- keyword_hits.csv", "- records_index.csv"])
    (out_dir / "summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print(f"analyzed {len(records)} records; wrote outputs to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
