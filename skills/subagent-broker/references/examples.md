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
      "dangerously_skip_permissions": true,
      "goal": "Review the test suite organization and recommend focused improvements.",
      "allowed_paths": ["tests/**"],
      "deny_paths": [".env*", ".git/**", "secrets/**"],
      "return": ["summary", "recommendations", "risks"]
    }
  ]
}
```

## Checking and Applying a Patch

```bash
python .agents/skills/subagent-broker/scripts/merge_patches.py --check .subagents/<run_id>/<agent_id>/patch.diff
python .agents/skills/subagent-broker/scripts/merge_patches.py --apply .subagents/<run_id>/<agent_id>/patch.diff
```

The apply command requires a passed policy result in the agent's `result.json` and does not auto-commit.
