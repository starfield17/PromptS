#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


READ_ONLY_DEFAULT_TOOLS = ["Read", "Grep", "Glob", "WebFetch", "WebSearch"]
WORKER_DEFAULT_TOOLS = ["Read", "Grep", "Glob", "Edit", "Write"]
WRITE_TOOLS = {"Edit", "Write", "NotebookEdit"}


def die(message: str, exit_code: int = 1) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(exit_code)


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return re.sub(r"-{2,}", "-", slug)[:48] or "task"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def isoformat(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def truncate_text(value: str, limit: int = 4000) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."


def read_json_file(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        die(f"Task file not found: {path}")
    except json.JSONDecodeError as exc:
        die(f"Invalid JSON in {path}: {exc}")


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


def tool_base_name(tool_spec: str) -> str:
    match = re.match(r"^([A-Za-z0-9_-]+)", tool_spec.strip())
    return match.group(1) if match else tool_spec.strip()


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
    if role not in {"reader", "worker"}:
        die("Task field 'role' must be either 'reader' or 'worker'.")
    if not isinstance(goal, str) or not goal.strip():
        die("Task field 'goal' is required and must be a non-empty string.")
    if not isinstance(cwd, str) or not cwd.strip():
        die("Task field 'cwd' is required and must be a non-empty string.")

    cwd_path = Path(cwd).expanduser().resolve()
    if not cwd_path.exists() or not cwd_path.is_dir():
        die(f"Task cwd does not exist or is not a directory: {cwd_path}")

    allowed_tools = normalize_string_list(task.get("allowed_tools"), "allowed_tools")
    constraints = normalize_string_list(task.get("constraints"), "constraints")
    deliverables = normalize_string_list(task.get("deliverables"), "deliverables")
    write_scope = normalize_string_list(task.get("write_scope"), "write_scope")
    context = normalize_context(task.get("context"))
    output_schema = task.get("output_schema")

    if role == "reader":
        if not allowed_tools:
            allowed_tools = READ_ONLY_DEFAULT_TOOLS.copy()
        invalid_write_tools = [
            tool for tool in allowed_tools if tool_base_name(tool) in WRITE_TOOLS
        ]
        if invalid_write_tools:
            die(
                "Reader tasks cannot request write tools: "
                + ", ".join(invalid_write_tools)
            )
        if write_scope:
            die("Reader tasks must not declare 'write_scope'.")

    if role == "worker":
        if not write_scope:
            die("Worker tasks must declare a non-empty 'write_scope'.")
        if not allowed_tools:
            allowed_tools = WORKER_DEFAULT_TOOLS.copy()

    if output_schema is not None and not isinstance(output_schema, dict):
        die("Field 'output_schema' must be a JSON object when provided.")

    normalized = {
        "name": name.strip(),
        "role": role,
        "goal": goal.strip(),
        "cwd": str(cwd_path),
        "context": context,
        "constraints": constraints,
        "deliverables": deliverables,
        "allowed_tools": allowed_tools,
        "write_scope": write_scope,
        "output_schema": output_schema,
    }
    return normalized


def render_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, indent=2)


def render_prompt_section(title: str, items: list[Any]) -> str:
    if not items:
        return f"{title}:\n- none"
    rendered = []
    for item in items:
        block = render_value(item).splitlines() or [""]
        rendered.append(f"- {block[0]}")
        rendered.extend(f"  {line}" for line in block[1:])
    return f"{title}:\n" + "\n".join(rendered)


def build_system_prompt(task: dict[str, Any]) -> str:
    common = [
        "You are Claude Code running as a subagent for Codex.",
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
        scope = ", ".join(task["write_scope"])
        common.extend(
            [
                "This task may modify files only when necessary.",
                f"Only touch files inside this write scope: {scope}",
                "Make the smallest change that satisfies the goal.",
                "Do not touch unrelated files or perform drive-by cleanup.",
                "If the scope is insufficient, stop and say so instead of expanding it yourself.",
                "If you changed files, end with a short changed-files summary.",
            ]
        )

    return "\n".join(common)


def build_user_prompt(task: dict[str, Any]) -> str:
    sections = [
        "Task contract for this Claude subagent run.",
        "",
        f"Name: {task['name']}",
        f"Role: {task['role']}",
        f"Working directory: {task['cwd']}",
        "",
        "Goal:",
        task["goal"],
        "",
        render_prompt_section("Context", task["context"]),
        "",
        render_prompt_section("Constraints", task["constraints"]),
        "",
        render_prompt_section("Deliverables", task["deliverables"]),
        "",
        render_prompt_section("Allowed tools", task["allowed_tools"]),
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
                "Return a response that conforms to the schema.",
            ]
        )

    sections.extend(
        [
            "",
            "Return only the requested deliverables for Codex.",
        ]
    )
    return "\n".join(sections)


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


def initial_summary(run_id: str, run_dir: Path, task: dict[str, Any], start: datetime) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "status": "running",
        "task": task,
        "started_at": isoformat(start),
        "ended_at": None,
        "duration_ms": None,
        "session_id": None,
        "model": None,
        "permission_mode": "dontAsk",
        "tool_calls": [],
        "permission_denials": [],
        "result": None,
        "structured_result": None,
        "result_parse_error": None,
        "total_cost_usd": None,
        "api_error_status": None,
        "terminal_reason": None,
        "num_turns": None,
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


def parse_tool_calls_from_message(message: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for block in message.get("content", []):
        if block.get("type") == "tool_use":
            result.append(
                {
                    "id": block.get("id"),
                    "name": block.get("name"),
                    "input": block.get("input"),
                }
            )
    return result


def parse_text_blocks_from_message(message: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for block in message.get("content", []):
        if block.get("type") == "text":
            text = block.get("text")
            if isinstance(text, str) and text.strip():
                result.append(text)
    return result


def handle_stream_event(
    event: dict[str, Any],
    summary: dict[str, Any],
    ops_path: Path,
    quiet: bool,
    seen_tool_use_keys: set[tuple[str | None, str | None]],
    seen_text_keys: set[tuple[str | None, str]],
) -> None:
    event_type = event.get("type")

    if event_type == "system" and event.get("subtype") == "init":
        summary["session_id"] = event.get("session_id")
        summary["model"] = event.get("model")
        emit_op(
            ops_path,
            {
                "type": "session_init",
                "session_id": event.get("session_id"),
                "model": event.get("model"),
                "permission_mode": event.get("permissionMode"),
            },
            quiet,
        )
        return

    if event_type == "system" and event.get("subtype") == "status":
        emit_op(
            ops_path,
            {
                "type": "status",
                "status": event.get("status"),
            },
            quiet,
        )
        return

    if event_type == "assistant":
        message = event.get("message", {})
        for tool_call in parse_tool_calls_from_message(message):
            dedupe_key = (tool_call.get("id"), tool_call.get("name"))
            if dedupe_key in seen_tool_use_keys:
                continue
            seen_tool_use_keys.add(dedupe_key)
            summary["tool_calls"].append(tool_call)
            emit_op(
                ops_path,
                {
                    "type": "tool_use",
                    "tool": tool_call.get("name"),
                    "tool_use_id": tool_call.get("id"),
                    "input": tool_call.get("input"),
                },
                quiet,
            )
        for text in parse_text_blocks_from_message(message):
            dedupe_key = (message.get("id"), text)
            if dedupe_key in seen_text_keys:
                continue
            seen_text_keys.add(dedupe_key)
            emit_op(
                ops_path,
                {
                    "type": "assistant_text",
                    "message_id": message.get("id"),
                    "text": text,
                },
                quiet,
            )
        return

    if event_type == "user" and "tool_use_result" in event:
        tool_result = event.get("tool_use_result", {})
        content = event.get("message", {}).get("content", [])
        tool_use_id = None
        if content and isinstance(content, list) and isinstance(content[0], dict):
            tool_use_id = content[0].get("tool_use_id")
        preview_source = tool_result.get("stdout") or tool_result.get("stderr") or ""
        emit_op(
            ops_path,
            {
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "is_error": tool_result.get("is_error", False),
                "stdout": truncate_text(tool_result.get("stdout", "")),
                "stderr": truncate_text(tool_result.get("stderr", "")),
                "preview": truncate_text(preview_source),
            },
            quiet,
        )
        return

    if event_type == "result":
        summary["status"] = "success" if not event.get("is_error") else "error"
        summary["result"] = event.get("result")
        summary["session_id"] = event.get("session_id") or summary["session_id"]
        summary["total_cost_usd"] = event.get("total_cost_usd")
        summary["api_error_status"] = event.get("api_error_status")
        summary["terminal_reason"] = event.get("terminal_reason")
        summary["num_turns"] = event.get("num_turns")
        summary["permission_denials"] = event.get("permission_denials", [])
        emit_op(
            ops_path,
            {
                "type": "result",
                "status": summary["status"],
                "result": event.get("result"),
                "total_cost_usd": event.get("total_cost_usd"),
                "terminal_reason": event.get("terminal_reason"),
            },
            quiet,
        )
        return


def run_command(args: argparse.Namespace) -> int:
    task = normalize_task(read_json_file(Path(args.task_file).expanduser().resolve()))

    start = now_utc()
    run_id = f"{start.strftime('%Y%m%dT%H%M%SZ')}-{slugify(task['name'])}-{uuid4().hex[:8]}"
    runs_dir = (
        Path(args.runs_dir).expanduser().resolve()
        if args.runs_dir
        else Path(task["cwd"]) / ".claude-subagents" / "runs"
    )
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

    system_prompt_path.write_text(system_prompt + "\n", encoding="utf-8")
    user_prompt_path.write_text(user_prompt + "\n", encoding="utf-8")
    write_json(task_path, task)

    summary = initial_summary(run_id, run_dir, task, start)
    write_json(summary_path, summary)

    emit_op(
        ops_path,
        {
            "type": "run_started",
            "run_id": run_id,
            "run_dir": str(run_dir),
            "role": task["role"],
            "cwd": task["cwd"],
        },
        args.quiet,
    )

    command = [
        "claude",
        "-p",
        "--verbose",
        "--output-format",
        "stream-json",
        "--permission-mode",
        "dontAsk",
        "--append-system-prompt",
        system_prompt,
        "--allowedTools",
        ",".join(task["allowed_tools"]),
        "--",
        user_prompt,
    ]

    if task["output_schema"] is not None:
        command[1:1] = ["--json-schema", json.dumps(task["output_schema"], ensure_ascii=False)]

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

    seen_tool_use_keys: set[tuple[str | None, str | None]] = set()
    seen_text_keys: set[tuple[str | None, str]] = set()

    with raw_path.open("a", encoding="utf-8") as raw_handle:
        try:
            assert process.stdout is not None
            for line in process.stdout:
                raw_handle.write(line)
                summary["raw_event_count"] += 1
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    emit_op(
                        ops_path,
                        {
                            "type": "parse_error",
                            "raw_line": truncate_text(line.rstrip()),
                        },
                        args.quiet,
                    )
                    continue
                handle_stream_event(
                    event=event,
                    summary=summary,
                    ops_path=ops_path,
                    quiet=args.quiet,
                    seen_tool_use_keys=seen_tool_use_keys,
                    seen_text_keys=seen_text_keys,
                )
        finally:
            stderr_output = process.stderr.read() if process.stderr is not None else ""
            stderr_path.write_text(stderr_output, encoding="utf-8")
            return_code = process.wait()

    ended_at = now_utc()
    summary["ended_at"] = isoformat(ended_at)
    summary["duration_ms"] = int((ended_at - start).total_seconds() * 1000)
    summary["exit_code"] = return_code

    if summary["status"] == "running":
        summary["status"] = "error" if return_code else "unknown"
        if stderr_output:
            summary["result"] = truncate_text(stderr_output)

    if task["output_schema"] is not None and isinstance(summary.get("result"), str):
        try:
            summary["structured_result"] = json.loads(summary["result"])
        except json.JSONDecodeError as exc:
            summary["result_parse_error"] = str(exc)

    if return_code and not stderr_output and summary["result"] is None:
        summary["result"] = f"claude exited with code {return_code}"

    with ops_path.open("r", encoding="utf-8") as handle:
        summary["ops_event_count"] = sum(1 for _ in handle)
    write_json(summary_path, summary)

    emit_op(
        ops_path,
        {
            "type": "run_finished",
            "run_id": run_id,
            "status": summary["status"],
            "summary_json": str(summary_path),
        },
        args.quiet,
    )

    summary["ops_event_count"] += 1
    write_json(summary_path, summary)
    return 0 if summary["status"] == "success" else 1


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
        description="Run local Claude Code sessions as observable Codex subagents.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run a Claude subagent task")
    run_parser.add_argument("--task-file", required=True, help="Path to a task JSON file")
    run_parser.add_argument(
        "--runs-dir",
        help="Override the base directory where run artifacts are stored",
    )
    run_parser.add_argument(
        "--quiet",
        action="store_true",
        help="Do not echo reduced ops events to stdout",
    )
    run_parser.set_defaults(func=run_command)

    tail_parser = subparsers.add_parser("tail", help="Print or follow ops.jsonl")
    tail_parser.add_argument("run_dir", help="Run directory created by the run command")
    tail_parser.add_argument(
        "--follow",
        action="store_true",
        help="Wait for new ops events until the run finishes",
    )
    tail_parser.set_defaults(func=tail_command)

    summary_parser = subparsers.add_parser("summary", help="Print summary.json")
    summary_parser.add_argument("run_dir", help="Run directory created by the run command")
    summary_parser.set_defaults(func=summary_command)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
