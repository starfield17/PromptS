# Runner Protocol

Use JSON task packets as the canonical input. YAML is optional and requires PyYAML.

## Task Packet

Top-level fields:

- `run_id`: safe identifier used under `.subagents/<run_id>/`; `.` and `..` are rejected.
- `defaults`: optional values inherited by each agent.
- `failure_policy`: `collect_all` by default or `fail_fast`.
- `success_policy`: `require_all` by default or `require_any`; controls the run exit code without hiding `partial_success`.
- `agents`: non-empty list of bounded jobs.

Agent fields:

- `id`: safe identifier unique within the run.
- `goal`: the only objective the subagent should work on.
- `harness`: `fake`, `opencode`, `claude-code`, `codex-cli`, or `grok-build`.
- `mode`: `read_only` or `patch_only`.
- `approval_policy`: `default`, Claude-only `bounded`, or `unattended`. Claude defaults to `bounded` and rejects `default` because headless jobs cannot answer approval prompts. Other harnesses default to `default`.
- `allowed_tools`: Claude `bounded` additions using native rules. Bare `Bash` and `Bash(*)` are rejected; use scoped rules such as `Bash(python -m pytest *)`.
- `model`, `agent`: optional harness model and agent values.
- `source_root`: relative directory under the invocation cwd; default `.`. Use it to avoid copying a non-Git multi-project parent.
- `allowed_paths`: repo-root-relative glob patterns a patch may modify.
- `deny_paths`: repo-root-relative glob patterns that always fail policy.
- `return`: expected output categories included in the generated prompt.
- `timeout_sec`: positive integer timeout per agent.
- `idle_timeout_sec`: seconds without stdout, stderr, or a stream event before terminating the harness; default 180.
- `max_output_bytes`: positive integer cap per stdout/stderr stream; exceeding it terminates the job with `output_limit`.
- `max_files_changed`: patch file-count limit; default 50.
- `max_workspace_files`, `max_workspace_bytes`: non-Git copy limits; defaults 25,000 files and 1 GiB.
- `allow_binary_changes`, `allow_deletes`: default false.
- `inherit_env`: default true for CLI compatibility.
- `home_policy`: `isolated` by default; choose `host` explicitly to reuse user auth/config.
- `session_persistence`: default false; currently controls Claude Code session persistence.
- `dangerously_skip_permissions`: legacy Claude-only alias for `approval_policy: unattended`.
- `dangerously_bypass_approvals_and_sandbox`: Codex-only escape hatch. It is never implied by ordinary `unattended` because it also disables Codex sandboxing.

In Claude `bounded` mode, allow `Read`, `Glob`, and `Grep`; add `Edit` and `Write` for `patch_only`. Deny every unlisted tool without prompting. `unattended` remains a broad vendor bypass and should be explicit.

Treat a non-empty Claude `permission_denials` result as a failed agent even when Claude reports `is_error: false`. Persist only denied tool names and IDs in `harness_metadata`, never the denied command input. Prefer command-family rules such as `Bash(python -m unittest *)` over flags that the model may legitimately reorder.

Booleans and integers are type-checked. Conflicting approval fields fail validation. The two dangerous compatibility fields are also rejected on the wrong harness.

Path globs are segment-aware: `*` matches one segment and `**` crosses directories. Default denied paths include nested `.env*`, `.git`, `.subagents`, and `secrets` paths.

## Result Contract

Each agent writes `.subagents/<run_id>/<agent_id>/result.json` with:

- identity: `run_id`, `agent_id`, `status`, `mode`, `harness`, `model`, `approval_policy`
- workspace: `source_root`, `source_repo_root`, `repo_subdir`, `baseline_commit`, `baseline_manifest_path`, `baseline_manifest_sha256`
- response: `summary`, `files_read`, `files_changed`, `tests_run`, `risks`, `recommendations`
- patch: `patch_path`, `patch_sha256`, `policy`
- diagnostics: `error`, `harness_metadata`, `runtime_path`, `started_at`, `ended_at`, `duration_sec`, `log_path`

