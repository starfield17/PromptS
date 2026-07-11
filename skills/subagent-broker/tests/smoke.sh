#!/usr/bin/env bash
# Optional smoke test against a built subagent-broker binary.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN="${SUBAGENT_BROKER_BIN:-$ROOT/scripts/subagent-broker}"
FIXTURE="${SUBAGENT_BROKER_FIXTURE:-$ROOT/tests/fixtures/fixture-harness.sh}"
if [[ ! -x "$BIN" ]]; then
  echo "missing binary: $BIN (build with: cargo build --release --locked -C rust)" >&2
  exit 2
fi
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
cat >"$TMP/tasks.json" <<JSON
{
  "schema_version": 3,
  "run_id": "smoke-001",
  "agents": [{
    "id": "worker",
    "goal": "smoke",
    "harness": {"kind": "custom", "executable": "$FIXTURE", "stream_family": "claude_stream_json"},
    "mode": "read_only",
    "requested_permissions": ["repo_read"],
    "limits": {
      "timeout_ms": 10000,
      "idle_timeout_ms": 5000,
      "max_workspace_files": 1000,
      "max_workspace_bytes": 10485760
    }
  }]
}
JSON
echo "smoke" >"$TMP/README.md"
git -C "$TMP" init -q
git -C "$TMP" config user.email smoke@example.invalid
git -C "$TMP" config user.name smoke
git -C "$TMP" add README.md
git -C "$TMP" commit -q -m baseline
"$BIN" doctor >/dev/null
"$BIN" run "$TMP/tasks.json" --cwd "$TMP"
test -f "$TMP/.subagents/smoke-001/result.json"
test -f "$TMP/.subagents/smoke-001/summary.md"
echo "smoke ok"
