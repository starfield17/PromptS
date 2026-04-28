#!/usr/bin/env python3
"""Generate an editable industry-chain map template for a market theme."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

DEFAULT_LAYERS = [
    "equipment/materials",
    "manufacturing/packaging",
    "chips/accelerators",
    "memory/storage",
    "servers/network/cooling/power",
    "cloud/platform",
    "model/api",
    "application/agent/saas",
    "end customers",
]
FIELDS = [
    "theme", "layer", "problem_solved", "global_players", "local_players", "profit_pool_or_bargaining_power",
    "competition", "key_variables", "validation_sources", "investment_judgment", "falsification_conditions",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Create an industry-chain CSV and optional markdown template.")
    parser.add_argument("--theme", required=True)
    parser.add_argument("--out", default="chain_map.csv")
    parser.add_argument("--markdown", default="", help="Optional markdown output path.")
    parser.add_argument("--layers", default="", help="Comma-separated custom layers.")
    args = parser.parse_args()
    layers = [x.strip() for x in args.layers.split(",") if x.strip()] or DEFAULT_LAYERS
    rows = []
    for layer in layers:
        rows.append({
            "theme": args.theme,
            "layer": layer,
            "problem_solved": "",
            "global_players": "",
            "local_players": "",
            "profit_pool_or_bargaining_power": "",
            "competition": "",
            "key_variables": "",
            "validation_sources": "",
            "investment_judgment": "discard/watch/deep-dive/investment hypothesis",
            "falsification_conditions": "",
        })
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    if args.markdown:
        lines = [f"# {args.theme} Industry Chain Map", "", "| " + " | ".join(FIELDS) + " |", "|" + "|".join(["---"] * len(FIELDS)) + "|"]
        for row in rows:
            lines.append("| " + " | ".join(str(row.get(f, "")) for f in FIELDS) + " |")
        Path(args.markdown).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} rows to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
