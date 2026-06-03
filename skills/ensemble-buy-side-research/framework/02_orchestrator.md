# Orchestrator

The orchestrator is the main control flow for the Skill.

## Inputs

```yaml
direction: string
trigger: string | null
company: string | null
region: list[string] | null
time_horizon: string | null
source_pack: list[Source] | null
user_view: string | null
```

## Processing Flow

```text
1. Normalize input
2. Classify trigger
3. Define problem solved
4. Build preliminary value-chain map
5. Identify players by layer
6. Score profit pools
7. Apply Buffett quality lens
8. Score commoditization risk
9. Extract or infer market consensus
10. Generate variant-view candidates
11. Convert thesis into variables
12. Build watchlist
13. Define falsification
14. Assign initial judgment
15. Generate next research steps
```

## Step 1: Normalize Input

Turn messy user input into a clean research object.

```text
Raw input:
"AI inference and Broadcom maybe benefiting from hyperscaler custom chips"

Normalized:
Direction: AI inference accelerator ecosystem
Company focus: Broadcom
Trigger: hyperscaler custom silicon adoption
Region: Global / US
Time horizon: 6–24 months
```

## Step 2: Classify Trigger

Use one or more labels:

```text
Demand
Supply
Policy
Technology
Financial
Narrative
Price Action
Competitive
Customer Adoption
Capacity
```

## Step 3: Define Problem

Use the pattern:

```text
This direction exists because [customer / system] needs to reduce [cost / latency / risk / scarcity] in [use case].
```

## Step 4: Value-chain Draft

Create a first-pass layer map.

Required:

```text
Layer
Role
Representative players
Potential economics
Uncertainty
```

## Step 5: Player Mapping

Separate:

```text
core beneficiaries
derivative beneficiaries
narrative proxies
potential losers
```

## Step 6: Profit Pool Score

Use the scoring rubric in `04_scoring_rubrics.md`.

## Step 7: Buffett Quality Lens

Use `09_buffett_quality_lens.md` to test whether the best-looking layer or company is actually a business worth owning.

Required output:

```text
Circle of competence
Moat source and moat trend
Owner economics
Pricing power
Capital intensity
Five-year market closure test
Downside / ruin risk
Implication for judgment
```

If the idea is outside the circle of competence, has no durable moat, or contains ruin risk, downgrade before continuing.

## Step 8: Commoditization Score

Identify layers likely to face margin erosion.

## Step 9: Consensus

If no fresh market data are available, write:

```text
Assumed consensus, pending source validation:
```

Do not pretend to know current positioning without evidence.

## Step 10: Variant View

Generate 1–3 variant-view candidates, then select the strongest one.

A candidate must include:

```text
consensus it disagrees with
value-chain layer
variable
time horizon
falsification
```

## Step 11: Variables

Build a variable map:

```text
Thesis driver → Observable variable → Source → Frequency → Threshold
```

## Step 12: Watchlist

Create a durable table that can be updated later by scripts or manually.

## Step 13: Falsification

List 3–7 conditions.

Good falsification is specific:

```text
If hyperscaler capex grows but custom silicon suppliers do not show backlog or margin improvement within 2–3 reporting cycles, the thesis is weakened.
```

Weak falsification is vague:

```text
If the industry does not grow, the thesis is wrong.
```

## Step 14: Initial Judgment

Assign one of:

```text
A. Discard
B. Watch
C. Deep Dive
D. Potential Investment Thesis
```

Include 2–4 sentences explaining why.

## Step 15: Next Steps

Make the next steps operational.

Examples:

```text
Read the latest 10-K/10-Q for segment disclosures.
Build a layer-by-layer peer margin table.
Track capex guidance from the top five customers.
Compare valuation multiples against margin durability.
Check whether the bottleneck is shifting from hardware to power/cooling.
```
