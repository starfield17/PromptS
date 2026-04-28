from __future__ import annotations


TRIGGER_KEYWORDS: dict[str, list[str]] = {
    "Demand": ["demand", "order", "backlog", "shipment", "adoption", "capex", "revenue", "customer", "需求", "订单", "出货", "资本开支"],
    "Supply": ["capacity", "shortage", "supply", "inventory", "utilization", "lead time", "产能", "供应", "库存", "稼动率"],
    "Policy": ["regulation", "policy", "tariff", "subsidy", "approval", "ban", "export control", "政策", "监管", "补贴", "出口管制"],
    "Technology": ["launch", "benchmark", "node", "yield", "model", "performance", "latency", "技术", "发布", "良率", "性能"],
    "Financial": ["margin", "guidance", "earnings", "valuation", "profit", "buyback", "毛利率", "指引", "利润", "估值"],
    "Narrative": ["theme", "concept", "story", "hype", "AI+", "概念", "主题", "叙事"],
    "Price Action": ["shares", "stock", "rally", "selloff", "跌", "涨停", "股价", "上涨", "下跌"],
    "Competitive": ["competitor", "market share", "self-build", "substitute", "price war", "竞争", "替代", "价格战", "自研"],
}


def classify_trigger(text: str | None) -> str:
    if not text:
        return "Unknown"
    lower = text.lower()
    scores: dict[str, int] = {}
    for label, words in TRIGGER_KEYWORDS.items():
        scores[label] = sum(1 for word in words if word.lower() in lower)
    best, score = max(scores.items(), key=lambda item: item[1])
    return best if score else "Unknown"
