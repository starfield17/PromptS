# Isolation Policy

The broker isolates subagents by context, environment, and file outputs. It is not an OS sandbox.

## Read-only Mode

Use `read_only` for exploration, review, test gap analysis, and planning.

- In a Git repository, the runner uses an isolated detached worktree when possible.
- Outside Git, the runner snapshots non-broker files before and after the harness run.
- Any file modification makes the job fail.
- Changes from read-only jobs are never applied.

## Patch-only Mode

Use `patch_only` only when a subagent should propose edits.

- The runner requires a Git repository.
- It creates `.subagents/<run_id>/<agent_id>/worktree`.
- It runs the harness inside that worktree.
- It saves `git diff --binary` as `patch.diff`.
- It runs `policy_check.py`.
- It never applies the patch automatically.

## Path Policy

Every changed path must match at least one `allowed_paths` pattern and no `deny_paths` pattern.

Fail closed:

- ambiguous paths fail
- absolute paths fail
- parent-directory paths fail
- denied paths fail even if also allowed
- binary changes fail unless `allow_binary_changes` is true
- deletions fail unless `allow_deletes` is true

## Context Isolation

Subagents receive only the generated prompt. Do not pass parent conversation history, other agents' transcripts, unrelated task packets, or result files.

## Environment Isolation

The runner sets:

```text
SUBAGENT_RUN_ID
SUBAGENT_AGENT_ID
SUBAGENT_MODE
SUBAGENT_DIR
HOME=<agent_dir>/home
TMPDIR=<agent_dir>/tmp
XDG_CACHE_HOME=<agent_dir>/cache
```

`inherit_env` defaults to true for practical CLI compatibility. This can expose credentials through normal process inheritance. Do not delegate tasks that require inspecting secrets. Future versions should support explicit environment allowlists.

Harnesses that store authentication only under the user's normal home directory may fail under isolated `HOME`. Prefer environment-based credentials or an explicit harness configuration when a CLI supports it.

Set `home_policy` to `host` only for a task that must reuse the inherited user home. This preserves the host `HOME` while still isolating `TMPDIR`, `XDG_CACHE_HOME`, and broker output paths. It also exposes host CLI config, auth state, history, and plugins to that harness process, so keep it opt-in and task-specific.

For Claude Code, `dangerously_skip_permissions` maps to Claude Code's permission-bypass flag. It can avoid interactive permission prompts, but it does not solve authentication; use `home_policy: "host"` or an API-key/settings-based auth path for that.

## Limitations

The broker does not provide seccomp, AppArmor, container isolation, network blocking, or direct multi-agent context sharing. Treat every external harness as code that can run local commands under the current user's authority.
