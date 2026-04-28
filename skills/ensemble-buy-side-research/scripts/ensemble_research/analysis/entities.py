from __future__ import annotations

import re
from collections import Counter
from typing import Any

from ..config import confidence_from_count
from ..io import collect_text, normalize_records, read_json
from ..models import EntityPack


METRIC_TERMS = {
    "capex",
    "gross margin",
    "operating margin",
    "revenue",
    "backlog",
    "orders",
    "inventory",
    "utilization",
    "capacity",
    "pricing",
    "ASP",
    "shipment",
    "ARPU",
    "retention",
    "take rate",
    "毛利率",
    "收入",
    "订单",
    "库存",
    "产能",
    "出货",
    "价格",
}

PRODUCT_TERMS = {
    "GPU",
    "ASIC",
    "HBM",
    "CoWoS",
    "chip",
    "accelerator",
    "robot",
    "actuator",
    "sensor",
    "battery",
    "cooling",
    "software",
    "SaaS",
    "API",
    "芯片",
    "机器人",
    "传感器",
    "电池",
    "软件",
}

EVENT_TERMS = {
    "capacity expansion",
    "price cut",
    "export control",
    "new product",
    "earnings",
    "guidance",
    "政策",
    "扩产",
    "降价",
    "新品",
    "财报",
}

LAYER_TERMS = {
    "raw materials",
    "equipment",
    "core components",
    "advanced packaging",
    "memory",
    "networking",
    "software",
    "systems integration",
    "distribution",
    "services",
    "materials",
    "power and cooling",
    "cloud service",
}


def _company_candidates(text: str) -> list[str]:
    # English public-company and organization-like spans, plus simple Chinese company suffixes.
    pattern = r"\b(?:[A-Z][A-Za-z0-9&.\-]+(?:\s+[A-Z][A-Za-z0-9&.\-]+){0,3})\b"
    blocked = {"The", "This", "Market", "Source", "Unknown", "Fact", "China", "Global", "US", "CN"}
    candidates = [match.group(0).strip() for match in re.finditer(pattern, text)]
    cn = re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,16}(?:股份|集团|科技|电子|能源|半导体|机器人|公司)", text)
    return [c for c in candidates + cn if c not in blocked and len(c) > 1]


def _terms_present(text: str, terms: set[str]) -> list[str]:
    lower = text.lower()
    found: list[str] = []
    for term in terms:
        if term.lower() in lower:
            found.append(term)
    return sorted(set(found))


def extract_entities_from_text(text: str, source_ids: list[str] | None = None) -> EntityPack:
    company_counts = Counter(_company_candidates(text))
    companies = [name for name, count in company_counts.most_common(30) if count >= 1]
    products = _terms_present(text, PRODUCT_TERMS)
    metrics = _terms_present(text, METRIC_TERMS)
    events = _terms_present(text, EVENT_TERMS)
    layers = _terms_present(text, LAYER_TERMS)
    confidence = confidence_from_count(len(companies) + len(products) + len(metrics) + len(events))
    uncertain_terms = []
    if not companies:
        uncertain_terms.append("No company candidates extracted")
    if not layers:
        uncertain_terms.append("No explicit value-chain layers extracted")
    return EntityPack(
        companies=companies,
        products=products,
        metrics=metrics,
        events=events,
        possible_layers=layers,
        uncertain_terms=uncertain_terms,
        source_ids=source_ids or [],
        confidence=confidence,
    )


def extract_entities_from_file(path: str) -> EntityPack:
    data = read_json(path)
    records = normalize_records(data)
    text, source_ids = collect_text(records)
    return extract_entities_from_text(text, source_ids)


def extract_entities_from_records(records: list[dict[str, Any]]) -> EntityPack:
    text, source_ids = collect_text(records)
    return extract_entities_from_text(text, source_ids)
