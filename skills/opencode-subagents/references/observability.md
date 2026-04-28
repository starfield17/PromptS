# Observability Contract

Each run writes a dedicated artifact directory under:

```text
<task.cwd>/.opencode-subagents/runs/<run-id>/
```

`run-many` writes batch metadata under:

```text
<first-task.cwd>/.opencode-subagents/batches/<batch-id>/
```

When `--runs-dir` is provided to `run-many`, that directory becomes the `.opencode-subagents` base and contains both `runs/` and `batches/`.

## Run Files

- `task.json`: normalized task contract used for the run
- `system_prompt.txt`: injected system guidance for the subagent
- `user_prompt.txt`: task-specific prompt rendered from the contract
- `raw.stream.jsonl`: original `opencode run --format json` output
- `ops.jsonl`: reduced event stream for Codex collaboration
- `stderr.log`: raw OpenCode stderr
- `summary.json`: final structured outcome

## Batch Files

- `batch.json`: normalized batch request
- `ops.jsonl`: reduced batch-level events
- `summary.json`: final batch summary with child run paths

## What To Watch

Use `ops.jsonl` for normal collaboration. It contains high-signal JSONL events such as:

- `run_started`
- `opencode_command`
- `step_start`
- `tool_use`
- `tool_result`
- `assistant_text`
- `permission_event`
- `result`
- `run_finished`

Use `raw.stream.jsonl` only when Codex needs full OpenCode event fidelity.

## Summary Shape

`summary.json` includes:

- run status and duration
- OpenCode command, model, variant, agent, and session id when available
- raw and reduced event counts
- tool calls observed from the stream
- permission-like messages detected from stream output or stderr
- final textual result
- parsed `structured_result` when `output_schema` is provided and the final result is JSON
- git-based touched-file and out-of-scope-file detection when `cwd` is a git worktree

Status values:

- `success`: OpenCode exited successfully and no scope violation was detected
- `error`: OpenCode failed or emitted an error event
- `scope_violation`: git tracking found touched files outside the allowed role scope
- `running`: only present while a run is still active

## Typical Codex Loop

1. Start one or more runs with `run` or `run-many`
2. Observe live stdout, or call `tail --follow` on a run directory
3. Read each `summary.json` when the run finishes
4. Inspect raw stream only if reduced events are insufficient
5. Merge results, retry with tighter context, or escalate from `reader` to `worker`
