#!/usr/bin/env python3

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


READONLY_TOOLS = "Read,Grep,Glob,LS"
EDITOR_TOOLS = "default"
FINAL_STATES = {"succeeded", "failed", "lost"}


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def skill_root():
    return Path(__file__).resolve().parent.parent


def runs_root():
    root = skill_root() / "runs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def read_json(path):
    return json.loads(path.read_text())


def first_line(text):
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:120]
    return ""


def make_worker_id():
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{timestamp}-{uuid4().hex[:8]}"


def worker_dir(worker_id):
    return runs_root() / worker_id


def process_alive(pid):
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def require_claude():
    if shutil.which("claude"):
        return
    raise SystemExit("`claude` was not found in PATH.")


def build_claude_command(metadata, prompt):
    command = [
        "claude",
        "-p",
        "--output-format",
        "json",
        "--add-dir",
        metadata["cwd"],
    ]

    model = metadata.get("model")
    if model:
        command.extend(["--model", model])

    effort = metadata.get("effort")
    if effort:
        command.extend(["--effort", effort])

    if metadata["mode"] == "readonly":
        command.extend(["--tools", READONLY_TOOLS, "--permission-mode", "dontAsk"])
    else:
        command.extend(["--tools", EDITOR_TOOLS, "--permission-mode", "acceptEdits"])

    command.append(prompt)
    return command


def parse_stdout(stdout_text):
    raw_text = stdout_text.strip()
    if not raw_text:
        return {"result_text": "", "session_id": None, "payload": None}

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError:
        return {"result_text": raw_text, "session_id": None, "payload": None}

    result_text = payload.get("result", "")
    if not isinstance(result_text, str):
        result_text = json.dumps(result_text, ensure_ascii=False)

    session_id = payload.get("session_id")
    if session_id is not None and not isinstance(session_id, str):
        session_id = str(session_id)

    return {"result_text": result_text.strip(), "session_id": session_id, "payload": payload}


def load_snapshot(run_dir):
    metadata = read_json(run_dir / "metadata.json")
    status = read_json(run_dir / "status.json")
    result_path = run_dir / "result.json"
    result = read_json(result_path) if result_path.exists() else None

    snapshot = {
        "worker_id": metadata["worker_id"],
        "mode": metadata["mode"],
        "cwd": metadata["cwd"],
        "model": metadata.get("model"),
        "effort": metadata.get("effort"),
        "task_summary": metadata["task_summary"],
        "started_at": metadata["started_at"],
        "status": status["status"],
        "pid": status.get("pid"),
        "finished_at": status.get("finished_at"),
        "exit_code": status.get("exit_code"),
        "run_dir": str(run_dir),
    }

    if result is not None:
        snapshot["session_id"] = result.get("session_id")
        snapshot["result_text"] = result.get("result_text")
        return snapshot

    if snapshot["status"] not in FINAL_STATES and snapshot["pid"] and not process_alive(snapshot["pid"]):
        snapshot["status"] = "lost"

    return snapshot


def cmd_start(args):
    require_claude()

    task_file = Path(args.task_file).resolve()
    if not task_file.is_file():
        raise SystemExit(f"Task file not found: {task_file}")

    cwd = Path(args.cwd).resolve()
    if not cwd.is_dir():
        raise SystemExit(f"Working directory not found: {cwd}")

    prompt = task_file.read_text()
    worker_id = make_worker_id()
    run_dir = worker_dir(worker_id)
    run_dir.mkdir(parents=True, exist_ok=False)

    metadata = {
        "worker_id": worker_id,
        "mode": args.mode,
        "cwd": str(cwd),
        "model": args.model,
        "effort": args.effort,
        "started_at": now_iso(),
        "pid": None,
        "status": "queued",
        "task_summary": first_line(prompt),
    }
    status = {
        "worker_id": worker_id,
        "status": "queued",
        "pid": None,
        "started_at": metadata["started_at"],
        "finished_at": None,
        "exit_code": None,
    }

    (run_dir / "prompt.txt").write_text(prompt)
    write_json(run_dir / "metadata.json", metadata)
    write_json(run_dir / "status.json", status)

    runner = subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), "_run", "--run-dir", str(run_dir)],
        cwd=str(cwd),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    metadata["pid"] = runner.pid
    write_json(run_dir / "metadata.json", metadata)

    status["pid"] = runner.pid
    write_json(run_dir / "status.json", status)

    print(json.dumps(load_snapshot(run_dir), indent=2, sort_keys=True))


