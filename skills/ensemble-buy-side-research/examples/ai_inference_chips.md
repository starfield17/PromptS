# Example: AI Inference Chips

> Illustrative example only. Current market facts, valuations, guidance, and company data must be verified before use.

## Direction

AI inference chips are hardware and software systems designed to reduce the cost, latency, and energy intensity of running trained AI models at scale.

## Trigger

| Field | Answer |
|---|---|
| Trigger | Hyperscalers increase focus on inference cost and custom silicon. |
| Trigger Type | Demand / Technology / Customer Adoption |
| Why Now | Training creates model capability, but inference determines recurring unit economics. |
| First-order Impact | GPU vendors, custom ASIC suppliers, memory, advanced packaging, networking. |
| Second-order Impact | Power, cooling, data-center infrastructure, model-optimization software. |
| Real Variable Changed? | Source needed: cloud capex, inference volume, API pricing, chip orders. |

## Problem Solved

The direction exists because running AI models at scale is expensive, power-constrained, and latency-sensitive. Buyers pay for lower cost per token, higher throughput, and better control over infrastructure economics.

## Facts

| Fact | Source | Confidence |
|---|---|---|
| Large-scale inference requires compute, memory bandwidth, networking, and software optimization. | Technical architecture / source needed | Medium |
| Hyperscalers have strategic incentives to reduce dependence on external accelerators. | Source needed | Medium |
| Inference economics depend on utilization, model architecture, power, and software stack. | Source needed | Medium |

## Value Chain Map

| Layer | Problem Solved by Layer | Representative Players | Bottleneck Level | Profit Pool Quality | Competition Intensity | Commoditization Risk | Investment Judgment |
|---|---|---|---|---|---|---|---|
| Accelerator chips | Compute throughput and latency | GPU vendors, custom ASIC suppliers | High | High | Medium | Medium | Attractive but crowded; verify pricing durability. |
| HBM / memory | Feeds data to compute; reduces memory bottleneck | Memory suppliers | High | High | Medium | Medium | Strong when capacity is scarce; watch supply expansion. |
| Advanced packaging | Connects compute and memory efficiently | Foundry / OSAT ecosystem | High | High | Medium | Low–Medium | Bottleneck layer; good second-order candidate. |
| Networking | Moves data across clusters | Switch, NIC, optical suppliers | Medium–High | Medium–High | Medium | Medium | Benefits from scale-out architecture. |
| Power and cooling | Enables dense deployment | Electrical, cooling, thermal vendors | Medium | Medium | Medium | Medium | Underappreciated second-order layer. |
| Software optimization | Improves utilization and cost per token | Compiler, runtime, serving stack | Medium | Potentially High | High | High | Attractive if lock-in exists; otherwise open-source pressure. |
| Cloud service layer | Packages inference for customers | Hyperscalers, AI platforms | Medium | Mixed | High | Medium | Depends on pricing power and utilization. |

## Profit Pool

### Highest-quality Profit Pool

```text
Layer: accelerator ecosystem bottlenecks, HBM, advanced packaging.
Why it exists: scarcity, technical difficulty, and high customer urgency.
Who captures it: suppliers with constrained capacity or differentiated performance.
How long it may last: depends on capacity expansion and customer self-build.
What could destroy it: oversupply, open-source efficiency gains, customer bargaining power.
```

### Overhyped Profit Pool

```text
Layer: undifferentiated AI application wrappers.
Why popular: easy narrative linkage to AI adoption.
Why economics may disappoint: low switching cost, model/API competition, weak distribution.
```

### Hidden / Second-order Profit Pool

```text
Layer: power, cooling, and data-center infrastructure.
Why underappreciated: less glamorous than chips but increasingly tied to physical deployment constraints.
Evidence needed: capex mix, data-center power constraints, order growth.
```

## Market Consensus

Assumed consensus, pending source validation:

```text
The market believes AI compute demand remains strong, leading GPU and infrastructure suppliers benefit, and custom silicon may diversify the profit pool.
```

## Variant View

```text
The market may be right about inference growth but wrong about where durable economics settle. Hardware scarcity may be a cyclical bottleneck, while long-term value may migrate toward layers that control utilization, packaging capacity, power density, and customer workload integration.
```

## Key Variables

| Variable | Why It Matters | Source | Frequency | Bullish Signal | Bearish Signal | Current Reading |
|---|---|---|---|---|---|---|
| Hyperscaler capex | Measures infrastructure demand | Company filings / calls | Quarterly | Upward revisions | Cuts or delays | Source needed |
| Inference API pricing | Indicates margin pressure | Public pricing pages / industry checks | Monthly | Stable price at rising volume | Rapid price cuts | Source needed |
| HBM capacity and pricing | Tests scarcity | Supplier calls / industry data | Quarterly | Tight supply, firm pricing | Capacity glut | Source needed |
| Advanced packaging capacity | Tests bottleneck durability | Foundry / OSAT disclosures | Quarterly | Persistent constraints | Rapid capacity normalization | Source needed |
| Power availability / cooling demand | Tests physical bottleneck | Utility / data-center data | Quarterly | More power-constrained projects | Weak deployment | Source needed |

## Initial Judgment

```text
C. Deep Dive
```

The problem is real and the value chain contains several high-quality bottleneck layers. However, market consensus may already be crowded in the obvious chip names, so the next work should focus on second-order layers, margin durability, and timing.

## Falsification Conditions

1. Inference volume grows but supplier margins compress faster than expected.
2. Hyperscaler capex guidance weakens or shifts away from AI infrastructure.
3. HBM and packaging capacity normalize faster than demand.
4. Open-source or model-efficiency improvements reduce compute intensity materially.
5. Customers gain bargaining power and force pricing down across the stack.

## Next Research Steps

1. Build a peer table by layer: chips, memory, packaging, networking, power/cooling, cloud.
2. Compare gross margin and capex intensity across layers.
3. Track hyperscaler capex guidance and AI infrastructure commentary.
4. Identify which suppliers have backlog visibility.
5. Separate direct beneficiaries from narrative proxies.
