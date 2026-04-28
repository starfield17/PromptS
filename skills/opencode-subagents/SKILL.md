---
name: opencode-subagents
description: Use this skill when Codex should delegate one or more bounded tasks to the local opencode CLI as observable subagents, especially for parallel reader tasks, isolated worker tasks, second-opinion analysis, or collaborations where Codex must inspect opencode's concrete behavior and outputs. Supports per-task provider/model selection.
---

# opencode Subagents

## Overview

This skill lets Codex use the local `opencode` CLI as an external subagent runner.

Keep the split of responsibilities simple:

- Codex decides whether a task is a `reader` or a `worker`
- Codex chooses a model with OpenCode's `provider/model` format when needed
- Codex prepares a small task contract for each subtask
- Codex launches one or more OpenCode runs in parallel
- Codex watches `ops.jsonl` for collaboration and `summary.json` for final results

The skill does not decompose tasks, choose when delegation is worth it, or merge results for Codex. It only provides a stable handoff contract plus observable run artifacts.

## When To Use

Use this skill when at least one of these is true:

- You want another model to inspect code, logs, or docs independently
- You want multiple bounded subtasks to run in parallel
- You want Codex to inspect OpenCode's actual tool calls and outputs
- You want a separate `worker` to make a narrow edit with an explicit write scope
- You want per-task model selection through OpenCode, such as `anthropic/claude-sonnet-4-5` or another configured provider model
- You want a durable artifact trail for later review or retry

Do not use this skill when Codex can finish the work directly without meaningful benefit from delegation.

## Quick Start

1. Create a task JSON using the contract in `references/task-contract.md`
2. Run `scripts/opencode_subagent.py run --task-file /path/to/task.json`
3. For parallel work, create a batch JSON and run `scripts/opencode_subagent.py run-many --batch-file /path/to/batch.json`
4. Watch live reduced events on stdout or inspect `.opencode-subagents/runs/.../ops.jsonl`
5. Read `.opencode-subagents/runs/.../summary.json` when each run finishes

Useful follow-up commands:

- `scripts/opencode_subagent.py tail /path/to/run-dir --follow`
- `scripts/opencode_subagent.py summary /path/to/run-dir`

## Roles

### `reader`

Use `reader` for bounded analysis tasks.

- The injected prompt is read-only
- `write_scope` is forbidden
- Good for code reading, grep-based investigation, log inspection, and independent review
- If the run changes files anyway, the wrapper marks the result as `scope_violation` when git tracking is available

### `worker`

Use `worker` only when the task needs file changes.

- `write_scope` is required
- The injected prompt tells OpenCode to touch only files inside that scope
- The wrapper validates that `write_scope` stays inside `cwd`
- Parallel `worker` runs are safe only when their write scopes do not overlap
- If the run changes files outside scope, the wrapper marks the result as `scope_violation` when git tracking is available

## How Codex Should Delegate

Keep each task contract small and decision-complete.

- One task should have one clear goal
- Include only the minimum context OpenCode needs
- State constraints explicitly instead of assuming them
- Ask for concrete deliverables Codex can consume directly
- Prefer several narrow `reader` tasks over one broad exploratory task
- Use `model` only when a specific OpenCode provider/model should run the task
- Use `agent` only when the target workspace already has an appropriate OpenCode agent

For `worker` tasks, give disjoint write scopes when running in parallel. The wrapper rejects obvious overlap in `run-many`, but Codex is still responsible for assigning independent work.

## Run Artifacts

Each run creates its own directory under the task `cwd`:

- `.opencode-subagents/runs/<run-id>/task.json`
- `.opencode-subagents/runs/<run-id>/system_prompt.txt`
- `.opencode-subagents/runs/<run-id>/user_prompt.txt`
- `.opencode-subagents/runs/<run-id>/raw.stream.jsonl`
- `.opencode-subagents/runs/<run-id>/ops.jsonl`
- `.opencode-subagents/runs/<run-id>/stderr.log`
- `.opencode-subagents/runs/<run-id>/summary.json`

`run-many` also writes a batch directory under `.opencode-subagents/batches/<batch-id>/`.

Use `ops.jsonl` for normal collaboration. Use `raw.stream.jsonl` only when Codex needs full OpenCode event fidelity.

For the exact task schema and examples, read `references/task-contract.md`.

For the observability contract and file meanings, read `references/observability.md`.