def cmd_run(args):
    run_dir = Path(args.run_dir).resolve()
    metadata_path = run_dir / "metadata.json"
    status_path = run_dir / "status.json"

    metadata = read_json(metadata_path)
    prompt = (run_dir / "prompt.txt").read_text()

    command = build_claude_command(metadata, prompt)
    process = subprocess.Popen(
        command,
        cwd=metadata["cwd"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    metadata["pid"] = process.pid
    metadata["status"] = "running"
    write_json(metadata_path, metadata)

    running_status = {
        "worker_id": metadata["worker_id"],
        "status": "running",
        "pid": process.pid,
        "started_at": metadata["started_at"],
        "finished_at": None,
        "exit_code": None,
    }
    write_json(status_path, running_status)

    stdout_text, stderr_text = process.communicate()

    (run_dir / "stdout.json").write_text(stdout_text)
    (run_dir / "stderr.txt").write_text(stderr_text)

    parsed = parse_stdout(stdout_text)
    finished_at = now_iso()
    final_status = "succeeded" if process.returncode == 0 else "failed"

    result = {
        "worker_id": metadata["worker_id"],
        "status": final_status,
        "mode": metadata["mode"],
        "cwd": metadata["cwd"],
        "model": metadata.get("model"),
        "effort": metadata.get("effort"),
        "task_summary": metadata["task_summary"],
        "pid": process.pid,
        "started_at": metadata["started_at"],
        "finished_at": finished_at,
        "exit_code": process.returncode,
        "session_id": parsed["session_id"],
        "result_text": parsed["result_text"],
    }

    metadata["status"] = final_status
    write_json(metadata_path, metadata)
    write_json(status_path, {
        "worker_id": metadata["worker_id"],
        "status": final_status,
        "pid": process.pid,
        "started_at": metadata["started_at"],
        "finished_at": finished_at,
        "exit_code": process.returncode,
    })
    write_json(run_dir / "result.json", result)
    (run_dir / "summary.txt").write_text(parsed["result_text"] + ("\n" if parsed["result_text"] else ""))

    return process.returncode


def cmd_status(args):
    run_dir = worker_dir(args.worker_id)
    if not run_dir.is_dir():
        raise SystemExit(f"Worker not found: {args.worker_id}")
    print(json.dumps(load_snapshot(run_dir), indent=2, sort_keys=True))


def cmd_result(args):
    run_dir = worker_dir(args.worker_id)
    if not run_dir.is_dir():
        raise SystemExit(f"Worker not found: {args.worker_id}")

    result_path = run_dir / "result.json"
    if not result_path.exists():
        snapshot = load_snapshot(run_dir)
        raise SystemExit(f"Worker is not finished yet. Current status: {snapshot['status']}")

    print(json.dumps(read_json(result_path), indent=2, sort_keys=True))


def cmd_list(_args):
    root = runs_root()
    workers = []
    for run_dir in sorted(root.iterdir(), reverse=True):
        if run_dir.is_dir() and (run_dir / "metadata.json").exists():
            workers.append(load_snapshot(run_dir))
    print(json.dumps(workers, indent=2, sort_keys=True))


def remove_run_dir(run_dir):
    snapshot = load_snapshot(run_dir)
    if snapshot["status"] not in FINAL_STATES:
        raise SystemExit(f"Worker is still active: {snapshot['worker_id']}")
    shutil.rmtree(run_dir)
    return snapshot["worker_id"]


def cmd_cleanup(args):
    removed = []

    if args.worker_id:
        run_dir = worker_dir(args.worker_id)
        if not run_dir.is_dir():
            raise SystemExit(f"Worker not found: {args.worker_id}")
        removed.append(remove_run_dir(run_dir))
    elif args.all_finished:
        root = runs_root()
        for run_dir in sorted(root.iterdir()):
            if not run_dir.is_dir() or not (run_dir / "metadata.json").exists():
                continue
            snapshot = load_snapshot(run_dir)
            if snapshot["status"] in FINAL_STATES:
                shutil.rmtree(run_dir)
                removed.append(snapshot["worker_id"])
    else:
        raise SystemExit("Specify --worker-id or --all-finished.")

    print(json.dumps({"removed": removed}, indent=2, sort_keys=True))


def build_parser():
    parser = argparse.ArgumentParser(
        description="Launch and manage local Claude Code workers."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start", help="Launch a background Claude worker.")
    start.add_argument("--mode", choices=["readonly", "editor"], required=True)
    start.add_argument("--task-file", required=True)
    start.add_argument("--cwd", required=True)
    start.add_argument("--model")
    start.add_argument("--effort", choices=["low", "medium", "high", "max"])
    start.set_defaults(func=cmd_start)

    status = subparsers.add_parser("status", help="Show worker status.")
    status.add_argument("--worker-id", required=True)
    status.set_defaults(func=cmd_status)

    result = subparsers.add_parser("result", help="Show worker result.")
    result.add_argument("--worker-id", required=True)
    result.set_defaults(func=cmd_result)

    listing = subparsers.add_parser("list", help="List workers.")
    listing.set_defaults(func=cmd_list)

    cleanup = subparsers.add_parser("cleanup", help="Remove finished worker runs.")
    cleanup.add_argument("--worker-id")
    cleanup.add_argument("--all-finished", action="store_true")
    cleanup.set_defaults(func=cmd_cleanup)

    runner = subparsers.add_parser("_run", help=argparse.SUPPRESS)
    runner.add_argument("--run-dir", required=True)
    runner.set_defaults(func=cmd_run)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    result = args.func(args)
    if isinstance(result, int):
        sys.exit(result)


if __name__ == "__main__":
    main()
