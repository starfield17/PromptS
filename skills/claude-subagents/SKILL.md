---
name: claude-subagents
description: This skill should be used when Codex needs to delegate a bounded task to one or more local Claude Code workers, especially for parallel analysis, review, drafting, or isolated code edits outside Codex's native subagent system.
---

# Claude Subagents

## Overview

Delegate bounded work to the local `claude` CLI through `scripts/claude_worker.py`.
Choose `readonly` workers for analysis, review, search, and drafting. Choose `editor`
workers for isolated implementation tasks inside a specific working directory.

## When To Use

Use this skill when a task benefits from an external Claude Code worker instead of a
native Codex subagent.

- Launch multiple workers in parallel for independent subtasks.
- Request a second implementation or review pass from Claude Code specifically.
- Keep a write-capable worker scoped to a disposable or isolated directory.
- Avoid this skill for tiny tasks that Codex can finish directly.

## Workflow

### 1. Write a bounded task file

Create a plain-text prompt file that includes:

- the concrete goal,
- exact scope boundaries,
- the expected output shape,
- any files or directories that are in or out of scope.

Prefer one worker per task file.

### 2. Choose the worker mode

- `readonly`: use for analysis, review, planning, drafting, and code reading. This mode
  runs Claude with `Read,Grep,Glob,LS` only.
- `editor`: use for isolated implementation tasks. This mode runs Claude with default
  tools and `--permission-mode acceptEdits` inside the delegated `--cwd`.

Decide the mode explicitly. Do not send write work to a `readonly` worker.

### 3. Launch one or more workers

Run:

```bash
python scripts/claude_worker.py start --mode readonly --task-file /tmp/task.txt --cwd /path/to/repo
python scripts/claude_worker.py start --mode editor --task-file /tmp/task.txt --cwd /path/to/sandbox
```

For parallel work, launch separate workers with separate task files. For `editor`
workers, prefer disjoint working directories or disjoint file ownership.

### 4. Poll status and collect the result

Run:

```bash
python scripts/claude_worker.py status --worker-id <worker-id>
python scripts/claude_worker.py result --worker-id <worker-id>
python scripts/claude_worker.py list
```

Worker artifacts live under `runs/<worker-id>/` and include:

- `prompt.txt`
- `metadata.json`
- `status.json`
- `stdout.json`
- `stderr.txt`
- `result.json`
- `summary.txt`

### 5. Clean up finished workers

Run:

```bash
python scripts/claude_worker.py cleanup --worker-id <worker-id>
python scripts/claude_worker.py cleanup --all-finished
```

Remove finished worker directories when they are no longer needed.

## Task File Template

Use a structure like this:

```text
Goal:
- <single concrete objective>

Context:
- <repo or directory>
- <important files or constraints>

Mode-specific rules:
- <readonly: no edits, explain findings>
- <editor: change only the named files>

Expected output:
- <summary, patch description, checklist, test notes, etc.>
```

Keep prompts short and concrete. Prefer explicit file paths and success criteria over
open-ended instructions.

## Operating Notes

- Assume the local `claude` CLI is already installed and authenticated.
- Prefer `readonly` unless the worker truly needs to edit files.
- Treat `result.json` as the normalized machine-readable outcome and `summary.txt` as
  the quick human-readable handoff.
- If a worker must edit files, keep its `--cwd` as narrow as possible.
