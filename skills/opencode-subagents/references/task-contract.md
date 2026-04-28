# Task Contract

`opencode_subagent.py run` expects a JSON object with this shape:

```json
{
  "name": "short task name",
  "role": "reader",
  "goal": "Clear bounded objective for OpenCode",
  "cwd": "/absolute/path/to/target/workspace",
  "model": "anthropic/claude-sonnet-4-5",
  "variant": "high",
  "agent": "build",
  "context": [
    "Optional context bullet 1",
    "Optional context bullet 2"
  ],
  "constraints": [
    "Optional constraint 1"
  ],
  "deliverables": [
    "What OpenCode should return"
  ],
  "files": [
    "optional/path/to/attach.txt"
  ],
  "write_scope": [],
  "output_schema": null,
  "dangerously_skip_permissions": false
}
```

## Field Notes

- `name`: human-readable label used in the run id and OpenCode session title
- `role`: `reader` or `worker`
- `goal`: the one thing the subagent should accomplish
- `cwd`: target workspace OpenCode should run inside
- `model`: optional OpenCode model in `provider/model` format
- `variant`: optional provider-specific model variant, such as `high` or `max`
- `agent`: optional OpenCode agent name, used only when the workspace already has that agent configured
- `context`: optional extra facts, file paths, or short structured blobs
- `constraints`: optional rules OpenCode must obey
- `deliverables`: optional checklist for the final answer
- `files`: optional files forwarded as repeated `opencode run --file` arguments
- `write_scope`: required for `worker`; forbidden for `reader`
- `output_schema`: optional JSON Schema-like object included in the prompt and used for final-result parsing
- `dangerously_skip_permissions`: default `false`; when true, forwards `--dangerously-skip-permissions`

For `worker` tasks, every `write_scope` path must stay within `cwd` after path resolution.

## Example: Reader

```json
{
  "name": "trace config loader",
  "role": "reader",
  "goal": "Find where config precedence is defined and summarize the exact order.",
  "cwd": "/repo",
  "model": "anthropic/claude-sonnet-4-5",
  "context": [
    "Focus on runtime config loading only.",
    "Return concrete file paths and function names."
  ],
  "constraints": [
    "Do not suggest refactors.",
    "Use tools instead of guessing."
  ],
  "deliverables": [
    "A concise summary of the precedence order",
    "The files and functions that implement it"
  ]
}
```

## Example: Worker

```json
{
  "name": "patch parser edge case",
  "role": "worker",
  "goal": "Fix the parser bug for empty input and keep the change minimal.",
  "cwd": "/repo",
  "model": "anthropic/claude-sonnet-4-5",
  "context": [
    "A failing repro already exists in tests/parser.test.ts."
  ],
  "constraints": [
    "Touch only the parser implementation and the adjacent test if needed."
  ],
  "deliverables": [
    "Minimal fix",
    "Short changed-files summary",
    "Any residual risk or blocker"
  ],
  "write_scope": [
    "src/parser.ts",
    "tests/parser.test.ts"
  ]
}
```

## Example: Batch

`opencode_subagent.py run-many` expects a JSON object with defaults and tasks:

```json
{
  "defaults": {
    "cwd": "/repo",
    "model": "anthropic/claude-sonnet-4-5",
    "variant": "high"
  },
  "max_parallel": null,
  "tasks": [
    {
      "name": "inspect auth flow",
      "role": "reader",
      "goal": "Map the auth flow and identify likely bug points."
    },
    {
      "name": "inspect config flow",
      "role": "reader",
      "goal": "Map config loading and precedence."
    }
  ]
}
```

Batch rules:

- Task fields override `defaults`
- `max_parallel: null` starts all tasks at once
- Multiple `worker` tasks must have non-overlapping `write_scope` paths
- Failed tasks are recorded in the batch summary; Codex decides whether to retry
