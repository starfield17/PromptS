# Isolation and patch policy

## Workspace

- Each agent gets a standalone Git repository mirroring visible source state (tracked + unstaged + non-ignored untracked).
- Source repo index/objects are never modified.
- Baseline commit + manifest SHA-256 are recorded under the agent directory.
- After harness completion, changes are measured against the trusted baseline.
- Harness-controlled `.git` metadata is discarded; an audit repository is rebuilt from the external baseline bundle before diffing.
- Submodules are rejected until explicit semantics exist.
- The default isolation level is `copy_isolation`: absolute symlinks and relative symlinks that normalize outside the workspace are rejected both before and after the agent run.
- A future `strict` sandbox must fail explicitly when no OS sandbox backend is available; it must not silently fall back to copy isolation.
- Git is invoked with argv arrays and NUL-delimited plumbing where applicable.

## Modes

### read_only

- Isolated copy must remain clean.
- Any modification → `failed` / `read_only_write`.
- Does **not** claim OS-level host path confinement.

### patch_only

- Diff output is bounded by the task resource budget; oversized patches fail closed.
- Mechanical policy checks: allowed/denied paths, file count, deletes, binary, baseline.
- Identity gate and permission-denial gate must pass.
- Only then is `MergeablePatch` constructed and `patch.diff` written atomically.
- Never write patch then delete on failure.
- Patch and sidecar are staged together and committed with rollback on a partial rename failure.

## Path rules

- Repo-relative, `/` separators, no `.` / `..` / NUL segments.
- Default deny roots include `.git`, `.subagents`, `.env*`.
- Glob matching via `globset`.

## Environment

- Default: fresh map with PATH, locale, CA, proxy, and named `allowed_env` only.
- Always override HOME, TMPDIR, XDG_*, GROK_HOME, CODEX_HOME, CLAUDE_CONFIG_DIR, PWD.
- `home: host` is explicit opt-in; summary marks reduced reproducibility.
- Environment **values** are never logged.
- Credential variables are passed only when explicitly named in `allowed_env`, including in host-home mode.
- Vendor stdout/stderr payloads are drained but not persisted verbatim; log files contain safe markers while byte totals and truncation metadata remain authoritative in `result.json`.
