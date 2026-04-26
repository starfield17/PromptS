#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 1 ]; then
  echo "usage: run_subagent.sh <task-file> [runtime-root]" >&2
  exit 2
fi

START_DIR="$(pwd -P)"
TASK_FILE_INPUT="$1"
RUNTIME_ROOT_INPUT="${2:-${CLAUDE_SUBAGENT_ROOT:-.CC_subagent}}"
CLAUDE_BIN="${CLAUDE_BIN:-claude}"
CLAUDE_SUBAGENT_EXTRA_ARGS="${CLAUDE_SUBAGENT_EXTRA_ARGS:-}"

timestamp_utc() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

resolve_path() {
  python3 - "$1" "$2" <<'PY'
import os
import sys

path = sys.argv[1]
base = sys.argv[2]
if os.path.isabs(path):
    print(os.path.abspath(path))
else:
    print(os.path.abspath(os.path.join(base, path)))
PY
}

relative_path_if_child() {
  python3 - "$1" "$2" <<'PY'
from pathlib import Path
import sys

parent = Path(sys.argv[1]).resolve()
child = Path(sys.argv[2]).resolve()
try:
    print(child.relative_to(parent).as_posix())
except ValueError:
    print("")
PY
}

parse_role() {
  python3 - "$1" <<'PY'
from pathlib import Path
import sys

lines = Path(sys.argv[1]).read_text(encoding="utf-8").splitlines()
for index, line in enumerate(lines):
    if line.strip().lower() == "## role":
        for candidate in lines[index + 1:]:
            value = candidate.strip()
            if value:
                print(value)
                raise SystemExit(0)
        break
print("unknown")
PY
}

write_running_status() {
  python3 - "$RUN_DIR/status.json" "$TASK_ID" "$ROLE" "$WORKSPACE_MODE" "$WORKSPACE_DIR" "$STARTED_AT" <<'PY'
import json
import sys
from pathlib import Path

path, task_id, role, workspace_mode, workspace_path, started_at = sys.argv[1:]
payload = {
    "task_id": task_id,
    "role": role or "unknown",
    "state": "running",
    "status": "unknown",
    "summary": "Claude Code subagent is running.",
    "confidence": "low",
    "files_touched": [],
    "tests_run": [],
    "tests_passed": None,
    "blocking_issues": [],
    "follow_up_recommendations": [],
    "workspace_mode": workspace_mode,
    "workspace_path": workspace_path,
    "started_at": started_at,
    "finished_at": None,
    "exit_code": None,
}
Path(path).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
}

write_session_json() {
  python3 - "$RUN_DIR/session.json" "$TASK_ID" "$ROLE" "$TASK_FILE" "$SOURCE_ROOT" "$RUNTIME_ROOT" "$RUN_DIR" "$WORKSPACE_DIR" "$WORKSPACE_MODE" "$CLAUDE_BIN" "$CLAUDE_SUBAGENT_EXTRA_ARGS" "$STARTED_AT" "$1" "$2" <<'PY'
import json
import shlex
import sys
from pathlib import Path

(
    path,
    task_id,
    role,
    task_file,
    source_root,
    runtime_root,
    run_dir,
    workspace_path,
    workspace_mode,
    claude_bin,
    extra_args,
    started_at,
    finished_at,
    exit_code,
) = sys.argv[1:]

payload = {
    "task_id": task_id,
    "role": role or "unknown",
    "task_file": task_file,
    "source_root": source_root,
    "runtime_root": runtime_root,
    "run_dir": run_dir,
    "workspace_path": workspace_path,
    "workspace_mode": workspace_mode,
    "claude_bin": claude_bin,
    "extra_args": shlex.split(extra_args) if extra_args else [],
    "started_at": started_at,
    "finished_at": finished_at or None,
    "exit_code": None if exit_code == "" else int(exit_code),
}
Path(path).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
}

