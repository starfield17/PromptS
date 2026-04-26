#!/usr/bin/env python3
"""Run Claude Code subagent task files concurrently."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run_one(task_file: Path, script: Path, runtime_root: Path, timeout: int | None) -> Dict[str, object]:
    env = os.environ.copy()
    cmd = [str(script), str(task_file), str(runtime_root)]
    try:
        completed = subprocess.run(cmd, env=env, text=True, capture_output=True, timeout=timeout)
        return {
            "task_id": task_file.stem,
            "task_file": str(task_file),
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "run_dir": str(runtime_root / "runs" / task_file.stem),
        }
    except subprocess.TimeoutExpired as exc:
        task_out = runtime_root / "runs" / task_file.stem
        task_out.mkdir(parents=True, exist_ok=True)
        (task_out / "timeout.txt").write_text(f"Timed out after {timeout} seconds\n", encoding="utf-8")
        return {
            "task_id": task_file.stem,
            "task_file": str(task_file),
            "returncode": 124,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or f"timed out after {timeout} seconds",
            "run_dir": str(task_out),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Claude Code subagent tasks in parallel.")
    parser.add_argument("tasks_dir", help="Directory containing .md task files")
    parser.add_argument("--max-workers", type=int, default=int(os.getenv("CLAUDE_SUBAGENT_MAX_WORKERS", "4")))
    parser.add_argument("--runtime-root", "--out-dir", dest="runtime_root", default=os.getenv("CLAUDE_SUBAGENT_ROOT", ".CC_subagent"))
    parser.add_argument("--timeout", type=int, default=int(os.getenv("CLAUDE_SUBAGENT_TIMEOUT", "0")), help="Per-task timeout in seconds; 0 disables timeout")
    parser.add_argument("--script", default=None, help="Path to run_subagent.sh")
    args = parser.parse_args()

    if args.max_workers < 1:
        print("--max-workers must be at least 1", file=sys.stderr)
        return 2

    tasks_dir = Path(args.tasks_dir)
    if not tasks_dir.is_dir():
        print(f"tasks directory not found: {tasks_dir}", file=sys.stderr)
        return 2

    task_files = sorted(tasks_dir.glob("*.md"))
    if not task_files:
        print(f"no .md task files found in: {tasks_dir}", file=sys.stderr)
        return 2

    task_ids = [task_file.stem for task_file in task_files]
    duplicates = sorted({task_id for task_id in task_ids if task_ids.count(task_id) > 1})
    if duplicates:
        print(f"duplicate task ids detected: {', '.join(duplicates)}", file=sys.stderr)
        return 2

    runtime_root = Path(args.runtime_root)
    runtime_root.mkdir(parents=True, exist_ok=True)

    script = Path(args.script) if args.script else Path(__file__).with_name("run_subagent.sh")
    if not script.exists():
        print(f"run_subagent.sh not found: {script}", file=sys.stderr)
        return 2

    collector = Path(__file__).with_name("collect_results.py")
    timeout = args.timeout or None
    results: List[Dict[str, object]] = []
    started_at = utc_now()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_workers) as pool:
        futures = [pool.submit(run_one, task_file, script, runtime_root, timeout) for task_file in task_files]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            results.append(result)
            print(f"[{result['task_id']}] exit={result['returncode']}")

    index: Dict[str, Any] = {
        "runtime_root": str(runtime_root),
        "started_at": started_at,
        "finished_at": utc_now(),
        "task_count": len(task_files),
        "results": sorted(results, key=lambda item: str(item["task_id"])),
    }
    (runtime_root / "index.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")

    if collector.exists():
        subprocess.run([sys.executable, str(collector), str(runtime_root)], check=False)

    return 0 if all(int(item["returncode"]) == 0 for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
