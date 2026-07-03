# Runner Protocol

Use JSON task packets as the canonical input. YAML is optional and only works when the Python environment already provides PyYAML.

## Task Packet

Top-level fields:

- `run_id`: safe identifier used under `.subagents/<run_id>/`.
- `defaults`: optional values inherited by each agent.
- `agents`: list of bounded jobs.

Agent fields:

- `id`: safe identifier used under the run directory.
- `goal`: the only objective the subagent should work on.
- `harness`: `fake`, `opencode`, `claude-code`, or `codex-cli`.
- `mode`: `read_only` or `patch_only`.
- `model`: optional harness model value.
- `agent`: optional harness-specific agent name.
- `allowed_paths`: glob patterns for paths that a patch may modify.
- `deny_paths`: glob patterns that always fail policy.
- `return`: expected output categories for the prompt.
- `timeout_sec`: per-agent timeout.
- `max_output_bytes`: stdout/stderr capture cap.
- `allow_binary_changes`: default false.
- `allow_deletes`: default false.
- `inherit_env`: default true for CLI compatibility.
- `home_policy`: `isolated` by default. Use `host` only when a harness must read authentication or settings from the inherited user home.
- `dangerously_skip_permissions`: default false. For `claude-code`, add Claude Code's permission-bypass flag when true.
- `session_persistence`: default false. For `claude-code`, preserve session files only when true.

The runner always adds conservative denied paths such as `.env*`, `.git/**`, `.subagents/**`, and `secrets/**`.

## Result Fields

Each agent writes `.subagents/<run_id>/<agent_id>/result.json` with:

- `run_id`, `agent_id`, `status`, `mode`, `harness`, `model`
- `summary`, `files_read`, `files_changed`
- `patch_path` for patch-producing jobs, otherwise null
- `tests_run`, `risks`, `recommendations`
- `policy` for patch-only policy results
- `error`, `started_at`, `ended_at`, `duration_sec`, `log_path`

Run-level `.subagents/<run_id>/result.json` aggregates agent results and status.

## Event Log

Each agent writes JSON Lines to `events.jsonl`. Required event families include:

- `started`
- `command`
- `stdout`
- `stderr`
- `patch_created`
- `policy_check`
- `completed`
- `failed`

Events should be useful for inspection without dumping secrets or full environments.

## Harnesses

- `fake`: deterministic test harness. It can return `fake_response`, fail with `fake_fail: true`, or create a patch with `fake_patch`.
- `opencode`: default public CLI shape is `opencode run [--model <model>] [--agent <agent>] <prompt>`.
- `claude-code`: default public CLI shape is `claude [--model <model>] [--agent <agent>] [--dangerously-skip-permissions] [--no-session-persistence] -p <prompt>`.
- `codex-cli`: default public CLI shape is `codex exec --json [--model <model>] <prompt>`.

Missing commands fail gracefully and still produce `result.json`.

Claude Code OAuth or keychain login commonly lives under the normal user home. If a manual `claude` command works but the broker reports `Not logged in`, set `home_policy` to `host` for that Claude task. `dangerously_skip_permissions` only bypasses Claude Code permission prompts; it does not authenticate Claude Code.

## Harness Configuration

Override defaults with `.agents/skills/subagent-broker/config.json`:

```json
{
  "harnesses": {
    "opencode": {
      "argv": ["opencode", "run", "--model", "{model}", "--agent", "{agent}", "{prompt}"]
    },
    "claude-code": {
      "argv": ["claude", "--dangerously-skip-permissions", "-p", "{prompt}"]
    },
    "codex-cli": {
      "argv": ["codex", "exec", "--json", "--model", "{model}", "{prompt}"]
    }
  }
}
```

Supported placeholders are `{model}`, `{agent}`, `{goal}`, `{prompt}`, `{prompt_file}`, `{cwd}`, `{run_dir}`, and `{agent_dir}`.

## Adding a Harness

Add a new harness by extending the adapter dispatch in `scripts/subagent_runner.py`, defining a default argv builder, and documenting any task fields the harness needs. Keep the normalized result contract unchanged.
