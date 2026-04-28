# Subagent Methodology

Use subagents for bounded qualitative judgment that scripts should not encode. Scripts produce artifacts; subagents critique, extend, and stress-test those artifacts. The main agent reconciles all outputs and owns the final memo.

## When to Delegate

Delegate only when the subtask is independent and concrete:

```text
Entity / layer sanity check
Value-chain expansion
Profit-pool critique
Consensus vs variant-view analysis
Watchlist and falsification review
Memo red-team review
```

Do not delegate vague requests such as “analyze this industry.” Give the subagent specific artifacts and a narrow output contract.

## Standard Subagent Output

Ask subagents to return:

```text
Findings
Evidence Used
Unverified Claims
Suggested Changes
Confidence
```

Require `Fact`, `Interpretation`, `Hypothesis`, or `Unknown` labels for important claims. A subagent should not make the final A/B/C/D judgment unless explicitly asked for a second opinion; even then, treat it as input, not authority.

## Recommended Passes

### 1. Entity and Layer Sanity Check

Use after `extract-entities` and `build-value-chain`.

Prompt pattern:

```text
Given source_pack.json, entities.json, and value_chain.json, identify missing companies, products, metrics, events, or value-chain layers. Return only evidence-labeled additions or corrections. Do not write a memo.
```

Expected output:

```text
Findings:
Evidence Used:
Unverified Claims:
Suggested Changes:
Confidence:
```

### 2. Profit-pool Critique

Use after `score-profit-pool`.

Prompt pattern:

```text
Given value_chain.json, scores.json, and financials.parquet summary, critique which layers may be over-scored or under-scored. Focus on margin quality, bargaining power, capacity, switching cost, customer concentration, capex burden, and commoditization risk.
```

Expected output should separate:

```text
Likely overstated economics
Likely understated economics
Evidence gaps
Suggested score adjustments
```

### 3. Consensus vs Variant-view Analysis

Use after `detect-consensus`.

Prompt pattern:

```text
Given news_items.json, consensus.json, and source_pack.json, separate repeated market narrative from sourced facts. Propose up to three variant views. Each variant view must map to a value-chain layer, measurable variable, time horizon, and falsification condition.
```

Reject subagent output that does not include measurable variables or falsification.

### 4. Watchlist Review

Use after `generate-watchlist`.

Prompt pattern:

```text
Given thesis.json if available, value_chain.json, scores.json, and watchlist.json, identify missing variables, weak sources, vague thresholds, or non-falsifiable watch items. Return concrete replacements.
```

Good suggestions name:

```text
Variable
Why it matters
Source
Frequency
Bullish signal
Bearish signal
```

### 5. Memo Red-team

Use before final delivery.

Prompt pattern:

```text
Given research_memo.md and the source artifacts used to produce it, find unsupported claims, generic sell-side language, missing consensus, weak variant views, missing losers, weak falsification, and next steps that are not operational.
```

The main agent should apply only changes that can be tied back to source artifacts or clearly marked assumptions.

## Reconciliation Rules

The main agent must:

```text
Compare subagent findings against source artifacts.
Mark unresolved claims as Source needed or Unknown.
Prefer primary filings, regulator data, exchange announcements, and company IR over news or social sources.
Keep contradictory evidence visible.
Avoid pasting subagent prose directly into the memo without checking evidence and tone.
```

If subagents conflict, preserve the disagreement in `Contradictory evidence` or `Evidence gaps` rather than forcing false precision.
