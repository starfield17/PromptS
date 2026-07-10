# Isolation Policy

The broker isolates context, working copies, process output, and patch artifacts. It is not a universal OS sandbox.

## Working Copy

For a Git repository, each agent receives a standalone one-commit repository under `.subagents/<run_id>/<agent_id>/worktree`:

- Build a temporary index from `HEAD` plus the current staged, unstaged, deleted, and non-ignored untracked state.
- Exclude effective deny paths before export.
- Write dirty blobs to an agent-local temporary object directory, never the source repository object database.
- Export exact visible bytes, symlink targets, and executable modes into a fresh repository.
- Record a raw baseline manifest and root commit. For patch tasks, also save a Git bundle outside the working copy and retain its SHA-256 in runner memory.
- Delete temporary index/object data before launching the harness.
- Reject source repositories containing Git submodules rather than silently changing gitlinks.

This makes the agent patch relative to the user's visible starting state without stashing, committing, or changing the source index. Ignored untracked files, empty directories, and dirty submodule contents are not mirrored.

For non-Git `read_only` tasks, copy the source tree into an isolated workspace while excluding deny paths. `patch_only` still requires Git.

Output root, run, and agent paths reject dot-segment IDs and pre-existing symlinks before cleanup. Artifact writers use atomic replacement or no-follow append operations so leaf symlinks cannot redirect broker output.

## Read-only Mode

- Run against the isolated copy.
- Snapshot working-tree file type, Git-relevant mode, raw content, and symlink targets before and after execution.
- Fail if any working-tree content changes, including ignored files and executable-bit changes. Disposable `.git` metadata is excluded.
- Never copy changes back to the source workspace.

Grok additionally receives its built-in `read-only` sandbox. That profile blocks project writes but can read outside the workspace. Other harnesses may provide their own sandbox behavior; the broker's isolated copy and post-run verification remain mandatory.

## Patch-only Mode

- Verify the working-copy directory identity, then discard harness-controlled `.git` metadata and rebuild it from the in-memory-hashed baseline bundle before the first post-harness Git command.
- Compare the final standalone working tree against the immutable recorded baseline, including the visible content from agent-created commits.
- Preflight changed paths from NUL-delimited Git output before reading patch content.
- Reset the standalone index to the baseline and stage only the exact prechecked literal paths.
- Re-check authoritative staged and current paths before persisting `git diff --cached --binary --no-renames` bytes.
- Detect binary changes and deletions from structured Git metadata.
- Never apply a patch automatically.

Grok receives its `workspace` sandbox, which limits writes to the standalone repo, Grok home, and temporary directories when supported by the host kernel.

## Applying Patches

`merge_patches.py`:

1. Requires invocation from the recorded original source repository and resolves its Git root even when invoked in a subdirectory.
2. Requires `completed` status and passed policy.
3. Verifies patch and raw baseline-manifest SHA-256 values.
4. Confirms every touched source path still matches its original visible mode/content hash.
5. Runs `git apply --check` and plain `git apply` with the same in-memory patch bytes.

It does not use `--3way`, stage files, commit, or alter unrelated staged/unstaged state. Moving the repository after a run invalidates the recorded source-root check and requires regenerating the patch artifact.

## Environment

The runner always sets `SUBAGENT_RUN_ID`, `SUBAGENT_AGENT_ID`, `SUBAGENT_MODE`, `SUBAGENT_DIR`, `TMPDIR`, `XDG_CACHE_HOME`, and `PWD`.

With default `home_policy: isolated`, it also redirects `HOME`, `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, `GROK_HOME`, `CODEX_HOME`, and `CLAUDE_CONFIG_DIR` under the agent directory. This prevents inherited vendor-home overrides from bypassing isolation, but tools may then require environment-based credentials.

With `home_policy: host`, preserve host HOME and vendor overrides so a harness can reuse local login/config. This exposes user auth, settings, plugins, histories, and session storage and must remain task-specific opt-in. Grok commonly needs host policy for `~/.grok/auth.json`; `--no-memory` does not prevent its fresh session record.

`inherit_env` defaults true for compatibility and may expose credential variables. Do not delegate secret inspection.

## Process Lifecycle

Capture stdout/stderr incrementally with a hard per-stream limit. Timeout, output overflow, cancellation, or pipe-drain failure terminates the saved process group with TERM then KILL. A completed leader's remaining same-group descendants are also terminated.

Processes that deliberately create a new session or double-fork can escape process-group cleanup. Strong lifecycle containment requires cgroups, containers, or platform Job Objects.

## Limitations

- Built-in Grok sandbox profiles may warn and fall back when required kernel features are unavailable; custom deny profiles have different failure behavior. Inspect stderr and do not treat the flag alone as a guaranteed boundary.
- Except where a harness provides effective kernel restrictions, an external process may still address source files by absolute path. Missing deny paths in the standalone copy and prompt rules reduce exposure but do not provide universal read confinement.
- The broker does not provide seccomp/AppArmor configuration for every harness, container isolation, universal network blocking, environment allowlists, or direct cross-agent context sharing.
