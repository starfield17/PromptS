# Codex native subagent configuration

Use this reference only when configuring Codex for `sol-supervisor`.

## Recommended global defaults

Put this in `~/.codex/config.toml` or adapt it to a trusted project's `.codex/config.toml`:

```toml
[agents]
enabled = true
max_concurrent_threads_per_session = 6
default_subagent_model = "gpt-5.6-luna"
default_subagent_reasoning_effort = "xhigh"
```

The default leaf is Luna xhigh. Select Terra explicitly for broad bounded synthesis/debugging/review. Six open child threads are capacity, not a target. Delegation should have positive expected value after prompt, coordination, waiting, synthesis, and reread cost.

## Normal model/effort combinations

```text
Luna xhigh
→ default narrow exploration / implementation / tests / validation / OCR

Luna max
→ unusually demanding but still narrow and architecture-free work

Terra high
→ default broad-context exploration / synthesis / debugging / pre-review

Terra xhigh
→ difficult broad-but-bounded work

Terra max
→ avoid; normally escalate to Sol instead
```

Do not use Luna low/medium/high or Terra low/medium under this skill.

Reasoning effort and model tier are separate controls. A higher effort setting does not erase a capability-floor mismatch.

## Optional workflow reinforcement in AGENTS.md

If the skill needs a short always-on reminder, use a value/capability rule rather than a delegation quota:

```text
When sol-supervisor applies, assess ambiguity, breadth, coupling, parallelism, and capability floor before substantial work.
Use DIRECT, SCOUT, PARALLEL, and PIPELINE as reusable execution patterns.
Delegate only when the unit has a stable contract, does not require repeated unresolved Sol judgment, the assigned model clears the capability floor, and delegation has positive value after coordination cost.
Run dependency-ready work instead of waiting by phase.
Keep Luna at xhigh/max and Terra at high/xhigh; avoid Terra max.
Keep high-entropy diagnosis, unresolved judgment, subtle semantic review, integration, and final acceptance with Sol.
Protect Sol from noise, not from critical semantic context.
```

Do **not** add an "at least one delegated unit" requirement. Subagent utilization is not an objective.

## Prefer roles over model-specific role files

Keep role and model separate for general engineering work:

- `explorer` — read-heavy mapping/evidence gathering;
- `worker` — implementation/fixes;
- `default` — only when neither specialized role fits.

Examples:

```text
explorer + Luna xhigh
→ narrow search / symbol mapping

worker + Luna xhigh/max
→ clear bounded implementation

explorer + Terra high/xhigh
→ broad or cross-module investigation

worker + Terra high/xhigh
→ context-heavy bounded implementation/debugging
```

A bounded unit can still require Sol if its capability floor is high, especially when the hard part is generating a non-obvious hypothesis rather than gathering facts.

## Optional read-only reviewer role

Create `.codex/agents/reviewer.toml` in a trusted project or `~/.codex/agents/reviewer.toml` globally:

```toml
name = "reviewer"
description = "Read-only bounded reviewer for correctness, regressions, subtle semantic risks, and missing tests before the primary agent performs final acceptance."
sandbox_mode = "read-only"

developer_instructions = """
Review only the assigned scope.
Prioritize correctness, behavior regressions, edge cases, and missing tests.
Lead with concrete findings and cite files/symbols.
Do not redesign architecture or approve the final diff.
Return uncertainty explicitly.
If independent judgment is requested, inspect expected behavior, actual behavior, diff/evidence, and relevant source before adopting the implementer's root-cause narrative.
"""
```

Intentionally omit model/effort so the parent can choose Terra high/xhigh or Luna xhigh when their capability floors are sufficient. Use Sol for subtle/high-entropy review when the risk demands it.

## Optional Luna OCR role

For repeated scanned-document/image work, a specialized visual transcription role is useful. Create `.codex/agents/ocr_reader.toml` or `~/.codex/agents/ocr_reader.toml`:

```toml
name = "ocr_reader"
description = "Read-only Luna visual transcription/OCR agent for scans, screenshots, handwriting, forms, and non-standard document text."
model = "gpt-5.6-luna"
model_reasoning_effort = "xhigh"
sandbox_mode = "read-only"

developer_instructions = """
Act as a faithful visual transcription/OCR worker.
Transcribe before interpreting.
Preserve page/order identity and material layout relationships.
Mark uncertain spans explicitly as [uncertain: ...] or [illegible].
Do not silently normalize or correct names, numbers, dates, citations, identifiers, or handwriting.
Return page-referenced transcription plus uncertainty; do not summarize unless the parent asks separately.
"""
```

Use Luna max explicitly for rare pages where xhigh is still uncertain and the task remains pure transcription/visual reading.

For large documents, the parent may spawn several `ocr_reader` leaves over disjoint page/range assignments and then send page-referenced outputs to Terra high for synthesis.

## Sandbox precedence caveat

A custom agent may set `sandbox_mode`, but live parent-turn runtime overrides can take precedence when a child is spawned. Treat the effective runtime permission as authoritative.

## Thread communication

Codex manages spawning, follow-up routing, waiting, steering, stopping, and closing agent threads. Threads remain separate contexts.

Use explicit follow-up/agent messaging to transmit compact evidence packets. Prefer steering an existing on-scope thread once over spawning a duplicate agent with the same question.

Do not treat waiting as a mandatory state-machine phase. Continue other dependency-ready work and wait only when the next meaningful decision is blocked.

Deliberate redundant analysis is allowed when independence itself is the validation mechanism; accidental replay merely to stay busy is not.
