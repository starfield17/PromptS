# Examples

## Read-only Repo Exploration

```json
{
  "run_id": "repo-map",
  "defaults": {"timeout_sec": 600, "mode": "read_only", "harness": "fake"},
  "agents": [
    {
      "id": "map",
      "goal": "Map the repository structure and identify likely test locations.",
      "allowed_paths": ["**"],
      "deny_paths": [".env*", ".git/**", "secrets/**"],
      "return": ["summary", "file_refs", "recommendations"]
    }
  ]
}
```

Run:

```bash
python .agents/skills/subagent-broker/scripts/subagent_runner.py run tasks.json --wait
```

## Parallel Review

```json
{
  "run_id": "parallel-review",
  "defaults": {"timeout_sec": 600, "mode": "read_only", "harness": "fake"},
  "agents": [
    {"id": "api-review", "goal": "Review API error handling.", "allowed_paths": ["src/api/**"], "return": ["summary", "risks"]},
    {"id": "test-review", "goal": "Review test coverage gaps.", "allowed_paths": ["tests/**"], "return": ["summary", "recommendations"]}
  ]
}
```

## Patch-only Test Generation

```json
{
  "run_id": "test-patch",
  "defaults": {"timeout_sec": 900, "harness": "fake"},
  "agents": [
    {
      "id": "add-tests",
      "mode": "patch_only",
      "goal": "Add missing tests for edge cases.",
      "allowed_paths": ["tests/**"],
      "deny_paths": [".env*", ".git/**", "secrets/**"],
      "return": ["summary", "patch", "tests_run", "risks"],
      "fake_patch": {"path": "tests/test_generated.py", "content": "def test_generated():\n    assert True\n"}
    }
  ]
}
```

## OpenCode Adapter Task

```json
{
  "run_id": "opencode-review",
  "defaults": {"timeout_sec": 900, "mode": "read_only", "harness": "opencode"},
  "agents": [
    {
      "id": "review",
      "model": "deepseek/deepseek-chat",
      "goal": "Review auth code for obvious correctness risks.",
      "allowed_paths": ["src/auth/**", "tests/auth/**"],
      "deny_paths": [".env*", ".git/**", "secrets/**"],
      "return": ["summary", "risks", "recommendations"]
    }
  ]
}
```

## Claude Code Adapter Task

```json
{
  "run_id": "claude-review",
  "defaults": {"timeout_sec": 900, "mode": "read_only", "harness": "claude-code"},
  "agents": [
    {
      "id": "review",
      "home_policy": "host",
      "goal": "Review the test suite organization and recommend focused improvements.",
      "allowed_paths": ["tests/**"],
      "deny_paths": [".env*", ".git/**", "secrets/**"],
      "return": ["summary", "recommendations", "risks"]
    }
  ]
}
```

Claude defaults to `bounded`; this read-only task needs no Bash permission. For a patch task that runs tests, set `mode` to `patch_only` and add only the required command family, for example `"allowed_tools": ["Bash(python -m pytest *)"]`. Exact flag sequences are brittle because Claude may choose equivalent flags or ordering.

## Grok Build Read-only Review

```json
{
  "run_id": "grok-review",
  "defaults": {
    "timeout_sec": 900,
    "mode": "read_only",
    "harness": "grok-build"
  },
  "agents": [
    {
      "id": "review",
      "home_policy": "host",
      "goal": "Review the API implementation for correctness risks without changing files.",
      "allowed_paths": ["src/api/**", "tests/api/**"],
      "return": ["summary", "risks", "recommendations"]
    }
  ]
}
```

`home_policy: "host"` reuses the local Grok login and configuration. Omit it when using environment-based authentication and an isolated Grok home.

## Grok Build Patch Task

```json
{
  "run_id": "grok-tests",
  "defaults": {
    "timeout_sec": 900,
    "mode": "patch_only",
    "harness": "grok-build",
    "approval_policy": "unattended"
  },
  "agents": [
    {
      "id": "add-tests",
      "home_policy": "host",
      "goal": "Add focused regression tests for the reported parser bug.",
      "allowed_paths": ["tests/parser/**"],
      "deny_paths": ["tests/fixtures/private/**"],
      "return": ["summary", "patch", "tests_run", "risks"]
    }
  ]
}
```

`unattended` maps to Grok `--always-approve`; this patch task uses it so tool approvals cannot stall the headless run. Prefer `default` whenever the task can complete without broad vendor approval. The broker still verifies paths, patch bytes, and the source baseline before application.

## Checking and Applying a Patch

```bash
python .agents/skills/subagent-broker/scripts/merge_patches.py --check .subagents/<run_id>/<agent_id>/patch.diff
python .agents/skills/subagent-broker/scripts/merge_patches.py --apply .subagents/<run_id>/<agent_id>/patch.diff
```

Run these commands from the original source repository. The apply command requires a completed result, passed policy, matching artifact hashes, the recorded source root, and an unchanged source baseline. It does not stage or commit.
