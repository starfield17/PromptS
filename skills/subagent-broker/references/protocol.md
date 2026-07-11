# V3.1 Protocol

## Task packet

- `schema_version` must be `3`. V1/V2 packets are rejected with a migration error.
- Unknown fields are rejected (`deny_unknown_fields`).
- `run_id` / agent `id`: no empty, `.`, `..`, or path separators.
- Paths are repo-relative; no absolute paths; no `..` segments.
- `requested_permissions`: closed set `repo_read`, `python_inspect`, `python_test`, `patch` (`capabilities` remains a compatibility alias).
  - `read_only` cannot include `patch`.
  - `patch_only` requires `patch` (not auto-added).
- Harness kinds: `claude_code`, `grok_build`, `codex_cli`, `opencode`, `custom`, `fake` (test).
- Stock adapters have fixed argv; custom requires absolute `executable` and optional `stream_family` (`plain` or `claude_stream_json`).
- `opencode` is a limited read-only adapter; `patch_only` is rejected.
- `isolation` defaults to `copy_isolation`; `strict` is reserved and fails explicitly until an OS sandbox backend is available.
- Custom harnesses with required identity must constrain executable realpath or SHA-256.
- A completed `run_id` cannot be reused; choose a new identifier.
- Production release binaries do not accept `fake`; it is available only with the `dev-harness` feature for tests.

## Limits (defaults)

| Field | Default |
|-------|---------|
| timeout_ms | 1800000 |
| idle_timeout_ms | 180000 |
| term_grace_ms | 1500 |
| pipe_grace_ms | 1000 |
| max_result_bytes | 262144 |
| max_raw_log_bytes | 1048576 |
| max_event_line_bytes | 8388608 |
| max_workspace_files | 25000 |
| max_workspace_bytes | 1073741824 |
| max_files_changed | 50 |

Task-level `resources` may additionally bound `max_task_bytes`, `max_agents`, `max_total_goal_bytes`, `max_file_bytes`, `max_workspace_bytes_after_run`, `max_patch_bytes`, `max_normalized_events`, and `max_events_log_bytes`. Values must be positive; overlapping per-agent and task budgets use the smaller value.

Three budgets are independent: raw log, result text, event line framing. Manifest hashing is streaming; patch and event-log output are bounded and fail closed on overflow. Parser diagnostics record unknown, invalid, and oversized stream events; patch mode rejects unrecognized stream data.

## Result

- `schema_version: 3`
- Monotonic `revision`
- Single authority: run-level `result.json`
- `summary.md` is a pure projection of the same state
- Agent fields include requested / executable / observed identity, identity_gate, permission_denials, response, diagnostics, patch (null unless success + gates). `response.tests.verification` distinguishes `self_reported`, `broker_verified`, and `broker_failed`; broker verification records bounded byte counts and exit status.
- Agent fields also record environment home mode, allowed environment names, host exposure, and reproducibility. Values are never recorded.

## Outcomes

| Outcome | Meaning |
|---------|---------|
| success | All gates passed; only success may have patch |
| blocked | permission_denied, provider_mismatch, or patch_policy |
| failed | timeout, invalid_stream, harness_exit, etc. |
| cancelled | SIGINT or harness cancel claim |

## CLI

```text
subagent-broker run tasks.json
subagent-broker status .subagents/<run_id>
subagent-broker patch check <patch.diff>
subagent-broker patch apply <patch.diff>
subagent-broker doctor
```

Exit codes: 0 success, 1 finished non-success, 2 precondition error, 130 SIGINT.

## Validation and release

```bash
subagent-broker validate-skill /path/to/subagent-broker
scripts/release_metadata.sh
```

CI (when hosted): `.github/workflows/ci.yml` runs fmt/clippy/test/audit/deny/smoke.
