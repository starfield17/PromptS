---
name: claude-subagents
description: Use this skill when Codex should delegate one or more bounded tasks to the local Claude Code CLI as observable subagents, especially for parallel reader tasks, isolated worker tasks, second-opinion analysis, or collaborations where Codex must inspect Claude's concrete tool behavior and outputs.
---

# Claude Subagents

## Overview

This skill lets Codex use the local `claude` CLI as an external subagent runner.

Keep the split of responsibilities simple:

- Codex decides whether a task is a `reader` or a `worker`
- Codex prepares a small task contract for each subtask
- Codex launches one or more Claude runs in parallel
- Codex watches `ops.jsonl` for collaboration and `summary.json` for final results

The skill does not do task decomposition, scheduling, or result synthesis for Codex. It only provides a stable handoff contract plus observable run artifacts.

## When To Use

Use this skill when at least one of these is true:

- You want a second model to inspect code, logs, or docs independently
- You want multiple bounded subtasks to run in parallel
- You want Codex to inspect Claude's actual tool calls and outputs
- You want a separate `worker` to make a narrow edit with an explicit write scope
- You want a durable artifact trail for later review or retry

Do not use this skill when Codex can finish the work directly without meaningful benefit from delegation.

## Quick Start

1. Create a task JSON using the contract in `references/task-contract.md`
2. Run `scripts/claude_subagent.py run --task-file /path/to/task.json`
3. Watch the live JSONL events on stdout or inspect `.claude-subagents/runs/.../ops.jsonl`
4. Read `.claude-subagents/runs/.../summary.json` when the run finishes

Useful follow-up commands:

- `scripts/claude_subagent.py tail /path/to/run-dir --follow`
- `scripts/claude_subagent.py summary /path/to/run-dir`

## Roles

### `reader`

Use `reader` for bounded analysis tasks.

- Default tool policy is read-only
- No file edits are allowed
- Good for code reading, grep-based investigation, log inspection, and independent review

### `worker`

Use `worker` only when the task needs file changes.

- `write_scope` is required
- The wrapper injects an explicit scope rule into Claude's instructions
- Parallel `worker` runs are safe only when their write scopes do not overlap or their working directories are isolated

## How Codex Should Delegate

Keep each task contract small and decision-complete.

- One task should have one clear goal
- Include only the minimum context Claude needs
- State constraints explicitly instead of assuming them
- Ask for concrete deliverables Codex can consume directly
- Prefer several narrow `reader` tasks over one broad exploratory task

If a task needs structured output, set `output_schema` in the task JSON so the wrapper asks Claude for machine-parseable output.

For `worker` tasks, the wrapper prepares parent directories for files listed in `write_scope` before Claude starts. Use `prepare_dirs` only for extra directories that are not implied by `write_scope`.

## Run Artifacts

Each run creates its own directory under the task `cwd`:

- `.claude-subagents/runs/<run-id>/task.json`
- `.claude-subagents/runs/<run-id>/system_prompt.txt`
- `.claude-subagents/runs/<run-id>/user_prompt.txt`
- `.claude-subagents/runs/<run-id>/raw.stream.jsonl`
- `.claude-subagents/runs/<run-id>/ops.jsonl`
- `.claude-subagents/runs/<run-id>/summary.json`

Use `ops.jsonl` for day-to-day collaboration. Use `raw.stream.jsonl` only when Codex needs the full Claude event stream.

The wrapper also records `prepared_dirs` and `permission_denial` events in `ops.jsonl`, and captures `StructuredOutput` payloads directly into `summary.json.structured_result`.

For the exact task schema and example payloads, read `references/task-contract.md`.

For the observability contract and file meanings, read `references/observability.md`.
