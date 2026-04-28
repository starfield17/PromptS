#!/usr/bin/env python3
"""Fetch selected SEC Company Facts XBRL tags by CIK and export a CSV.

Example:
python scripts/sec_companyfacts.py --cik 0000320193 --tag Revenues --tag NetIncomeLoss --user-agent "name email@example.com" --out apple_facts.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.request
from pathlib import Path
from typing import Any


def normalize_cik(cik: str) -> str:
    digits = "".join(ch for ch in cik if ch.isdigit())
    return digits.zfill(10)


def fetch_companyfacts(cik: str, user_agent: str, timeout: int) -> dict[str, Any]:
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{normalize_cik(cik)}.json"
    req = urllib.request.Request(url, headers={"User-Agent": user_agent, "Accept-Encoding": "identity"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def extract_rows(data: dict[str, Any], cik: str, tags: list[str]) -> list[dict[str, Any]]:
    rows = []
    facts = data.get("facts", {})
    for taxonomy, taxonomy_data in facts.items():
        for tag, tag_data in taxonomy_data.items():
            if tags and tag not in tags:
                continue
            label = tag_data.get("label", "")
            description = tag_data.get("description", "")
            units = tag_data.get("units", {})
            for unit, values in units.items():
                for value in values:
                    rows.append({
                        "cik": normalize_cik(cik),
                        "entity_name": data.get("entityName", ""),
                        "taxonomy": taxonomy,
                        "tag": tag,
                        "label": label,
                        "unit": unit,
                        "fy": value.get("fy", ""),
                        "fp": value.get("fp", ""),
                        "form": value.get("form", ""),
                        "filed": value.get("filed", ""),
                        "end": value.get("end", ""),
                        "val": value.get("val", ""),
                        "accn": value.get("accn", ""),
                        "description": description,
                    })
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = ["cik", "entity_name", "taxonomy", "tag", "label", "unit", "fy", "fp", "form", "filed", "end", "val", "accn", "description"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch SEC Company Facts for CIKs and selected tags.")
    parser.add_argument("--cik", action="append", required=True, help="CIK. Repeatable.")
    parser.add_argument("--tag", action="append", default=[], help="US-GAAP tag to keep, e.g. Revenues. Repeatable. If omitted, exports all tags.")
    parser.add_argument("--out", default="sec_companyfacts.csv")
    parser.add_argument("--user-agent", required=True, help="SEC requires a descriptive User-Agent with contact info.")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--sleep", type=float, default=0.2)
    args = parser.parse_args()
    all_rows: list[dict[str, Any]] = []
    for cik in args.cik:
        data = fetch_companyfacts(cik, args.user_agent, args.timeout)
        all_rows.extend(extract_rows(data, cik, args.tag))
        if args.sleep:
            time.sleep(args.sleep)
    write_csv(Path(args.out), all_rows)
    print(f"wrote {len(all_rows)} rows to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
