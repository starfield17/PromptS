# Data Sources and Metrics

Use this guide to choose validation data by industry-chain layer. Prefer primary sources and time-stamped data.

## Universal Source Types

- Company filings: annual reports, 10-K, 10-Q, 8-K, prospectus, shareholder letters.
- Earnings calls and investor presentations.
- Order books, backlog, bookings, design wins, customer announcements.
- Pricing: product price sheets, API pricing, cloud pricing, distributor quotes, channel checks.
- Shipment and capacity: units shipped, wafer starts, HBM capacity, CoWoS capacity, server deliveries, utilization.
- Capex and depreciation: hyperscaler capex, fab capex, data-center capex, depreciation schedule, useful life changes.
- Customer adoption: active users, paid seats, ARR/ARPU, retention, churn, usage per customer, conversion.
- Product benchmarks: performance, cost per unit, energy efficiency, latency, quality metrics.
- Policy and trade: export controls, subsidies, procurement rules, localization policy.
- Market data: relative performance, valuation spread, short interest, ownership, options-implied expectations.

## Chain-Layer Metric Examples

| Layer | Typical metrics | Confirming direction | Weakening direction |
|---|---|---|---|
| equipment/materials | order intake, backlog, lead time, tool utilization, gross margin | backlog extends, pricing stable, utilization high | cancellations, lead time normalizes, price discounting |
| manufacturing/packaging | capacity, yield, utilization, customer concentration, capex | capacity sold out, yields improve, long-term agreements | utilization falls, customers dual-source aggressively |
| chips/accelerators | shipments, ASP, gross margin, software lock-in, benchmark lead | strong shipment growth, margin durability, ecosystem lock-in | ASIC substitution, export limits, ASP pressure |
| memory/storage | HBM pricing, bit growth, capacity allocation, inventory | HBM shortage persists, pricing firm | inventory rises, price decline accelerates |
| servers/network/cooling/power | server orders, optics demand, power availability, cooling capex | bottleneck shifts here, orders accelerate | ODM margin pressure, power constraints delay projects |
| cloud/platform | capex, revenue growth, GPU utilization, ROIC, depreciation | capex converts to revenue, utilization high | capex rises faster than revenue, depreciation weighs on margin |
| model/API | token volume, API pricing, training/inference cost, benchmark rank | usage growth exceeds price decline | open-source/API price war erodes margin |
| applications/agents/SaaS | ARR, retention, seat expansion, workflow penetration, gross margin | paid conversion and retention improve | pilots do not convert, churn rises, cost to serve remains high |

## AI Infrastructure Default Watchlist

- Hyperscaler capex and commentary.
- GPU, HBM, advanced packaging, optical module, liquid cooling, and power equipment supply.
- Inference token growth and cost per token decline.
- API price changes and open-source model performance.
- Enterprise AI spend conversion from pilots to production.
- Data-center power availability and interconnect constraints.
- Export controls and domestic substitution progress.
- Depreciation cycle, useful life assumptions, and cloud provider ROIC.

## Evidence Grading

| Grade | Meaning |
|---|---|
| A | primary source, dated, quantitative, directly tied to thesis |
| B | primary or high-quality secondary source, partially quantitative |
| C | reputable secondary source or management commentary without full data |
| D | market rumor, unsourced claim, weakly relevant, or stale data |

Use A/B evidence for conclusions. C/D evidence can motivate questions but should not carry the thesis.
