---
name: investment-chain-analyst
description: systematic buy-side industry-chain and thematic investment research. use when the user asks to evaluate a market theme, sector, industry chain, emerging technology, stock basket, narrative, beneficiaries, key variables, data to monitor, or whether to discard/watch/deep-dive/form an investment hypothesis. especially useful for ai infrastructure, semiconductors, robotics, energy, saas, shipping, materials, and other multi-layer supply-demand chains.
---

# Investment Chain Analyst

## Overview

Use this skill to convert a broad market theme into a disciplined buy-side research memo: define the trigger, collect facts, map the value chain, identify winners and losers, find variant perception, specify key variables, and decide whether to discard, watch, deep-dive, or form an investment hypothesis.

The source framework behind this skill is an internalized and generalized version of a sector-chain research answer: it is not a copy of the original text; it is an English reusable workflow for future analysis.

## Default Workflow

1. **Frame the direction and trigger**
   - State the theme in one sentence: e.g., "AI inference chips", "advanced packaging", "humanoid robots", "nuclear power", "export-oriented SaaS".
   - Explain why it matters today: price move, order change, policy/news catalyst, filing, customer adoption, cost decline, capacity bottleneck, or narrative shift.
   - Define the time horizon: trade, 3-12 month thesis, or multi-year structural thesis.

2. **Build the fact pack**
   - Separate facts from interpretation.
   - Use dated evidence: filings, earnings calls, orders/backlogs, shipment/capacity data, pricing, capex, utilization, margins, product benchmarks, customer adoption, and policy.
   - For web or uploaded data, cite every non-obvious claim and keep source URLs in tables when available.
   - If raw sources need extraction, run `scripts/fetch_sources.py` on URLs/RSS feeds.

3. **Summarize the market narrative**
   - Explain how the market currently tells the story.
   - Identify what is likely already priced in: consensus beneficiaries, consensus bottlenecks, and consensus risks.

4. **State the variant perception**
   - Ask: "What could I see earlier or differently than the market?"
   - Favor measurable variants: faster adoption, slower price decline, underappreciated margin durability, bottleneck moving to a different layer, customer concentration easing, or China/localization creating a separate profit pool.

5. **Map the industry chain**
   - Build the chain from supply bottleneck to demand monetization.
   - Use layers such as: equipment/materials, manufacturing/packaging, chips/accelerators, memory/storage, servers/network/cooling/power, cloud/platform, model/API, application/agent/SaaS, and end customers.
   - For each layer, capture: problem solved, core players, bargaining power/margins, competition, key variables, validation sources, and investment judgment.
   - Generate a starting CSV with `scripts/chain_map_template.py` when useful.

6. **Identify beneficiaries, losers, and concept-only players**
   - Classify each company or sub-sector as: direct beneficiary, indirect beneficiary, bottleneck owner, capacity supplier, cost absorber, substitution risk, cyclical laggard, or concept-only exposure.
   - Avoid assuming every participant benefits equally. Profit pools usually concentrate where capacity is scarce, switching costs are high, IP is defensible, or customers are locked in.

7. **Define key variables**
   - Track 5-10 variables that can change the thesis, such as capex, shipments, lead times, prices, gross margins, utilization, token/API pricing, inference demand, customer ROI, churn/retention, energy constraints, export controls, inventory, and working capital.
   - For AI infrastructure themes, default variables include hyperscaler capex, GPU/HBM/advanced packaging supply, inference-token growth, token-cost decline, enterprise AI spend conversion, data-center power/cooling bottlenecks, export controls, domestic substitution, open-source/API pricing pressure, depreciation cycles, and cloud ROIC.

8. **Plan validation**
   - Specify the next data to check: news, filings, earnings calls, orders/backlogs, channel checks, pricing, import/export data, capacity announcements, product benchmarks, customer metrics, or web traffic.
   - Use `scripts/signal_analyzer.py` to summarize large collections of article snippets, filings, transcripts, or notes.
   - Use `scripts/sec_companyfacts.py` for US company XBRL facts when the user provides CIKs and a User-Agent.

9. **Make the initial judgment**
   - Choose one of four labels:
     - `discard`: no durable profit pool, evidence weak, or thesis already fully reflected.
     - `watch`: plausible but missing key confirming evidence.
     - `deep-dive`: evidence suggests a real edge but more company/layer work is required.
     - `investment hypothesis`: a testable thesis exists with named beneficiaries, variables, catalysts, and disconfirming evidence.

10. **Write falsification conditions**
    - Always answer: "What would prove me wrong?"
    - Include both data-based and narrative-based disconfirmers.

## Output Structure

Use this structure unless the user asks for a different format:

```markdown
# [Theme] Investment Chain Analysis

## 1. Direction and catalyst
- Direction:
- Why now:
- Horizon:

## 2. Fact pack
| Date | Fact | Source | Implication | Confidence |
|---|---|---|---|---|

## 3. Market narrative
[How consensus currently explains the theme.]

## 4. Variant perception
[What may be earlier, different, or mispriced.]

## 5. Industry-chain map
| Layer | Problem solved | Key players | Profit pool / bargaining power | Competition | Key variables | Investment judgment |
|---|---|---|---|---|---|---|

## 6. Key variables to monitor
| Variable | Why it matters | Data source | Direction that confirms | Direction that weakens |
|---|---|---|---|---|

## 7. Initial judgment
Label: discard / watch / deep-dive / investment hypothesis

## 8. Falsification conditions
- [Condition 1]
- [Condition 2]
```

## Script Usage

- `scripts/fetch_sources.py`: collect plain-text snippets from URLs and RSS/Atom feeds into JSONL. Use it for source gathering only; do not bypass paywalls, login walls, robots.txt restrictions, or website terms.
- `scripts/signal_analyzer.py`: analyze JSONL/CSV source collections for top terms, keyword hits, timelines, repeated entities, and a markdown summary.
- `scripts/chain_map_template.py`: create an editable industry-chain CSV/Markdown template for a theme.
- `scripts/sec_companyfacts.py`: fetch selected SEC Company Facts XBRL tags by CIK and export CSV for US-listed companies.

All scripts use Python standard libraries only. Prefer running scripts on user-provided files or public URLs. When the runtime has no internet access, ask the user to upload source files or paste URLs/data gathered elsewhere.

## Quality Bar

- Distinguish `fact`, `estimate`, `market narrative`, and `opinion`.
- Do not infer investability from story strength alone; require a profit-pool mechanism and measurable validation path.
- State dates for fast-moving metrics.
- Do not present financial advice as certainty. Frame outputs as research analysis and hypothesis generation.
- For current prices, news, legal/regulatory status, or time-sensitive facts, use available browsing/data tools and cite sources.
- If evidence is thin, say so and downgrade the judgment.

## Additional References

- Use `references/framework.md` for the full framework checklist and investment judgment rubric.
- Use `references/data_sources.md` for suggested data sources and metric types by chain layer.
- Use `references/output_templates.md` for reusable memo, table, and watchlist templates.
