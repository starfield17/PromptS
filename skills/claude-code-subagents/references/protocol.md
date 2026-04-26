# Claude Code Subagent Protocol

This protocol defines how Codex should describe work to Claude Code subagents and how subagents should report observable results.

## Task file schema

Each subagent task should be written as Markdown.

Required fields:

```markdown
# Task: <task-id>

## Role
<explorer | implementer | reviewer | tester | debugger | documenter | adversary | custom>

## Objective
Clear single objective.

## Context
Relevant background from Codex.

## Scope
Files, directories, modules, or concepts the subagent may inspect.

## Out of scope
Things the subagent should avoid.

## Permissions
- May edit files: yes/no
- May run tests: yes/no
- May install dependencies: yes/no
- May use network: yes/no
- May create new files: yes/no

## Expected output
The subagent must write:

- result.md
- status.json
- changed-files.txt
- patch.diff, if changes were made

## Completion criteria
Concrete condition for finishing.

## Notes for Claude Code
Be explicit. Report uncertainty. Do not hide failed attempts.
```

## Runtime layout

Runtime output should be written under the active repository or working directory, not inside the packaged skill.

```text
.CC_subagent/
  index.json
  summary.md
  summary.json
  runs/
    <task-id>/
      task.md
      prompt.md
      events.jsonl
      stderr.log
      result.md
      changed-files.txt
      patch.diff
      status.json
      session.json
      exit_code.txt
  workspaces/
    <task-id>/
```

When `copy` mode is used, the wrapper may also create internal snapshot material under `runs/<task-id>/` so it can build a stable `patch.diff`.

## Runtime modes

- `git-worktree`: preferred for clean Git repositories; produces Git-native diffs in an isolated linked worktree
- `copy`: used for non-Git directories or dirty Git repositories; copies the current local state into an isolated workspace so pre-existing edits are not mistaken for subagent edits

Codex should treat `workspace_mode` as an observable fact, not as a user-facing concern.

## status.json schema

```json
{
  "task_id": "string",
  "role": "string",
  "state": "queued | running | finished",
  "status": "success | partial | failed | blocked | timeout | unknown",
  "summary": "string",
  "confidence": "low | medium | high",
  "files_touched": ["string"],
  "tests_run": ["string"],
  "tests_passed": true,
  "blocking_issues": ["string"],
  "follow_up_recommendations": ["string"],
  "workspace_mode": "git-worktree | copy",
  "workspace_path": "string",
  "started_at": "ISO-8601 string",
  "finished_at": "ISO-8601 string or null",
  "exit_code": 0
}
```

## result.md schema

```markdown
# Result

## Summary
What the subagent did.

## Findings
Important observations.

## Changes
Files changed and why.

## Tests
Commands run and results.

## Risks
Potential issues or edge cases.

## Recommended next steps
What Codex should do next.

## Unresolved questions
Anything unclear or blocked.
```

## session.json schema

`session.json` is launcher-owned metadata. It should record enough information for Codex to audit the run without parsing the shell wrapper itself.

Suggested fields:

```json
{
  "task_id": "string",
  "role": "string",
  "task_file": "string",
  "source_root": "string",
  "runtime_root": "string",
  "run_dir": "string",
  "workspace_path": "string",
  "workspace_mode": "git-worktree | copy",
  "claude_bin": "string",
  "extra_args": ["string"],
  "started_at": "ISO-8601 string",
  "finished_at": "ISO-8601 string or null",
  "exit_code": 0
}
```

## events.jsonl

`events.jsonl` is the raw stdout stream from Claude Code. The wrapper should prefer `claude -p --output-format stream-json --include-partial-messages` when available so Codex can observe incremental behavior without parsing the human-readable final answer.

## Prompt wrapper

Codex should append this instruction to every subagent task:

```text
You are running as a Claude Code subagent supervised by Codex. Complete only the assigned task. Work only inside your isolated workspace unless the task explicitly says otherwise. Write observable outputs to the requested files. Be honest about uncertainty, failed commands, and incomplete work. Do not claim success unless the completion criteria are met.
```

## Conflict handling

If subagents disagree, Codex should not average their answers. Inspect the underlying evidence, diffs, tests, and logs. If necessary, launch a reviewer or adversary subagent with the conflicting outputs as context.

If two successful tasks touch the same file, treat that as a manual review boundary even when their summaries do not mention a conflict.
