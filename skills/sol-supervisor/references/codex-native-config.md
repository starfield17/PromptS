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

The default leaf is Luna xhigh. Select Terra explicitly for broad bounded synthesis/debugging/review. Six open child threads are capacity, not a target; prefer the smallest independent wave that quarantines meaningful context.

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
→ exceptional; normally escalate to Sol instead
```

Do not use Luna low/medium/high or Terra low/medium under this skill.

## Workflow reinforcement in AGENTS.md

If the skill still does not trigger delegation reliably enough, add only this short always-on rule to the applicable `AGENTS.md`:

```text
When sol-supervisor applies, every non-trivial task follows:
ROUTE → DELEGATE → WAIT → SOL DECIDE → EXECUTE → VERIFY/REVIEW → SOL ACCEPT.
Before substantial exploration or implementation, assign each work unit to Sol, Terra, or Luna.
At least one eligible work unit must be delegated unless every remaining unit is inherently Sol-owned.
Never silently take a delegated unit back into Sol while waiting.
Use Luna xhigh/max and Terra high/xhigh; avoid Terra max.
```

This reinforces the state-machine invariant without duplicating the full skill.

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

## Optional read-only reviewer role

Create `.codex/agents/reviewer.toml` in a trusted project or `~/.codex/agents/reviewer.toml` globally:

```toml
name = "reviewer"
description = "Read-only bounded reviewer for correctness, regressions, and missing tests before the primary agent performs final acceptance."
sandbox_mode = "read-only"

developer_instructions = """
Review only the assigned scope.
Prioritize correctness, behavior regressions, edge cases, and missing tests.
Lead with concrete findings and cite files/symbols.
Do not redesign architecture or approve the final diff.
Return uncertainty explicitly.
"""
```

Intentionally omit model/effort so the parent can choose Terra high/xhigh or Luna xhigh as appropriate.

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

For large documents, the parent may spawn several `ocr_reader` leaves over disjoint page/range assignments and then send the page-referenced outputs to Terra high for synthesis.

## Sandbox precedence caveat

A custom agent may set `sandbox_mode`, but live parent-turn runtime overrides can take precedence when a child is spawned. Treat the effective runtime permission as authoritative.

## Thread communication

Codex manages spawning, follow-up routing, waiting, steering, stopping, and closing agent threads. Threads remain separate contexts.

Use explicit follow-up/agent messaging to transmit small evidence packets. Prefer steering an existing on-scope thread once over spawning a duplicate agent with the same question.
