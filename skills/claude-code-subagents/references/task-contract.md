# Task Contract

`claude_subagent.py run` expects a JSON object with this shape:

```json
{
  "name": "short task name",
  "role": "reader",
  "goal": "Clear bounded objective for Claude",
  "cwd": "/absolute/path/to/target/workspace",
  "context": [
    "Optional context bullet 1",
    "Optional context bullet 2"
  ],
  "constraints": [
    "Optional constraint 1",
    "Optional constraint 2"
  ],
  "deliverables": [
    "What Claude should return"
  ],
  "allowed_tools": [
    "Read",
    "Grep",
    "Glob"
  ],
  "write_scope": [],
  "prepare_dirs": [],
  "output_schema": {
    "type": "object"
  }
}
```

## Field Notes

- `name`: human-readable label used in the run id and summary
- `role`: `reader` or `worker`
- `goal`: the one thing the subagent should accomplish
- `cwd`: target workspace Claude should run inside
- `context`: optional extra facts, file paths, or short structured blobs
- `constraints`: optional rules Claude must obey
- `deliverables`: optional checklist for the final answer
- `allowed_tools`: optional explicit Claude tool list; defaults depend on `role`
- `write_scope`: required for `worker`; soft guard expressed in the injected prompt
- `prepare_dirs`: optional extra directories to create before a `worker` run starts
- `output_schema`: optional JSON Schema forwarded to Claude for structured output

For `worker` tasks, both `write_scope` and `prepare_dirs` must stay within `cwd` after path resolution.

## Default Tool Policies

If `allowed_tools` is omitted:

- `reader` defaults to `Read`, `Grep`, `Glob`, `WebFetch`, `WebSearch`
- `worker` defaults to `Read`, `Grep`, `Glob`, `Edit`, `Write`

If Codex wants shell access, it must request it explicitly in `allowed_tools`.

Even when shell access is allowed, prefer `Write` and `Edit` for file creation. The wrapper creates parent directories implied by `write_scope` before launching Claude.

## Example: Reader

```json
{
  "name": "trace config loader",
  "role": "reader",
  "goal": "Find where config precedence is defined and summarize the exact order.",
  "cwd": "/repo",
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
  "prepare_dirs": [
    "src/generated"
  ],
  "write_scope": [
    "src/parser.ts",
    "tests/parser.test.ts"
  ]
}
```

In this example, the wrapper creates `src/` from `write_scope` automatically and also prepares `src/generated/` because it was listed explicitly in `prepare_dirs`.