normalize_status() {
  python3 - "$RUN_DIR/status.json" "$RUN_DIR/changed-files.txt" "$TASK_ID" "$ROLE" "$WORKSPACE_MODE" "$WORKSPACE_DIR" "$STARTED_AT" "$FINISHED_AT" "$EXIT_CODE" <<'PY'
import json
import sys
from pathlib import Path

(
    status_path,
    changed_files_path,
    task_id,
    role,
    workspace_mode,
    workspace_path,
    started_at,
    finished_at,
    exit_code_text,
) = sys.argv[1:]

exit_code = int(exit_code_text)
path = Path(status_path)

try:
    existing = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(existing, dict):
        raise ValueError("status.json root is not an object")
except Exception:
    existing = {}

changed_files = []
changed_path = Path(changed_files_path)
if changed_path.is_file():
    changed_files = [line.strip() for line in changed_path.read_text(encoding="utf-8").splitlines() if line.strip()]

status_value = existing.get("status")
if not status_value:
    if exit_code == 124:
        status_value = "timeout"
    elif exit_code != 0:
        status_value = "failed"
    else:
        status_value = "unknown"

summary = existing.get("summary")
if not summary:
    if exit_code == 0:
        summary = "Claude Code completed, but did not provide a structured status summary."
    else:
        summary = f"Claude Code exited with code {exit_code}. Inspect events.jsonl and stderr.log."

blocking_issues = existing.get("blocking_issues")
if not isinstance(blocking_issues, list):
    blocking_issues = []
if exit_code != 0:
    message = f"Claude Code process exited with code {exit_code}."
    if message not in blocking_issues:
        blocking_issues.append(message)

confidence = existing.get("confidence") or "low"
files_touched = existing.get("files_touched")
if not isinstance(files_touched, list):
    files_touched = []
files_touched = sorted({*files_touched, *changed_files})

tests_run = existing.get("tests_run")
if not isinstance(tests_run, list):
    tests_run = []

follow_up = existing.get("follow_up_recommendations")
if not isinstance(follow_up, list):
    follow_up = []
if not follow_up and status_value in {"failed", "timeout", "unknown"}:
    follow_up.append("Inspect result.md, events.jsonl, stderr.log, and patch.diff before deciding on follow-up work.")

if exit_code != 0 and status_value == "success":
    status_value = "partial"

payload = {
    "task_id": task_id,
    "role": existing.get("role") or role or "unknown",
    "state": "finished",
    "status": status_value,
    "summary": summary,
    "confidence": confidence,
    "files_touched": files_touched,
    "tests_run": tests_run,
    "tests_passed": existing.get("tests_passed"),
    "blocking_issues": blocking_issues,
    "follow_up_recommendations": follow_up,
    "workspace_mode": existing.get("workspace_mode") or workspace_mode,
    "workspace_path": existing.get("workspace_path") or workspace_path,
    "started_at": existing.get("started_at") or started_at,
    "finished_at": finished_at,
    "exit_code": exit_code,
}

path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
}

