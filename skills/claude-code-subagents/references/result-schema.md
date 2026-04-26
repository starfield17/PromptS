# Result Schema

Subagents and the wrapper together should produce stable machine-readable and human-readable artifacts.

## status.json

```json
{
  "task_id": "example-task",
  "role": "explorer",
  "state": "finished",
  "status": "success",
  "summary": "Identified the relevant files and recommended a minimal implementation path.",
  "confidence": "medium",
  "files_touched": [],
  "tests_run": [],
  "tests_passed": null,
  "blocking_issues": [],
  "follow_up_recommendations": ["Launch an implementer subagent scoped to src/api."],
  "workspace_mode": "copy",
  "workspace_path": "/repo/.CC_subagent/workspaces/example-task",
  "started_at": "2026-04-26T10:00:00Z",
  "finished_at": "2026-04-26T10:02:00Z",
  "exit_code": 0
}
```

## changed-files.txt

One path per line. Leave empty if no files were changed.

## patch.diff

Unified diff of changes. Leave empty if no patch was created.

## session.json

Launcher-owned metadata for the run:

```json
{
  "task_id": "example-task",
  "role": "explorer",
  "task_file": "/repo/tasks/example-task.md",
  "source_root": "/repo",
  "runtime_root": "/repo/.CC_subagent",
  "run_dir": "/repo/.CC_subagent/runs/example-task",
  "workspace_path": "/repo/.CC_subagent/workspaces/example-task",
  "workspace_mode": "copy",
  "claude_bin": "claude",
  "extra_args": ["--model", "sonnet"],
  "started_at": "2026-04-26T10:00:00Z",
  "finished_at": "2026-04-26T10:02:00Z",
  "exit_code": 0
}
```

## summary.json

`scripts/collect_results.py` should also produce a root-level `summary.json` that includes:

- task count
- normalized task statuses
- file collision warnings
- recommended follow-up actions
