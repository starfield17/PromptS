#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN="${SUBAGENT_BROKER_BIN:-$ROOT/scripts/subagent-broker}"
FIXTURE="${SUBAGENT_BROKER_PATCH_FIXTURE:-$ROOT/tests/fixtures/patch-fixture-harness.sh}"
if [[ ! -x "$BIN" || ! -x "$FIXTURE" ]]; then
  echo "missing patch smoke executable" >&2
  exit 2
fi
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
echo baseline > "$TMP/README.md"
git -C "$TMP" init -q
git -C "$TMP" config user.email smoke@example.invalid
git -C "$TMP" config user.name smoke
git -C "$TMP" add README.md
git -C "$TMP" commit -q -m baseline
cat > "$TMP/tasks.json" <<JSON
{
  "schema_version": 3,
  "run_id": "patch-smoke-001",
  "agents": [{
    "id": "worker",
    "goal": "create the requested smoke file",
    "harness": {"kind": "custom", "executable": "$FIXTURE", "stream_family": "claude_stream_json"},
    "mode": "patch_only",
    "requested_permissions": ["repo_read", "patch"],
    "allowed_paths": ["smoke-created.txt"]
  }]
}
JSON
"$BIN" run "$TMP/tasks.json" --cwd "$TMP" >/dev/null
PATCH="$TMP/.subagents/patch-smoke-001/worker/patch.diff"
test -s "$PATCH"
"$BIN" patch check "$PATCH" >/dev/null
echo "patch smoke ok"