write_default_result() {
  if [ -f "$RUN_DIR/result.md" ]; then
    return
  fi

  cat > "$RUN_DIR/result.md" <<EOF
# Result

## Summary
No structured result was written by Claude Code. Inspect \`events.jsonl\`, \`stderr.log\`, and \`patch.diff\`.

## Findings
- No wrapper-generated findings.

## Changes
- See \`changed-files.txt\` and \`patch.diff\`.

## Tests
- No structured test report was written.

## Risks
- The run may be incomplete or only partially captured.

## Recommended next steps
- Review the raw artifacts before accepting any result.

## Unresolved questions
- Why Claude Code did not produce \`result.md\`.
EOF
}

copy_source_tree() {
  local destination="$1"
  rm -rf "$destination"
  mkdir -p "$destination"

  local tar_cmd=(tar)
  tar_cmd+=(--exclude=./.git)
  if [ -n "$RUNTIME_ROOT_REL" ]; then
    tar_cmd+=("--exclude=./$RUNTIME_ROOT_REL")
  fi
  tar_cmd+=(-cf - .)

  (cd "$SOURCE_ROOT" && "${tar_cmd[@]}") | (cd "$destination" && tar -xf -)
}

generate_copy_changed_files() {
  python3 - "$BASELINE_DIR" "$WORKSPACE_DIR" "$RUN_DIR/changed-files.txt" <<'PY'
from pathlib import Path
import filecmp
import os
import sys

baseline = Path(sys.argv[1])
workspace = Path(sys.argv[2])
output = Path(sys.argv[3])

changed = set()
all_paths = set()

for root, _, files in os.walk(baseline):
    root_path = Path(root)
    for name in files:
        all_paths.add((root_path / name).relative_to(baseline).as_posix())

for root, _, files in os.walk(workspace):
    root_path = Path(root)
    for name in files:
        all_paths.add((root_path / name).relative_to(workspace).as_posix())

for relative in sorted(all_paths):
    left = baseline / relative
    right = workspace / relative
    if not left.exists() or not right.exists():
        changed.add(relative)
        continue
    if not filecmp.cmp(left, right, shallow=False):
        changed.add(relative)

output.write_text("".join(f"{path}\n" for path in sorted(changed)), encoding="utf-8")
PY
}

generate_copy_patch() {
  local raw_diff
  raw_diff="$(mktemp)"
  set +e
  diff -ruN "$BASELINE_DIR" "$WORKSPACE_DIR" > "$raw_diff"
  local diff_exit=$?
  set -e

  python3 - "$raw_diff" "$RUN_DIR/patch.diff" "$BASELINE_DIR" "$WORKSPACE_DIR" <<'PY'
from pathlib import Path
import sys

raw_path = Path(sys.argv[1])
patch_path = Path(sys.argv[2])
baseline = sys.argv[3].rstrip("/")
workspace = sys.argv[4].rstrip("/")

content = raw_path.read_text(encoding="utf-8", errors="replace")
content = content.replace(f"{baseline}/", "a/")
content = content.replace(f"{workspace}/", "b/")
content = content.replace(baseline, "a")
content = content.replace(workspace, "b")
patch_path.write_text(content, encoding="utf-8")
PY

  rm -f "$raw_diff"
  if [ "$diff_exit" -gt 1 ]; then
    echo "copy-mode diff generation failed with exit code $diff_exit" >> "$RUN_DIR/stderr.log"
  fi
}

generate_git_artifacts() {
  (
    cd "$WORKSPACE_DIR"
    git add -N . >/dev/null 2>&1 || true
    git diff --name-only -- . | sort > "$RUN_DIR/changed-files.txt"
    git diff --binary -- . > "$RUN_DIR/patch.diff"
  )
}

generate_copy_artifacts() {
  generate_copy_changed_files
  generate_copy_patch
}

if git -C "$START_DIR" rev-parse --show-toplevel >/dev/null 2>&1; then
  SOURCE_ROOT="$(git -C "$START_DIR" rev-parse --show-toplevel)"
else
  SOURCE_ROOT="$START_DIR"
fi

TASK_FILE="$(resolve_path "$TASK_FILE_INPUT" "$START_DIR")"
RUNTIME_ROOT="$(resolve_path "$RUNTIME_ROOT_INPUT" "$SOURCE_ROOT")"

if [ ! -f "$TASK_FILE" ]; then
  echo "task file not found: $TASK_FILE" >&2
  exit 2
fi

TASK_ID="$(basename "$TASK_FILE" .md)"
RUN_DIR="$RUNTIME_ROOT/runs/$TASK_ID"
WORKSPACE_DIR="$RUNTIME_ROOT/workspaces/$TASK_ID"
BASELINE_DIR="$RUN_DIR/baseline"
ROLE="$(parse_role "$TASK_FILE")"
STARTED_AT="$(timestamp_utc)"
RUNTIME_ROOT_REL="$(relative_path_if_child "$SOURCE_ROOT" "$RUNTIME_ROOT")"

mkdir -p "$RUNTIME_ROOT/runs" "$RUNTIME_ROOT/workspaces"
rm -rf "$RUN_DIR"
mkdir -p "$RUN_DIR"

WORKSPACE_MODE="copy"
if git -C "$SOURCE_ROOT" rev-parse --show-toplevel >/dev/null 2>&1; then
  GIT_STATUS_ARGS=(status --porcelain --untracked-files=all -- .)
  if [ -n "$RUNTIME_ROOT_REL" ]; then
    GIT_STATUS_ARGS+=(":(exclude)$RUNTIME_ROOT_REL")
  fi
  GIT_STATUS_OUTPUT="$(git -C "$SOURCE_ROOT" "${GIT_STATUS_ARGS[@]}" || true)"
  if [ -z "$GIT_STATUS_OUTPUT" ]; then
    WORKSPACE_MODE="git-worktree"
  fi
fi

if [ "$WORKSPACE_MODE" = "git-worktree" ]; then
  mkdir -p "$(dirname "$WORKSPACE_DIR")"
  git -C "$SOURCE_ROOT" worktree prune >/dev/null 2>&1 || true
  git -C "$SOURCE_ROOT" worktree remove --force "$WORKSPACE_DIR" >/dev/null 2>&1 || true
  rm -rf "$WORKSPACE_DIR"
  if ! git -C "$SOURCE_ROOT" worktree add --detach "$WORKSPACE_DIR" HEAD >/dev/null 2>>"$RUN_DIR/stderr.log"; then
    WORKSPACE_MODE="copy"
  fi
fi

if [ "$WORKSPACE_MODE" = "copy" ]; then
  copy_source_tree "$BASELINE_DIR"
  copy_source_tree "$WORKSPACE_DIR"
fi

cp "$TASK_FILE" "$RUN_DIR/task.md"

PROMPT_FILE="$RUN_DIR/prompt.md"
cat "$TASK_FILE" > "$PROMPT_FILE"
cat >> "$PROMPT_FILE" <<PROMPT

---

You are running as a Claude Code subagent supervised by Codex.
Complete only the assigned task.
Your isolated workspace is:

- $WORKSPACE_DIR

Write observable outputs to:

- $RUN_DIR/result.md
- $RUN_DIR/status.json
- $RUN_DIR/changed-files.txt
- $RUN_DIR/patch.diff

Be honest about uncertainty, failed commands, and incomplete work.
Do not claim success unless the completion criteria are met.
PROMPT

touch "$RUN_DIR/events.jsonl" "$RUN_DIR/stderr.log"
write_running_status
write_session_json "" ""

if ! command -v "$CLAUDE_BIN" >/dev/null 2>&1; then
  echo "claude binary not found: $CLAUDE_BIN" >> "$RUN_DIR/stderr.log"
  EXIT_CODE=127
  printf '%s\n' "$EXIT_CODE" > "$RUN_DIR/exit_code.txt"
  : > "$RUN_DIR/changed-files.txt"
  : > "$RUN_DIR/patch.diff"
  FINISHED_AT="$(timestamp_utc)"
  write_default_result
  normalize_status
  write_session_json "$FINISHED_AT" "$EXIT_CODE"
  exit "$EXIT_CODE"
fi

CLAUDE_CMD=("$CLAUDE_BIN" "-p" "--output-format" "stream-json" "--include-partial-messages")
if [ -n "$CLAUDE_SUBAGENT_EXTRA_ARGS" ]; then
  read -r -a EXTRA_ARGS <<< "$CLAUDE_SUBAGENT_EXTRA_ARGS"
  CLAUDE_CMD+=("${EXTRA_ARGS[@]}")
fi
CLAUDE_CMD+=("$(cat "$PROMPT_FILE")")

set +e
(
  cd "$WORKSPACE_DIR"
  "${CLAUDE_CMD[@]}"
) > "$RUN_DIR/events.jsonl" 2>> "$RUN_DIR/stderr.log"
EXIT_CODE=$?
set -e

if [ "$WORKSPACE_MODE" = "git-worktree" ]; then
  generate_git_artifacts
else
  generate_copy_artifacts
fi

write_default_result
printf '%s\n' "$EXIT_CODE" > "$RUN_DIR/exit_code.txt"
FINISHED_AT="$(timestamp_utc)"
normalize_status
write_session_json "$FINISHED_AT" "$EXIT_CODE"
exit "$EXIT_CODE"
