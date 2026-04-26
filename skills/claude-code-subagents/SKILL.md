---
name: claude-code-subagents
description: use this skill when codex needs to delegate coding, analysis, review, debugging, refactoring, test generation, repository exploration, or documentation tasks to one or more claude code subprocess agents. this skill provides a lightweight protocol for running observable claude code subagents in isolated workspaces, collecting auditable artifacts, and letting codex coordinate follow-up work while retaining final authority.
---

# Claude Code Subagents

Use this skill to run Claude Code as one or more observable subagents under Codex supervision.

The primary agent remains responsible for planning, validation, final decisions, and user-facing answers. Claude Code subagents are disposable workers that inspect code, propose changes, run commands if allowed, and return structured artifacts for review.

## Use this skill when

- the work can be split into narrow tasks
- independent exploration or implementation would benefit from parallelism
- Codex wants an external reviewer, tester, debugger, or adversarial pass
- you want logs, diffs, and status files that Codex can inspect after each run

## Do not use this skill when

- the task is too small to justify process overhead
- the task requires broad authority across the whole repository
- Codex is not prepared to inspect artifacts before applying changes
- the user expects Claude Code to make the final decision without Codex review

## Core rules

- Delegate execution, not authority.
- Prefer small, independent tasks with explicit completion criteria.
- Treat subagent outputs as evidence, not truth.
- Preserve artifacts in `.CC_subagent/` so Codex can audit behavior.
- Inspect `patch.diff`, `result.md`, `status.json`, and `events.jsonl` before accepting a result.
- If multiple tasks touch the same file, escalate to Codex review instead of auto-merging.

## Runtime model

The default runtime root is `.CC_subagent/` under the active repository or working directory. Each task gets:

- `runs/<task-id>/` for observable artifacts
- `workspaces/<task-id>/` for the isolated execution workspace

Execution mode is chosen by the wrapper:

- `git-worktree`: used for clean Git repositories, so `patch.diff` maps cleanly to subagent changes
- `copy`: used for non-Git directories and dirty Git repositories, so the workspace preserves the current local state without mixing in pre-existing edits

The wrapper always writes stable artifacts, even when Claude does not:

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
      status.json
      changed-files.txt
      patch.diff
      session.json
      exit_code.txt
  workspaces/
    <task-id>/
```

## Minimal workflow

1. Decide whether the task should be delegated.
2. Split the work into one or more bounded task files.
3. Author each task in Markdown, preferably from `references/task-template.md`.
4. Launch one task with `scripts/run_subagent.sh` or many with `scripts/run_parallel_subagents.py`.
5. Monitor `status.json` and `events.jsonl` while tasks run.
6. Aggregate results with `scripts/collect_results.py`.
7. Inspect diffs, logs, and claims before applying anything.
8. Launch follow-up reviewer or adversary tasks when evidence conflicts.

## Task authoring

Every task should state:

- task id
- role
- objective
- scope
- out-of-scope areas
- permissions
- completion criteria
- expected outputs

Keep the task format flexible. The wrapper understands only Markdown tasks and artifact paths. Role semantics remain a prompt-layer convention, not a runtime-enforced contract.

See `references/protocol.md` for the full protocol and `references/task-template.md` for the recommended template.

## Observation model

Codex should inspect:

- `status.json` for stable machine-readable status
- `events.jsonl` for raw Claude output events
- `stderr.log` for launcher or CLI failures
- `result.md` for human-readable findings
- `patch.diff` for proposed file changes
- `changed-files.txt` for quick surface-area checks
- `session.json` for runtime metadata and workspace mode

If a claim matters, verify it independently. Do not accept a subagent result purely because it reports `success`.

## Suggested roles

Codex may define any role, but these common ones work well:

- `explorer`
- `implementer`
- `reviewer`
- `tester`
- `debugger`
- `documenter`
- `adversary`

See `references/delegation-patterns.md` for example coordination patterns.

## Safety and containment

Prefer narrow scope and explicit permissions. Avoid broad authority to:

- rewrite unrelated files
- delete files
- touch credentials or secrets
- install global dependencies
- modify lockfiles unless the task requires it
- run destructive commands outside the isolated workspace

If broad permissions are necessary, say why in the task file.

## Coordination reminders

- Prefer one task per concern.
- Prefer reviewer subagents for large or risky patches.
- Preserve failing or partial runs; they are useful evidence.
- If two subagents disagree, inspect artifacts and launch a focused follow-up task instead of averaging answers.
- After accepting changes, run validation from Codex when the repository supports it.

This skill is successful when Codex gains an observable, parallel, auditable Claude Code worker pool without giving up final control.