`harness_metadata` contains only adapter-allowlisted fields: Grok correlation IDs, Codex CLI's thread ID, or Claude session/duration/turn/cost values. It never contains prompts or environment values.

Terminal agent statuses include `completed`, `failed`, `policy_failed`, `timeout`, `idle_timeout`, `output_limit`, and `cancelled`. Run-level statuses include `completed`, `partial_success`, `failed`, and `cancelled`.

Create a patch artifact only for a completed agent with at least one policy-compliant change. Failed, cancelled, timed-out, or successful no-change jobs leave `patch_path`, `patch_sha256`, and `policy` null.

Patch application requires the recorded original source repository, a completed result, passed policy, matching patch and baseline-manifest hashes, and unchanged raw visible baseline state for every touched path.

## Event Log

Each agent writes JSON Lines to `events.jsonl`. Event families include `started`, `command`, `tool_started`, `tool_finished`, `harness_result`, `heartbeat`, `stdout`, `stderr`, `patch_created`, `policy_check`, `descendants_terminated`, `completed`, `failed`, and `cancelled`.

Append stdout/stderr while the harness runs. Track PID/PGID, last activity, current tool, tool count, and byte counts in `runtime.json`. Command events redact generated prompts and goals; tool events omit tool inputs and outputs. Full prompts remain in `prompt.txt`; environments and credentials are never logged.

`status` merges queued run-level records with agent `result.json` and `runtime.json`. `cancel` persists a cancellation marker, verifies the recorded Linux process start token, sends TERM then KILL to each active process group, and prevents queued agents from launching.

## Harness Mapping

- `opencode`: `opencode run [--model ...] [--agent ...] [--auto] <prompt>`.
- `claude-code`: `claude --output-format stream-json --verbose [--permission-mode dontAsk --tools ... --allowedTools ... | --dangerously-skip-permissions] [--no-session-persistence] -p <prompt>`.
- `codex-cli`: `codex exec --json --ephemeral --sandbox <read-only|workspace-write> [--model ...] <prompt>`. The explicit dangerous escape hatch replaces the native sandbox flag.
- `grok-build`: `grok --output-format streaming-json --no-plan --no-subagents --no-leader --no-ask-user --no-memory --no-auto-update --sandbox <read-only|workspace> --cwd <repo> [--model ...] [--agent ...] [--always-approve] --prompt-file <file>`.

Grok Build support is verified against `grok 0.2.93`. Newer versions are attempted rather than version-blocked; incompatible output or flags fail with explicit adapter/command errors. Its streaming decoder accepts unknown event types but requires response text and an `end` event.

Treat Grok `Cancelled`/`Canceled` stop reasons as terminal failures. The broker does not retry them because a prior attempt may already have performed tool actions. For repeated cancellations, use `harness_metadata` and the raw logs to correlate the Grok session/request, reproduce the logged command with a minimal prompt, and then investigate CLI, API, account, or model routing.

All Git harnesses start at the standalone repository root so sandbox write scope matches repo-root-relative path policy. The original invocation subdirectory is included in the prompt and result.

Missing commands fail gracefully and still produce `result.json`.

For non-Git `read_only`, preflight the sanitized source before copying it. Stop at the configured file/byte limit and recommend a narrower `source_root`; do not partially copy an oversized workspace.

## Harness Configuration

Override a registered adapter command with `config.json` in the skill root:

```json
{
  "harnesses": {
    "opencode": {
      "argv": ["opencode", "run", "--model", "{model}", "{prompt}"]
    }
  }
}
```

Supported placeholders are `{model}`, `{agent}`, `{goal}`, `{prompt}`, `{prompt_file}`, `{cwd}`, `{run_dir}`, `{agent_dir}`, `{mode}`, and `{approval_policy}`. A custom argv is a complete override and must preserve the registered adapter's expected output format.

Add a harness by registering one `HarnessSpec` in `scripts/harness_adapters.py` with its argv builder and output decoder. Keep the normalized task/result contract stable and map vendor flag changes inside the adapter.
