# Observability Contract

Each run writes a dedicated artifact directory under:

```text
<task.cwd>/.claude-subagents/runs/<run-id>/
```

## Files

- `task.json`: normalized task contract used for the run
- `system_prompt.txt`: injected system guidance for Claude
- `user_prompt.txt`: task-specific prompt rendered from the contract
- `raw.stream.jsonl`: original `claude --output-format stream-json` output
- `ops.jsonl`: reduced event stream for Codex collaboration
- `stderr.log`: raw Claude stderr
- `summary.json`: final structured outcome

## What To Watch

Use `ops.jsonl` for normal collaboration. It contains high-signal JSONL events such as:

- `run_started`
- `prepared_dirs`
- `status`
- `tool_use`
- `tool_result`
- `permission_denial`
- `structured_result`
- `assistant_text`
- `result`
- `run_finished`

Use `raw.stream.jsonl` only when Codex needs full event fidelity, including raw stream events and provider metadata.

## Summary Shape

`summary.json` includes the run status, duration, model, session id, tool calls, costs, permission denials, and final result. If Claude emits a `StructuredOutput` tool call, that payload is stored directly in `structured_result`. When no such tool call exists, the wrapper falls back to parsing the final textual result as JSON only when `output_schema` was provided.

## Typical Codex Loop

1. Start one or more runs with `run`
2. Observe live stdout or call `tail --follow`
3. Read `summary.json` when each run finishes
4. Merge results, retry with tighter context, or escalate to a `worker`
