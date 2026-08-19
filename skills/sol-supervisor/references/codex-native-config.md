# Codex native subagent configuration

This reference is optional. Use it when configuring Codex for `sol-supervisor`.

## Recommended global defaults

Put this in `~/.codex/config.toml` (or adapt it to a trusted project's `.codex/config.toml`):

```toml
[agents]
enabled = true
max_concurrent_threads_per_session = 4
default_subagent_model = "gpt-5.6-luna"
default_subagent_reasoning_effort = "medium"
```

Why:

- Luna is the cheapest sensible default leaf model.
- Terra should normally be selected explicitly when broad context/synthesis is needed.
- Four concurrent child threads is enough for useful parallelism without encouraging agent swarms. Increase only for genuinely independent read-heavy work.

Explicit spawn values override these defaults.

## Prefer roles over model-specific role files

Keep **role** and **model** separate.

Use built-in roles where possible:

- `explorer` — read-heavy mapping/evidence gathering;
- `worker` — implementation/fixes;
- `default` — only when neither specialized role fits.

Then select model/effort per task:

```text
explorer + Luna medium
→ narrow search / symbol mapping

worker + Luna high
→ clear bounded implementation

explorer + Terra medium/high
→ broad or cross-module investigation

worker + Terra high/xhigh
→ context-heavy bounded implementation/debugging
```

Do not create separate `luna_worker`, `terra_worker`, `luna_explorer`, and `terra_explorer` roles unless they truly need different tool/sandbox/instruction policies. Model identity is not a role.

## Optional read-only reviewer role

If a persistent Terra pre-review role is useful, create `.codex/agents/reviewer.toml` in a trusted project or `~/.codex/agents/reviewer.toml` globally:

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

Intentionally omit `model` and `model_reasoning_effort`. The parent can spawn this role with Terra high for broad review, Luna high for narrow factual checking, or another explicit choice later without duplicating role files.

## Sandbox precedence caveat

A custom agent may set `sandbox_mode`, but live parent-turn runtime overrides can take precedence when a child is spawned. Treat the effective runtime permission as authoritative and do not rely solely on the agent file for safety.

## Thread communication

Codex manages spawning, follow-up routing, waiting, steering, stopping, and closing agent threads. Threads remain separate contexts.

Use explicit follow-up/agent messaging when available to transmit small evidence packets. Do not assume another agent has seen the parent thread, sibling findings, or raw logs unless those facts were explicitly provided.

Prefer steering an existing on-scope thread once over spawning a duplicate agent with the same question.
