from __future__ import annotations

from typing import Any

from jinja2 import Template

from ..models import Consensus, ResearchMemo, ScoreCard, ValueChain, Watchlist


MEMO_TEMPLATE = Template(
    """# {{ memo.direction }}

## Trigger

| Field | Answer |
|---|---|
| Trigger | {{ memo.trigger.get("description", "Source needed") }} |
| Trigger Type | {{ memo.trigger.get("type", "Unknown") }} |
| Why Now | {{ memo.trigger.get("why_now", "Source needed") }} |
| Real Variable Changed? | {{ memo.trigger.get("real_variable_changed", "Unclear") }} |

## Problem Solved

{{ memo.problem_solved }}

## Facts

| Fact | Source | Confidence |
|---|---|---|
{% for fact in memo.facts -%}
| {{ fact.get("fact", "") }} | {{ fact.get("source_id", "Source needed") }} | {{ fact.get("confidence", "unknown") }} |
{% else -%}
| Source needed | Source needed | unknown |
{% endfor %}

## Value Chain Map

| Layer | Problem Solved by Layer | Representative Players | Bottleneck Level | Profit Pool Quality | Competition Intensity | Commoditization Risk | Investment Judgment |
|---|---|---|---|---|---|---|---|
{% if memo.value_chain -%}
{% for layer in memo.value_chain.layers -%}
| {{ layer.name }} | {{ layer.problem_solved }} | {{ (layer.players.global_ + layer.players.regional) | join(", ") }} | {{ layer.bottleneck_level }} | {{ layer.profit_pool_quality }} | {{ layer.competition_intensity }} | {{ layer.commoditization_risk }} | {{ layer.judgment }} |
{% endfor -%}
{% endif %}

## Profit Pool

{{ memo.profit_pool.get("summary", "Source needed") }}

## Buffett Quality Lens

| Field | Assessment |
|---|---|
| Circle of Competence | {{ memo.buffett_quality_lens.get("circle_of_competence", "Unknown") }} |
| Business Quality | {{ memo.buffett_quality_lens.get("business_quality", "Source needed") }} |
| Moat Source | {{ memo.buffett_quality_lens.get("moat_source", "Source needed") }} |
| Moat Trend | {{ memo.buffett_quality_lens.get("moat_trend", "Unknown") }} |
| Pricing Power | {{ memo.buffett_quality_lens.get("pricing_power", "Source needed") }} |
| Capital Intensity | {{ memo.buffett_quality_lens.get("capital_intensity", "Source needed") }} |
| Five-Year Market Closure Test | {{ memo.buffett_quality_lens.get("five_year_market_closure_test", "Unknown") }} |
| Downside / Ruin Risk | {{ memo.buffett_quality_lens.get("downside_or_ruin_risk", "Source needed") }} |
| Implication | {{ memo.buffett_quality_lens.get("implication", "Neutral pending evidence") }} |

## Commoditization Risk

{% for item in memo.commoditization_risk -%}
- **{{ item.get("layer", "Unknown") }}**: {{ item.get("reason", "Source needed") }}
{% else -%}
- Source needed.
{% endfor %}

## Market Consensus

{{ memo.market_consensus }}

## Variant View

{{ memo.variant_view }}

## Key Variables

| Variable | Why It Matters | Source | Frequency | Bullish Signal | Bearish Signal | Current Reading |
|---|---|---|---|---|---|---|
{% for item in memo.key_variables -%}
| {{ item.variable }} | {{ item.why_it_matters }} | {{ item.source }} | {{ item.frequency }} | {{ item.bullish_signal }} | {{ item.bearish_signal }} | {{ item.current_reading or "Source needed" }} |
{% endfor %}

## Initial Judgment

{{ memo.initial_judgment }}

## Falsification Conditions

{% for item in memo.falsification_conditions -%}
{{ loop.index }}. {{ item }}
{% else -%}
1. Source needed.
{% endfor %}

## Next Research Steps

{% for item in memo.next_research_steps -%}
{{ loop.index }}. {{ item }}
{% else -%}
1. Validate current source pack.
2. Compare layer-level economics.
3. Track the watchlist variables.
{% endfor %}
"""
)


