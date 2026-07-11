# Examples

## Fixture smoke (development only)

```json
{
  "schema_version": 3,
  "run_id": "demo-fixture",
  "agents": [
    {
      "id": "mapper",
      "goal": "Map the repository structure.",
      "harness": {
        "kind": "custom",
        "executable": "/path/to/fixture-harness.sh",
        "stream_family": "claude_stream_json"
      },
      "mode": "read_only",
      "requested_permissions": ["repo_read"]
    }
  ]
}
```

```bash
scripts/subagent-broker run tasks.json
scripts/subagent-broker status .subagents/demo-fixture
```

## Real harness smoke (use host home for login/OAuth)

Isolated `home` redirects `HOME` / `GROK_HOME` / `CLAUDE_CONFIG_DIR` / `CODEX_HOME` into a sandbox.
Real Claude / Grok / Codex sessions then ask the user to log in and often produce **no usable stream**.

For real CLI runs on a developer machine, set **`environment.home: host`**:

```json
{
  "schema_version": 3,
  "run_id": "real-smoke",
  "agents": [
    {
      "id": "worker",
      "goal": "Reply with exactly: pong. Do not use tools.",
      "harness": { "kind": "grok_build" },
      "mode": "read_only",
      "requested_permissions": ["repo_read"],
      "environment": {
        "home": "host",
        "allowed_env": ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "XAI_API_KEY"]
      }
    }
  ]
}
```

Default for automation remains **`home: isolated`** (reproducible, no host secrets). The in-process `fake` harness is compiled only with the `dev-harness` Cargo feature and is not accepted by release binaries.

## Claude read-only review with identity required

See `templates/task.v3.example.json`.

## Patch-only agent

```json
{
  "schema_version": 3,
  "run_id": "patch-demo",
  "agents": [
    {
      "id": "fixer",
      "goal": "Add a unit test for path validation.",
      "harness": { "kind": "claude_code", "model": "claude-sonnet-4-20250514" },
      "mode": "patch_only",
      "requested_permissions": ["repo_read", "patch"],
      "allowed_paths": ["src/**", "tests/**"],
      "deny_paths": [".env*", "secrets/**"],
      "environment": { "home": "host" },
      "patch_policy": { "allow_deletes": false, "allow_binary_changes": false }
    }
  ]
}
```

```bash
scripts/subagent-broker run tasks.json
scripts/subagent-broker patch check .subagents/patch-demo/fixer/patch.diff
# review, then:
scripts/subagent-broker patch apply .subagents/patch-demo/fixer/patch.diff
```

## Doctor

```bash
scripts/subagent-broker doctor
```
