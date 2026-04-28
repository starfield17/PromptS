#!/usr/bin/env python3

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


VALID_ROLES = {"reader", "worker"}
PERMISSION_RE = re.compile(r"(permission|approval|denied|not allowed)", re.IGNORECASE)


def die(message: str, exit_code: int = 1) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(exit_code)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def isoformat(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return re.sub(r"-{2,}", "-", slug)[:48] or "task"


def truncate_text(value: Any, limit: int = 8000) -> str:
    text = value if isinstance(value, str) else summarize_value(value)
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def summarize_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except TypeError:
        return repr(value)


def read_json_file(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        die(f"JSON file not found: {path}")
    except json.JSONDecodeError as exc:
        die(f"Invalid JSON in {path}: {exc}")


def write_json(path: Path, value: Any) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def append_jsonl(path: Path, value: Any) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False) + "\n")


def emit_op(path: Path, event: dict[str, Any], quiet: bool) -> None:
    append_jsonl(path, event)
    if not quiet:
        print(json.dumps(event, ensure_ascii=False), flush=True)


def normalize_string_list(value: Any, field_name: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            if not isinstance(item, str):
                die(f"Field '{field_name}' must contain only strings.")
            stripped = item.strip()
            if stripped:
                result.append(stripped)
        return result
    die(f"Field '{field_name}' must be a string or a list of strings.")


def normalize_context(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def normalize_optional_string(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        die(f"Field '{field_name}' must be a string when provided.")
    stripped = value.strip()
    return stripped or None


def normalize_bool(value: Any, field_name: str, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    die(f"Field '{field_name}' must be a boolean when provided.")


def is_path_within(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
        return True
    except ValueError:
        return False


def resolve_task_path(cwd_path: Path, raw_path: str, field_name: str) -> Path:
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = cwd_path / candidate
    resolved = candidate.resolve()
    if not is_path_within(cwd_path, resolved):
        die(f"Field '{field_name}' must stay within cwd {cwd_path}: {raw_path}")
    return resolved


def normalize_task(raw_task: Any) -> dict[str, Any]:
    if not isinstance(raw_task, dict):
        die("Task JSON must be an object.")

    task = deepcopy(raw_task)
    name = task.get("name")
    role = task.get("role")
    goal = task.get("goal")
    cwd = task.get("cwd")

    if not isinstance(name, str) or not name.strip():
        die("Task field 'name' is required and must be a non-empty string.")
    if role not in VALID_ROLES:
        die("Task field 'role' must be either 'reader' or 'worker'.")
    if not isinstance(goal, str) or not goal.strip():
        die("Task field 'goal' is required and must be a non-empty string.")
    if not isinstance(cwd, str) or not cwd.strip():
        die("Task field 'cwd' is required and must be a non-empty string.")

    cwd_path = Path(cwd).expanduser().resolve()
    if not cwd_path.exists() or not cwd_path.is_dir():
        die(f"Task cwd does not exist or is not a directory: {cwd_path}")

    context = normalize_context(task.get("context"))
    constraints = normalize_string_list(task.get("constraints"), "constraints")
    deliverables = normalize_string_list(task.get("deliverables"), "deliverables")
    files = normalize_string_list(task.get("files"), "files")
    write_scope = normalize_string_list(task.get("write_scope"), "write_scope")
    model = normalize_optional_string(task.get("model"), "model")
    variant = normalize_optional_string(task.get("variant"), "variant")
    agent = normalize_optional_string(task.get("agent"), "agent")
    output_schema = task.get("output_schema")
    dangerously_skip_permissions = normalize_bool(
        task.get("dangerously_skip_permissions"),
        "dangerously_skip_permissions",
    )

    if model is not None and "/" not in model:
        die("Field 'model' must use OpenCode's provider/model format.")

    if role == "reader":
        if write_scope:
            die("Reader tasks must not declare 'write_scope'.")

    if role == "worker":
        if not write_scope:
            die("Worker tasks must declare a non-empty 'write_scope'.")
        for path_value in write_scope:
            resolve_task_path(cwd_path, path_value, "write_scope")

    if output_schema is not None and not isinstance(output_schema, dict):
        die("Field 'output_schema' must be a JSON object when provided.")

    return {
        "name": name.strip(),
        "role": role,
        "goal": goal.strip(),
        "cwd": str(cwd_path),
        "model": model,
        "variant": variant,
        "agent": agent,
        "context": context,
        "constraints": constraints,
        "deliverables": deliverables,
        "files": files,
        "write_scope": write_scope,
        "output_schema": output_schema,
        "dangerously_skip_permissions": dangerously_skip_permissions,
    }


def merge_task_defaults(defaults: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(defaults)
    merged.update(task)
    return merged


def normalize_batch(raw_batch: Any) -> tuple[list[dict[str, Any]], int | None]:
    if not isinstance(raw_batch, dict):
        die("Batch JSON must be an object.")
    defaults = raw_batch.get("defaults", {})
    if defaults is None:
        defaults = {}
    if not isinstance(defaults, dict):
        die("Batch field 'defaults' must be an object when provided.")
    raw_tasks = raw_batch.get("tasks")
    if not isinstance(raw_tasks, list) or not raw_tasks:
        die("Batch field 'tasks' must be a non-empty list.")

    tasks: list[dict[str, Any]] = []
    for item in raw_tasks:
        if not isinstance(item, dict):
            die("Batch field 'tasks' must contain only objects.")
        tasks.append(normalize_task(merge_task_defaults(defaults, item)))
    max_parallel = raw_batch.get("max_parallel")
    if max_parallel is None:
        return tasks, None
    if not isinstance(max_parallel, int) or max_parallel < 1:
        die("Batch field 'max_parallel' must be a positive integer or null.")
    return tasks, max_parallel


def render_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, indent=2)


def render_prompt_section(title: str, items: list[Any]) -> str:
    if not items:
        return f"{title}:\n- none"
    rendered: list[str] = []
    for item in items:
        block = render_value(item).splitlines() or [""]
        rendered.append(f"- {block[0]}")
        rendered.extend(f"  {line}" for line in block[1:])
    return f"{title}:\n" + "\n".join(rendered)


def build_system_prompt(task: dict[str, Any]) -> str:
    common = [
        "You are OpenCode running as a subagent for Codex.",
        "Follow the provided task contract exactly.",
        "Do not ask the end user questions.",
        "If you are blocked, say what blocked you and what Codex should do next.",
        "Use tools rather than guessing.",
        "Codex can inspect your tool trace, so never claim actions you did not perform.",
        "Keep the final answer concise and directly useful to Codex.",
    ]

    if task["role"] == "reader":
        common.extend(
            [
                "This is a read-only task.",
                "Do not edit, write, or propose broad refactors.",
                "Focus on findings, concrete evidence, and actionable conclusions.",
            ]
        )
    else:
        common.extend(
            [
                "This task may modify files only when necessary.",
                "You are not alone in the codebase; do not revert or overwrite unrelated changes.",
                "Only touch files inside the declared write scope.",
                "Make the smallest change that satisfies the goal.",
                "Do not touch unrelated files or perform drive-by cleanup.",
                "If the scope is insufficient, stop and say so instead of expanding it yourself.",
                "If you changed files, end with a short changed-files summary.",
            ]
        )

    return "\n".join(common)


def build_user_prompt(task: dict[str, Any]) -> str:
    sections = [
        "System instructions for this OpenCode subagent run:",
        build_system_prompt(task),
        "",
        "Task contract:",
        f"Name: {task['name']}",
        f"Role: {task['role']}",
        f"Working directory: {task['cwd']}",
        f"Model: {task['model'] or 'OpenCode default'}",
        f"Agent: {task['agent'] or 'OpenCode default'}",
        "",
        "Goal:",
        task["goal"],
        "",
        render_prompt_section("Context", task["context"]),
        "",
        render_prompt_section("Constraints", task["constraints"]),
        "",
        render_prompt_section("Deliverables", task["deliverables"]),
    ]

    if task["role"] == "worker":
        sections.extend(["", render_prompt_section("Write scope", task["write_scope"])])

    if task["output_schema"] is not None:
        sections.extend(
            [
                "",
                "Output schema:",
                json.dumps(task["output_schema"], ensure_ascii=False, indent=2),
                "",
                "Return a final response that conforms to the schema.",
            ]
        )

    sections.extend(["", "Return only the requested deliverables for Codex."])
    return "\n".join(sections)


def build_opencode_command(
    task: dict[str, Any],
    opencode_bin: str,
    user_prompt: str,
) -> list[str]:
    command = [
        opencode_bin,
        "run",
        "--format",
        "json",
        "--dir",
        task["cwd"],
        "--title",
        task["name"],
    ]

    if task["model"]:
        command.extend(["--model", task["model"]])
    if task["variant"]:
        command.extend(["--variant", task["variant"]])
    if task["agent"]:
        command.extend(["--agent", task["agent"]])
    for file_path in task["files"]:
        command.extend(["--file", file_path])
    if task["dangerously_skip_permissions"]:
        command.append("--dangerously-skip-permissions")

    command.append(user_prompt)
    return command


def command_display(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def is_git_worktree(cwd: Path) -> bool:
    process = subprocess.run(
        ["git", "-C", str(cwd), "rev-parse", "--is-inside-work-tree"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
    )
    return process.returncode == 0 and process.stdout.strip() == "true"


def git_dirty_files(cwd: Path) -> set[str]:
    process = subprocess.run(
        ["git", "-C", str(cwd), "status", "--porcelain=v1", "-z"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if process.returncode != 0:
        return set()

    entries = [entry for entry in process.stdout.split("\0") if entry]
    paths: set[str] = set()
    index = 0
    while index < len(entries):
        entry = entries[index]
        if len(entry) < 4:
            index += 1
            continue
        code = entry[:2]
        path = entry[3:]
        if code[0] in {"R", "C"} and index + 1 < len(entries):
            index += 1
            path = entries[index]
        paths.add(path)
        index += 1
    return paths


def scope_matches(scope_raw: str, cwd: Path, touched_raw: str) -> bool:
    scope_path = resolve_task_path(cwd, scope_raw, "write_scope")
    touched_path = resolve_task_path(cwd, touched_raw, "touched_files")
    if touched_path == scope_path:
        return True
    if scope_path.exists() and scope_path.is_dir():
        return is_path_within(scope_path, touched_path)
    if scope_raw.endswith(("/", os.sep)):
        return is_path_within(scope_path, touched_path)
    return False


def find_out_of_scope_files(task: dict[str, Any], touched_files: list[str]) -> list[str]:
    if not touched_files:
        return []
    if task["role"] == "reader":
        return touched_files

    cwd = Path(task["cwd"])
    out_of_scope: list[str] = []
    for touched_file in touched_files:
        if not any(scope_matches(scope, cwd, touched_file) for scope in task["write_scope"]):
            out_of_scope.append(touched_file)
    return out_of_scope


def filter_artifact_files(paths: set[str]) -> set[str]:
    return {
        path
        for path in paths
        if path != ".opencode-subagents"
        and not path.startswith(".opencode-subagents/")
    }


def scopes_overlap(task_a: dict[str, Any], scope_a: str, task_b: dict[str, Any], scope_b: str) -> bool:
    cwd_a = Path(task_a["cwd"])
    cwd_b = Path(task_b["cwd"])
    path_a = resolve_task_path(cwd_a, scope_a, "write_scope")
    path_b = resolve_task_path(cwd_b, scope_b, "write_scope")
    return path_a == path_b or is_path_within(path_a, path_b) or is_path_within(path_b, path_a)


def validate_worker_scope_overlap(tasks: list[dict[str, Any]]) -> None:
    workers = [task for task in tasks if task["role"] == "worker"]
    for left_index, left in enumerate(workers):
        for right in workers[left_index + 1 :]:
            for left_scope in left["write_scope"]:
                for right_scope in right["write_scope"]:
                    if scopes_overlap(left, left_scope, right, right_scope):
                        die(
                            "Worker write scopes overlap: "
                            f"{left['name']}:{left_scope} and {right['name']}:{right_scope}"
                        )


def extract_error_message(event: dict[str, Any]) -> str | None:
    error = event.get("error")
    if isinstance(error, str):
        return error
    if isinstance(error, dict):
        data = error.get("data")
        if isinstance(data, dict):
            message = data.get("message")
            if isinstance(message, str):
                return message
        message = error.get("message") or error.get("name")
        if isinstance(message, str):
            return message
    return None


def detect_permission_event(text: str) -> bool:
    return bool(text and PERMISSION_RE.search(text))


def initial_summary(run_id: str, run_dir: Path, task: dict[str, Any], start: datetime) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "status": "running",
        "task": task,
        "started_at": isoformat(start),
        "ended_at": None,
        "duration_ms": None,
        "exit_code": None,
        "session_id": None,
        "model": task["model"],
        "variant": task["variant"],
        "agent": task["agent"],
        "opencode_command": None,
        "workspace_tracking": "unavailable",
        "dirty_files_before": [],
        "dirty_files_after": [],
        "touched_files": [],
        "out_of_scope_files": [],
        "tool_calls": [],
        "permission_events": [],
        "result": None,
        "structured_result": None,
        "result_parse_error": None,
        "total_cost_usd": 0,
        "tokens": {
            "input": 0,
            "output": 0,
            "reasoning": 0,
            "cache_read": 0,
            "cache_write": 0,
        },
        "terminal_reason": None,
        "raw_event_count": 0,
        "ops_event_count": 0,
        "artifacts": {
            "task_json": str(run_dir / "task.json"),
            "system_prompt": str(run_dir / "system_prompt.txt"),
            "user_prompt": str(run_dir / "user_prompt.txt"),
            "raw_stream": str(run_dir / "raw.stream.jsonl"),
            "ops_stream": str(run_dir / "ops.jsonl"),
            "stderr_log": str(run_dir / "stderr.log"),
            "summary_json": str(run_dir / "summary.json"),
        },
    }


def add_tokens(summary: dict[str, Any], tokens: dict[str, Any]) -> None:
    if not isinstance(tokens, dict):
        return
    summary["tokens"]["input"] += int(tokens.get("input") or 0)
    summary["tokens"]["output"] += int(tokens.get("output") or 0)
    summary["tokens"]["reasoning"] += int(tokens.get("reasoning") or 0)
    cache = tokens.get("cache")
    if isinstance(cache, dict):
        summary["tokens"]["cache_read"] += int(cache.get("read") or 0)
        summary["tokens"]["cache_write"] += int(cache.get("write") or 0)


def append_permission_event(
    summary: dict[str, Any],
    ops_path: Path,
    quiet: bool,
    source: str,
    message: str,
) -> None:
    event = {"source": source, "message": truncate_text(message)}
    if event in summary["permission_events"]:
        return
    summary["permission_events"].append(event)
    emit_op(
        ops_path,
        {
            "type": "permission_event",
            "source": source,
            "message": truncate_text(message),
        },
        quiet,
    )


def handle_stream_event(
    event: dict[str, Any],
    summary: dict[str, Any],
    ops_path: Path,
    quiet: bool,
    text_blocks: list[str],
) -> None:
    event_type = event.get("type")
    part = event.get("part") if isinstance(event.get("part"), dict) else {}
    session_id = event.get("sessionID") or part.get("sessionID")
    if session_id and summary["session_id"] is None:
        summary["session_id"] = session_id

    if event_type == "step_start":
        emit_op(
            ops_path,
            {
                "type": "step_start",
                "session_id": session_id,
                "message_id": part.get("messageID"),
                "snapshot": part.get("snapshot"),
            },
            quiet,
        )
        return

    if event_type == "tool_use":
        state = part.get("state") if isinstance(part.get("state"), dict) else {}
        metadata = state.get("metadata") if isinstance(state.get("metadata"), dict) else {}
        tool_call = {
            "id": part.get("callID") or part.get("id"),
            "part_id": part.get("id"),
            "tool": part.get("tool"),
            "status": state.get("status"),
            "input": state.get("input"),
            "title": state.get("title"),
            "metadata": metadata,
        }
        output = state.get("output")
        if output is None:
            output = metadata.get("output")
        summary["tool_calls"].append(tool_call)
        emit_op(
            ops_path,
            {
                "type": "tool_use",
                "tool": tool_call["tool"],
                "tool_use_id": tool_call["id"],
                "status": tool_call["status"],
                "input": tool_call["input"],
                "title": tool_call["title"],
            },
            quiet,
        )
        emit_op(
            ops_path,
            {
                "type": "tool_result",
                "tool": tool_call["tool"],
                "tool_use_id": tool_call["id"],
                "output": truncate_text(output or ""),
                "metadata": metadata,
            },
            quiet,
        )
        rendered = summarize_value(output)
        if detect_permission_event(rendered):
            append_permission_event(summary, ops_path, quiet, "tool_result", rendered)
        return

    if event_type == "text":
        text = part.get("text")
        if isinstance(text, str) and text:
            text_blocks.append(text)
            emit_op(
                ops_path,
                {
                    "type": "assistant_text",
                    "part_id": part.get("id"),
                    "text": truncate_text(text),
                },
                quiet,
            )
            if detect_permission_event(text):
                append_permission_event(summary, ops_path, quiet, "assistant_text", text)
        return

    if event_type == "step_finish":
        reason = part.get("reason")
        summary["terminal_reason"] = reason or summary["terminal_reason"]
        cost = part.get("cost")
        if isinstance(cost, (int, float)):
            summary["total_cost_usd"] += cost
        add_tokens(summary, part.get("tokens"))
        emit_op(
            ops_path,
            {
                "type": "step_finish",
                "session_id": session_id,
                "reason": reason,
                "cost": cost,
                "tokens": part.get("tokens"),
                "snapshot": part.get("snapshot"),
            },
            quiet,
        )
        return

    if event_type == "error":
        message = extract_error_message(event) or summarize_value(event)
        summary["status"] = "error"
        summary["result"] = truncate_text(message)
        emit_op(
            ops_path,
            {
                "type": "error",
                "session_id": session_id,
                "message": truncate_text(message),
            },
            quiet,
        )
        if detect_permission_event(message):
            append_permission_event(summary, ops_path, quiet, "error", message)
        return

    emit_op(
        ops_path,
        {
            "type": "event",
            "event_type": event_type,
            "preview": truncate_text(event),
        },
        quiet,
    )


def parse_structured_result(result: Any) -> tuple[Any, str | None]:
    if result is None:
        return None, None
    if not isinstance(result, str):
        return result, None

    text = result.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```") and lines[-1].strip() == "```":
            text = "\n".join(lines[1:-1]).strip()
    try:
        return json.loads(text), None
    except json.JSONDecodeError as exc:
        return None, str(exc)


def read_stderr(stderr: Any, stderr_path: Path, collector: list[str]) -> None:
    with stderr_path.open("a", encoding="utf-8") as handle:
        for line in stderr:
            collector.append(line)
            handle.write(line)
            handle.flush()


def count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for _ in handle)


def run_task(
    task: dict[str, Any],
    runs_dir: Path,
    opencode_bin: str,
    quiet: bool,
) -> dict[str, Any]:
    if os.sep in opencode_bin:
        executable = str(Path(opencode_bin).expanduser().resolve())
        if not Path(executable).exists():
            executable = None
    else:
        executable = shutil.which(opencode_bin)
    if executable is None:
        die(f"Could not find opencode executable: {opencode_bin}")

    start = now_utc()
    run_id = f"{start.strftime('%Y%m%dT%H%M%SZ')}-{slugify(task['name'])}-{uuid4().hex[:8]}"
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    raw_path = run_dir / "raw.stream.jsonl"
    ops_path = run_dir / "ops.jsonl"
    stderr_path = run_dir / "stderr.log"
    summary_path = run_dir / "summary.json"
    system_prompt_path = run_dir / "system_prompt.txt"
    user_prompt_path = run_dir / "user_prompt.txt"
    task_path = run_dir / "task.json"

    system_prompt = build_system_prompt(task)
    user_prompt = build_user_prompt(task)
    command = build_opencode_command(task, executable, user_prompt)

    system_prompt_path.write_text(system_prompt + "\n", encoding="utf-8")
    user_prompt_path.write_text(user_prompt + "\n", encoding="utf-8")
    write_json(task_path, task)

    summary = initial_summary(run_id, run_dir, task, start)
    summary["opencode_command"] = command_display(command)

    cwd_path = Path(task["cwd"])
    if is_git_worktree(cwd_path):
        summary["workspace_tracking"] = "git"
        summary["dirty_files_before"] = sorted(git_dirty_files(cwd_path))

    write_json(summary_path, summary)
    emit_op(
        ops_path,
        {
            "type": "run_started",
            "run_id": run_id,
            "run_dir": str(run_dir),
            "role": task["role"],
            "cwd": task["cwd"],
            "model": task["model"],
            "agent": task["agent"],
        },
        quiet,
    )
    emit_op(
        ops_path,
        {
            "type": "opencode_command",
            "command": summary["opencode_command"],
        },
        quiet,
    )

    process = subprocess.Popen(
        command,
        cwd=task["cwd"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    stderr_lines: list[str] = []
    stderr_thread = threading.Thread(
        target=read_stderr,
        args=(process.stderr, stderr_path, stderr_lines),
        daemon=True,
    )
    stderr_thread.start()

    text_blocks: list[str] = []
    with raw_path.open("a", encoding="utf-8") as raw_handle:
        assert process.stdout is not None
        for line in process.stdout:
            raw_handle.write(line)
            raw_handle.flush()
            summary["raw_event_count"] += 1
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                emit_op(
                    ops_path,
                    {"type": "parse_error", "raw_line": truncate_text(line.rstrip())},
                    quiet,
                )
                continue
            if not isinstance(event, dict):
                emit_op(
                    ops_path,
                    {"type": "parse_error", "raw_line": truncate_text(event)},
                    quiet,
                )
                continue
            try:
                handle_stream_event(event, summary, ops_path, quiet, text_blocks)
            except Exception as exc:
                emit_op(
                    ops_path,
                    {
                        "type": "event_error",
                        "event_type": event.get("type"),
                        "error": truncate_text(str(exc)),
                    },
                    quiet,
                )

    return_code = process.wait()
    stderr_thread.join(timeout=5)
    stderr_output = "".join(stderr_lines)

    ended_at = now_utc()
    summary["ended_at"] = isoformat(ended_at)
    summary["duration_ms"] = int((ended_at - start).total_seconds() * 1000)
    summary["exit_code"] = return_code

    if summary["workspace_tracking"] == "git":
        summary["dirty_files_after"] = sorted(git_dirty_files(cwd_path))
        before = filter_artifact_files(set(summary["dirty_files_before"]))
        after = filter_artifact_files(set(summary["dirty_files_after"]))
        summary["touched_files"] = sorted(after - before)
        summary["out_of_scope_files"] = find_out_of_scope_files(
            task,
            summary["touched_files"],
        )

    if summary["result"] is None:
        summary["result"] = "\n".join(text_blocks).strip() or None

    if stderr_output and detect_permission_event(stderr_output):
        append_permission_event(summary, ops_path, quiet, "stderr", stderr_output)

    if summary["out_of_scope_files"]:
        summary["status"] = "scope_violation"
    elif summary["status"] == "running":
        summary["status"] = "success" if return_code == 0 else "error"

    if return_code and summary["result"] is None:
        summary["result"] = truncate_text(stderr_output or f"opencode exited with code {return_code}")

    if task["output_schema"] is not None:
        structured_result, parse_error = parse_structured_result(summary["result"])
        summary["structured_result"] = structured_result
        summary["result_parse_error"] = parse_error

    emit_op(
        ops_path,
        {
            "type": "result",
            "status": summary["status"],
            "result": truncate_text(summary["result"]),
            "touched_files": summary["touched_files"],
            "out_of_scope_files": summary["out_of_scope_files"],
            "total_cost_usd": summary["total_cost_usd"],
        },
        quiet,
    )
    emit_op(
        ops_path,
        {
            "type": "run_finished",
            "run_id": run_id,
            "status": summary["status"],
            "summary_json": str(summary_path),
        },
        quiet,
    )

    summary["ops_event_count"] = count_lines(ops_path)
    write_json(summary_path, summary)
    return summary


def run_command(args: argparse.Namespace) -> int:
    task = normalize_task(read_json_file(Path(args.task_file).expanduser().resolve()))
    runs_dir = (
        Path(args.runs_dir).expanduser().resolve()
        if args.runs_dir
        else Path(task["cwd"]) / ".opencode-subagents" / "runs"
    )
    summary = run_task(
        task=task,
        runs_dir=runs_dir,
        opencode_bin=args.opencode_bin,
        quiet=args.quiet,
    )
    return 0 if summary["status"] == "success" else 1


def batch_summary_initial(batch_id: str, batch_dir: Path, tasks: list[dict[str, Any]], start: datetime) -> dict[str, Any]:
    return {
        "batch_id": batch_id,
        "batch_dir": str(batch_dir),
        "status": "running",
        "started_at": isoformat(start),
        "ended_at": None,
        "duration_ms": None,
        "task_count": len(tasks),
        "runs": [],
        "artifacts": {
            "batch_json": str(batch_dir / "batch.json"),
            "ops_stream": str(batch_dir / "ops.jsonl"),
            "summary_json": str(batch_dir / "summary.json"),
        },
    }


def run_many_command(args: argparse.Namespace) -> int:
    raw_batch = read_json_file(Path(args.batch_file).expanduser().resolve())
    tasks, batch_max_parallel = normalize_batch(raw_batch)
    validate_worker_scope_overlap(tasks)

    max_parallel = args.max_parallel or batch_max_parallel or len(tasks)
    base_dir = (
        Path(args.runs_dir).expanduser().resolve()
        if args.runs_dir
        else Path(tasks[0]["cwd"]) / ".opencode-subagents"
    )
    runs_dir = base_dir / "runs"

    start = now_utc()
    batch_id = f"{start.strftime('%Y%m%dT%H%M%SZ')}-batch-{uuid4().hex[:8]}"
    batch_dir = base_dir / "batches" / batch_id
    batch_dir.mkdir(parents=True, exist_ok=False)

    batch_json_path = batch_dir / "batch.json"
    ops_path = batch_dir / "ops.jsonl"
    summary_path = batch_dir / "summary.json"
    write_json(batch_json_path, {"tasks": tasks, "max_parallel": max_parallel})

    batch_summary = batch_summary_initial(batch_id, batch_dir, tasks, start)
    write_json(summary_path, batch_summary)
    emit_op(
        ops_path,
        {
            "type": "batch_started",
            "batch_id": batch_id,
            "batch_dir": str(batch_dir),
            "task_count": len(tasks),
            "max_parallel": max_parallel,
        },
        args.quiet,
    )

    failures = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_parallel) as executor:
        future_to_task = {
            executor.submit(run_task, task, runs_dir, args.opencode_bin, True): task
            for task in tasks
        }
        for future in concurrent.futures.as_completed(future_to_task):
            task = future_to_task[future]
            try:
                run_summary = future.result()
            except Exception as exc:
                failures += 1
                run_record = {
                    "name": task["name"],
                    "status": "error",
                    "error": truncate_text(str(exc)),
                }
            else:
                if run_summary["status"] != "success":
                    failures += 1
                run_record = {
                    "name": task["name"],
                    "status": run_summary["status"],
                    "run_id": run_summary["run_id"],
                    "run_dir": run_summary["run_dir"],
                    "summary_json": run_summary["artifacts"]["summary_json"],
                    "model": run_summary["model"],
                    "agent": run_summary["agent"],
                }
            batch_summary["runs"].append(run_record)
            emit_op(
                ops_path,
                {
                    "type": "task_finished",
                    **run_record,
                },
                args.quiet,
            )
            write_json(summary_path, batch_summary)

    ended_at = now_utc()
    batch_summary["ended_at"] = isoformat(ended_at)
    batch_summary["duration_ms"] = int((ended_at - start).total_seconds() * 1000)
    batch_summary["status"] = "success" if failures == 0 else "error"
    emit_op(
        ops_path,
        {
            "type": "batch_finished",
            "batch_id": batch_id,
            "status": batch_summary["status"],
            "summary_json": str(summary_path),
        },
        args.quiet,
    )
    write_json(summary_path, batch_summary)
    return 0 if failures == 0 else 1


def tail_command(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).expanduser().resolve()
    ops_path = run_dir / "ops.jsonl"
    summary_path = run_dir / "summary.json"
    if not ops_path.exists():
        die(f"ops.jsonl not found in {run_dir}")

    with ops_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            print(line, end="")

        if not args.follow:
            return 0

        while True:
            position = handle.tell()
            line = handle.readline()
            if line:
                print(line, end="", flush=True)
                continue

            handle.seek(position)
            if summary_path.exists():
                summary = read_json_file(summary_path)
                if isinstance(summary, dict) and summary.get("status") != "running":
                    time.sleep(0.2)
                    position = handle.tell()
                    line = handle.readline()
                    if not line:
                        break
                    handle.seek(position)
            time.sleep(0.2)
    return 0


def summary_command(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).expanduser().resolve()
    summary_path = run_dir / "summary.json"
    if not summary_path.exists():
        die(f"summary.json not found in {run_dir}")
    summary = read_json_file(summary_path)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run local OpenCode sessions as observable Codex subagents.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run one OpenCode subagent task")
    run_parser.add_argument("--task-file", required=True, help="Path to a task JSON file")
    run_parser.add_argument(
        "--runs-dir",
        help="Override the directory where run artifacts are stored",
    )
    run_parser.add_argument(
        "--opencode-bin",
        default="opencode",
        help="OpenCode executable to run",
    )
    run_parser.add_argument(
        "--quiet",
        action="store_true",
        help="Do not echo reduced ops events to stdout",
    )
    run_parser.set_defaults(func=run_command)

    run_many_parser = subparsers.add_parser(
        "run-many",
        help="Run multiple OpenCode subagent tasks in parallel",
    )
    run_many_parser.add_argument("--batch-file", required=True, help="Path to a batch JSON file")
    run_many_parser.add_argument(
        "--runs-dir",
        help="Override the base directory where batch and run artifacts are stored",
    )
    run_many_parser.add_argument(
        "--max-parallel",
        type=int,
        help="Override batch max_parallel",
    )
    run_many_parser.add_argument(
        "--opencode-bin",
        default="opencode",
        help="OpenCode executable to run",
    )
    run_many_parser.add_argument(
        "--quiet",
        action="store_true",
        help="Do not echo batch events to stdout",
    )
    run_many_parser.set_defaults(func=run_many_command)

    tail_parser = subparsers.add_parser("tail", help="Print or follow ops.jsonl")
    tail_parser.add_argument("run_dir", help="Run or batch directory")
    tail_parser.add_argument(
        "--follow",
        action="store_true",
        help="Wait for new ops events until the run finishes",
    )
    tail_parser.set_defaults(func=tail_command)

    summary_parser = subparsers.add_parser("summary", help="Print summary.json")
    summary_parser.add_argument("run_dir", help="Run or batch directory")
    summary_parser.set_defaults(func=summary_command)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if getattr(args, "max_parallel", None) is not None and args.max_parallel < 1:
        die("--max-parallel must be a positive integer.")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
