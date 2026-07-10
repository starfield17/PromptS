---
name: subagent-broker
description: Delegate bounded coding, review, exploration, testing, or patch-generation tasks to external harnesses such as Grok Build, Claude Code, OpenCode, Codex CLI, or cheap model workers. Use when work can run in parallel, should preserve main context, or must be isolated into read-only or patch-only worker workspaces.
---

# Subagent Broker

Use this skill when a task can be split into independent subagent jobs.

Prefer this skill for:
- codebase exploration
- test gap analysis
- parallel review
- isolated patch generation
- migration planning
- comparing multiple implementation options
- using cheaper models for bounded subtasks

Do not use this skill for:
- tiny single-step edits
- tasks requiring shared long-running context
- tasks requiring direct writes to the main workspace
- secrets or credential inspection

## Workflow

1. Create a task packet JSON file. Start from `templates/task_packet.example.json` when useful.
2. Prefer `read_only` mode.
3. Use `patch_only` mode only when a subagent should propose changes.
4. Give each agent one cohesive deliverable. Split unrelated formats, backends, or applications into separate agents or runs.
5. For Claude Code, prefer the default `bounded` policy and list each required Bash pattern in `allowed_tools`. Use `unattended` only as an explicit broad-permission escape hatch.
6. Run:

```bash
python .agents/skills/subagent-broker/scripts/subagent_runner.py run tasks.json --wait
```

7. Inspect progress when useful:

```bash
python .agents/skills/subagent-broker/scripts/subagent_runner.py status .subagents/<run_id>
python .agents/skills/subagent-broker/scripts/subagent_runner.py cancel .subagents/<run_id>
```

8. Read:

```text
.subagents/<run_id>/summary.md
```

9. Review any generated patch manually.
10. Apply patches only after policy checks pass:

```bash
python .agents/skills/subagent-broker/scripts/merge_patches.py --check .subagents/<run_id>/<agent_id>/patch.diff
python .agents/skills/subagent-broker/scripts/merge_patches.py --apply .subagents/<run_id>/<agent_id>/patch.diff
```

The parent Codex agent is always responsible for final review and merge.

Claude Code headless jobs reject `approval_policy: default` because no interactive approval channel exists. `bounded` uses non-interactive denials, allows read/search tools, adds edit tools in `patch_only`, and requires explicit scoped Bash rules such as `Bash(python -m pytest *)`.

## Modes

- `read_only`: allow analysis only. The runner rejects jobs that modify working-tree content.
- `patch_only`: allow edits only in an isolated standalone Git repository. The runner saves `patch.diff` and checks it against path policy.

Reject `direct_write`, `shared_workspace`, `network_sandbox`, and `daemon` in this MVP.

## References

- Read `references/runner_protocol.md` for task packets, result fields, event logs, harness behavior, and extension points.
- Read `references/isolation_policy.md` before using `patch_only` or adjusting allow/deny paths.
- Read `references/examples.md` for common task packets and patch application commands.
