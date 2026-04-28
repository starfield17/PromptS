# Evidence Policy

## Evidence Types

Classify every important input as one of:

```text
Primary evidence
Secondary evidence
Market evidence
Management claim
Model output
User-provided assumption
Unverified claim
```

## Fact / Interpretation / Hypothesis

Use this triad consistently.

### Fact

A statement supported by a source or direct calculation.

```text
Fact: Company X disclosed Y revenue in segment Z.
```

### Interpretation

A reasoned reading of facts.

```text
Interpretation: Segment growth suggests customer adoption is improving, but margin impact is not yet visible.
```

### Hypothesis

A testable forward-looking claim.

```text
Hypothesis: If customer adoption continues, suppliers in layer A should show backlog growth within two reporting cycles.
```

## Source Reliability

Prefer:

```text
filings
earnings calls
company IR material
regulatory data
exchange announcements
industry bodies
reputable financial media
```

Be cautious with:

```text
social media
anonymous claims
aggregated SEO pages
promotional investor decks
single-source rumors
```

## Source Pack Requirements

A source pack should include:

```text
Title
URL or local reference
Source type
Publisher
Date
Reliability score
Relevant claims
Linked variables
```

## Handling Unknowns

When uncertain, write:

```text
Unknown:
Source needed:
Assumption:
```

Do not fill gaps with confident language.

## Freshness

Market narratives, prices, guidance, laws, regulations, and management teams can change quickly. Treat them as time-sensitive.

For a live production system, these should be verified by scripts or web access before being used as current facts:

```text
current price
valuation multiple
latest guidance
current management
recent policy
recent capacity plans
latest earnings
latest product roadmap
market consensus
```

## Evidence-to-Thesis Chain

Every thesis should be traceable:

```text
Source → Fact → Interpretation → Hypothesis → Variable → Falsification
```

## Contradictory Evidence

Do not hide contradictory data. Use this structure:

```text
Supporting evidence:
Contradictory evidence:
Which side matters more:
What data would resolve it:
```

## Minimum Evidence Standard by Judgment Level

### A. Discard

Requires enough evidence to show the problem or economics are weak.

### B. Watch

Requires a plausible problem but insufficient evidence on timing, economics, or consensus.

### C. Deep Dive

Requires evidence of a real problem and possible profit pool.

### D. Potential Investment Thesis

Requires clear support for:

```text
problem
profit pool
variant view
variables
falsification
```
