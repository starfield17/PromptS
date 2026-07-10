# Runner Protocol

Use JSON task packets as the canonical input. YAML is optional and requires PyYAML.

## Task Packet

Top-level fields:

- `run_id`: safe identifier used under `.subagents/<run_id>/`; `.` and `..` are rejected.
- `defaults`: optional values inherited by each agent.
- `agents`: non-empty list of bounded jobs.

Agent fields:

- `id`: safe identifier unique within the run.
- `goal`: the only objective the subagent should work on.
- `harness`: `fake`, `opencode`, `claude-code`, `codex-cli`, or `grok-build`.
- `mode`: `read_only` or `patch_only`.
- `approval_policy`: `default` or `unattended`; default `default`. `unattended` is valid in either mode and maps to the vendor's automatic approval flag, so use it only when the task cannot proceed with default approvals.
- `model`, `agent`: optional harness model and agent values.
- `allowed_paths`: repo-root-relative glob patterns a patch may modify.
- `deny_paths`: repo-root-relative glob patterns that always fail policy.
- `return`: expected output categories included in the generated prompt.
- `timeout_sec`: positive integer timeout per agent.
- `max_output_bytes`: positive integer cap per stdout/stderr stream; exceeding it terminates the job with `output_limit`.
- `allow_binary_changes`, `allow_deletes`: default false.
- `inherit_env`: default true for CLI compatibility.
- `home_policy`: `isolated` by default; choose `host` explicitly to reuse user auth/config.
- `session_persistence`: default false; currently controls Claude Code session persistence.
- `dangerously_skip_permissions`: legacy Claude-only alias for `approval_policy: unattended`.
- `dangerously_bypass_approvals_and_sandbox`: Codex-only escape hatch. It is never implied by ordinary `unattended` because it also disables Codex sandboxing.

Booleans and integers are type-checked. Conflicting approval fields fail validation. The two dangerous compatibility fields are also rejected on the wrong harness.

Path globs are segment-aware: `*` matches one segment and `**` crosses directories. Default denied paths include nested `.env*`, `.git`, `.subagents`, and `secrets` paths.

## Result Contract

Each agent writes `.subagents/<run_id>/<agent_id>/result.json` with:

- identity: `run_id`, `agent_id`, `status`, `mode`, `harness`, `model`, `approval_policy`
- workspace: `source_repo_root`, `repo_subdir`, `baseline_commit`, `baseline_manifest_path`, `baseline_manifest_sha256`
- response: `summary`, `files_read`, `files_changed`, `tests_run`, `risks`, `recommendations`
- patch: `patch_path`, `patch_sha256`, `policy`
- diagnostics: `error`, `started_at`, `ended_at`, `duration_sec`, `log_path`

Terminal agent statuses include `completed`, `failed`, `policy_failed`, `timeout`, `output_limit`, and `cancelled`. Run-level results aggregate the agent results.

Patch application requires the recorded original source repository, a completed result, passed policy, matching patch and baseline-manifest hashes, and unchanged raw visible baseline state for every touched path.

## Event Log

Each agent writes JSON Lines to `events.jsonl`. Event families include `started`, `command`, `stdout`, `stderr`, `patch_created`, `policy_check`, `descendants_terminated`, `completed`, `failed`, and `cancelled`.

Command events redact generated prompts and goals. Full prompts remain in `prompt.txt`; environments and credentials are never logged.

## Harness Mapping

- `opencode`: `opencode run [--model ...] [--agent ...] [--auto] <prompt>`.
- `claude-code`: `claude [--model ...] [--agent ...] [--dangerously-skip-permissions] [--no-session-persistence] -p <prompt>`.
- `codex-cli`: `codex exec --json --ephemeral --sandbox <read-only|workspace-write> [--model ...] <prompt>`. The explicit dangerous escape hatch replaces the native sandbox flag.
- `grok-build`: `grok --output-format streaming-json --no-plan --no-subagents --no-leader --no-ask-user --no-memory --no-auto-update --sandbox <read-only|workspace> --cwd <repo> [--model ...] [--agent ...] [--always-approve] --prompt-file <file>`.

Grok Build support is verified against `grok 0.2.93`. Newer versions are attempted rather than version-blocked; incompatible output or flags fail with explicit adapter/command errors. Its streaming decoder accepts unknown event types but requires response text and an `end` event.

All Git harnesses start at the standalone repository root so sandbox write scope matches repo-root-relative path policy. The original invocation subdirectory is included in the prompt and result.

Missing commands fail gracefully and still produce `result.json`.

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
