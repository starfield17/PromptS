---
name: subagent-broker
description: Delegate bounded coding, review, exploration, testing, or patch-generation tasks to external harnesses such as Grok Build, Claude Code, OpenCode, Codex CLI, or cheap model workers. Use when work can run in parallel, should preserve main context, or must be isolated into read-only or patch-only worker workspaces.
---

# Subagent Broker (V3.1)

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

1. Create a **schema_version 3** task packet JSON. Start from `templates/task.v3.example.json`.
2. Prefer `read_only` mode. Use `patch_only` only when a subagent should propose changes.
3. Give each agent one cohesive deliverable.
4. Declare closed **`requested_permissions`**: `repo_read`, `python_inspect`, `python_test`, `patch` (`capabilities` is a compatibility alias).
   - Capabilities configure vendor tool permissions; they are **not** an OS security boundary.
   - Legacy `allowed_tools` is **not** supported in V3.
5. Run (always blocks until the whole run is terminal):

```bash
path/to/subagent-broker/scripts/subagent-broker run tasks.json
```

There is no `--wait` or `--detach`. Foreground cancel is SIGINT (exit 130).
Each `run_id` is single-use; choose a new ID instead of reusing an existing run directory.

6. **Yield-on-session warning:** if your command tool returns a session/cell id or “still running”, that is **not** CLI exit. Keep waiting on the same execution session.

7. Optional live view:

```bash
path/to/subagent-broker/scripts/subagent-broker status .subagents/<run_id>
```

8. Read the unified summary (always written for ordinary terminal outcomes):

```text
.subagents/<run_id>/summary.md
.subagents/<run_id>/result.json
```

9. Review any generated patch manually. Patches are emitted **only** for `outcome=success` after identity, denial, and mechanical policy gates — never for `blocked`, failed, cancelled, or timeout.
10. Apply patches only after review:

```bash
path/to/subagent-broker/scripts/subagent-broker patch check .subagents/<run_id>/<agent_id>/patch.diff
path/to/subagent-broker/scripts/subagent-broker patch apply .subagents/<run_id>/<agent_id>/patch.diff
```

The parent agent is always responsible for final review and merge. Agent self-reported tests are labeled `self_reported`, not verified truth.

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | run outcome `success` (all agents success); or patch check/apply success |
| 1 | run finished non-success (`failed` / `blocked` / `cancelled`) |
| 2 | task packet, CLI, or environment error (run did not start) |
| 130 | foreground run cancelled by SIGINT (processes reaped, state persisted) |

## Identity and environment

- Results record **requested** harness/model, **executable** path/realpath/version/trust, and stream-**observed** (claimed) provider/model.
- With `"identity": {"required": true, ...}`, missing or mismatched observed identity → `blocked` / `provider_mismatch` and no patch.
- Stream identity is **claimed/observed**, not cryptographic proof. Prefer `expected_executable_realpath` / `expected_executable_sha256` for stronger binding.
- Default environment is **minimal isolated** HOME/TMP/XDG (and harness config dirs). Credentials pass only via named `environment.allowed_env` (values never recorded).
- **Real Claude / Grok / Codex on a logged-in machine:** set `"environment": {"home": "host"}`. Isolated home forces re-login and often yields empty/no stream.
- `"environment": {"home": "host"}` is explicit opt-in and is marked **host configuration exposed / reproducibility: reduced** in status and summary. Host mode preserves host `HOME`, XDG_*, `GROK_HOME`, `CODEX_HOME`, `CLAUDE_CONFIG_DIR` (values never logged).

## Modes

- `read_only`: analysis only; runner fails the job if the isolated copy is modified. Does **not** claim host absolute-path read confinement.
- `patch_only`: edits in an isolated standalone Git repo; runner writes `patch.diff` only after all gates pass.
- OpenCode is currently a limited `read_only` adapter; V3 rejects OpenCode `patch_only`.

## Permission denials

Any vendor permission denial is visible mid-run (`permission_denials` + tool name only — no command text) and forces terminal `blocked` / `permission_denied` even if the vendor result claims success. `harness_completed` may still be true.

`stdout.log` / `stderr.log` contain redaction markers rather than vendor payloads; byte totals and truncation diagnostics remain in `result.json`.

## Diagnostics

```bash
path/to/subagent-broker/scripts/subagent-broker doctor
```

Lists stock harness realpaths/versions, platform support, and Git version. Does not start agent sessions.

```bash
path/to/subagent-broker/scripts/subagent-broker validate-skill path/to/subagent-broker
path/to/subagent-broker/scripts/release_metadata.sh
```

`validate-skill` checks V3 layout and requires the executable launcher plus the current-platform packaged binary. Release metadata prints toolchain, Cargo.lock hash, launcher/binary SHA-256 (does not install/replace the skill).

## Platform


V3 MVP: **Linux** x86_64 / aarch64. Non-Linux returns a clear unsupported-platform error. Release packages contain `bin/linux-x86_64/`, `bin/linux-aarch64/`, and an architecture-selecting `scripts/subagent-broker` launcher.

## References

- `references/protocol.md` — packet/result fields, streaming, identity, summary contract
- `references/isolation.md` — workspace and patch policy
- `references/examples.md` — sample packets and merge commands

## Implementation note

The broker is a Rust binary under `bin/` selected by the `scripts/subagent-broker` launcher (built from `rust/`). The in-process fake harness is only compiled with the `dev-harness` Cargo feature and is not accepted by production release binaries. There is no Python V2 runtime in this skill tree.