def build_memo(
    direction: str,
    value_chain: ValueChain | None,
    consensus: Consensus | None,
    watchlist: Watchlist | None,
    scorecard: ScoreCard | None,
    trigger: dict[str, Any] | None = None,
) -> ResearchMemo:
    layers = value_chain.layers if value_chain else []
    best_layer = None
    if scorecard and scorecard.layer_scores:
        best_layer = max(scorecard.layer_scores, key=lambda item: item.investability_score)
    highest = best_layer.layer if best_layer else (layers[0].name if layers else "Source needed")
    facts = []
    if value_chain and value_chain.source_ids:
        facts.append({"fact": "Source pack was processed into a preliminary value-chain map.", "source_id": ", ".join(value_chain.source_ids[:5]), "confidence": "medium"})
    market_consensus = consensus.consensus if consensus else "Assumed consensus, pending source validation"
    variant = (
        f"The market may be right about the direction but wrong about durable profit capture. The current strongest layer candidate is {highest}; validate with margin, capacity, and customer evidence."
    )
    falsification = [
        "Demand indicators improve but layer-level margins compress.",
        "Capacity normalizes faster than demand and pricing power disappears.",
        "Customers self-build or switch to substitutes, reducing supplier bargaining power.",
    ]
    return ResearchMemo(
        direction=direction,
        trigger=trigger or {"description": "Source needed", "type": "Unknown"},
        problem_solved=f"The direction exists because customers need to reduce cost, scarcity, latency, risk, or underpenetration in {direction}. Validate the exact economic problem with primary sources.",
        facts=facts,
        value_chain=value_chain,
        profit_pool={"summary": f"Preliminary highest-quality profit-pool candidate: {highest}. Validate with gross margin, pricing power, switching costs, and capex burden."},
        buffett_quality_lens={
            "circle_of_competence": "Unknown - validate whether the decisive variables are understandable.",
            "business_quality": f"Preliminary candidate layer: {highest}; validate return on incremental capital and cash conversion.",
            "moat_source": "Source needed - test for brand/share-of-mind, low cost, switching cost, scale, IP, license, or process know-how.",
            "moat_trend": "Unknown",
            "pricing_power": "Source needed - compare price, gross margin, discounting, and customer behavior.",
            "capital_intensity": "Source needed - compare growth capex with incremental returns.",
            "five_year_market_closure_test": "Unknown - do not pass until business quality, balance sheet, and valuation are underwritten.",
            "downside_or_ruin_risk": "Source needed - check leverage, liquidity, concentration, governance, and tail risks.",
            "implication": "Neutral pending evidence; downgrade if outside competence, no durable moat, or ruin risk appears.",
        },
        commoditization_risk=[
            {"layer": layer.name, "reason": f"Commoditization risk is currently marked {layer.commoditization_risk}; validate with supplier count, ASP pressure, and switching cost."}
            for layer in layers
            if layer.commoditization_risk in {"medium", "high"}
        ],
        market_consensus=market_consensus,
        variant_view=variant,
        key_variables=watchlist.items if watchlist else [],
        initial_judgment=scorecard.initial_judgment if scorecard else "B. Watch",
        falsification_conditions=falsification,
        next_research_steps=[
            "Read primary filings and earnings-call commentary for representative companies.",
            "Build a layer-by-layer peer margin and valuation table.",
            "Validate whether the bottleneck layer has pricing power or only temporary scarcity.",
            "Update the watchlist after the next reporting cycle.",
        ],
    )


def render_memo(memo: ResearchMemo) -> str:
    return MEMO_TEMPLATE.render(memo=memo)
