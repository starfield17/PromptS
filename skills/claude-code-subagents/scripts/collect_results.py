#!/usr/bin/env python3
"""Collect Claude Code subagent result summaries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


def load_status(path: Path) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("status.json root is not an object")
        return data
    except Exception as exc:
        return {
            "task_id": path.parent.name,
            "role": "unknown",
            "state": "finished",
            "status": "failed",
            "summary": f"Could not parse status.json: {exc}",
            "confidence": "low",
            "files_touched": [],
            "tests_run": [],
            "tests_passed": None,
            "blocking_issues": [f"status.json could not be parsed: {exc}"],
            "follow_up_recommendations": ["Inspect stderr.log and events.jsonl for the failed task."],
            "workspace_mode": "unknown",
            "workspace_path": "",
            "started_at": None,
            "finished_at": None,
            "exit_code": None,
        }


def load_changed_files(path: Path) -> List[str]:
    if not path.is_file():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect Claude Code subagent results into summary files.")
    parser.add_argument("out_dir", nargs="?", default=".CC_subagent")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    statuses: List[Dict[str, Any]] = []
    for status_file in sorted(out_dir.glob("*/status.json")):
        statuses.append(load_status(status_file))
    for status_file in sorted(out_dir.glob("runs/*/status.json")):
        statuses.append(load_status(status_file))

    deduped: Dict[str, Dict[str, Any]] = {}
    for item in statuses:
        deduped[str(item.get("task_id", ""))] = item
    statuses = sorted(deduped.values(), key=lambda item: str(item.get("task_id", "")))

    collisions: Dict[str, List[str]] = {}
    for item in statuses:
        task_id = str(item.get("task_id", ""))
        changed_files = load_changed_files(out_dir / "runs" / task_id / "changed-files.txt")
        for changed_file in changed_files:
            collisions.setdefault(changed_file, []).append(task_id)

    collision_rows = {
        changed_file: sorted(task_ids)
        for changed_file, task_ids in collisions.items()
        if len(set(task_ids)) > 1
    }

    warnings: List[str] = []
    for item in statuses:
        if item.get("status") in {"failed", "blocked", "timeout"}:
            warnings.append(
                f"Task `{item.get('task_id', '')}` ended with status `{item.get('status', '')}`."
            )
    for changed_file, task_ids in sorted(collision_rows.items()):
        warnings.append(
            f"File collision on `{changed_file}` across tasks: {', '.join(task_ids)}."
        )

    lines: List[str] = ["# Subagent Run Summary", ""]
    if not statuses:
        lines.append("No subagent status files found.")
    else:
        lines.extend([
            "| Task | Role | State | Status | Mode | Files | Confidence | Summary |",
            "|---|---|---|---|---|---:|---|---|",
        ])
        for item in statuses:
            files_count = len(load_changed_files(out_dir / "runs" / str(item.get("task_id", "")) / "changed-files.txt"))
            lines.append(
                f"| {item.get('task_id', '')} | {item.get('role', '')} | {item.get('state', '')} | {item.get('status', '')} | {item.get('workspace_mode', '')} | {files_count} | {item.get('confidence', '')} | {str(item.get('summary', '')).replace('|', '/')} |"
            )
        lines.extend(["", "## Warnings", ""])
        if warnings:
            lines.extend(f"- {warning}" for warning in warnings)
        else:
            lines.append("- No task-level failures or file collisions detected.")

        lines.extend(["", "## File Collisions", ""])
        if collision_rows:
            lines.extend([
                "| File | Tasks |",
                "|---|---|",
            ])
            for changed_file, task_ids in sorted(collision_rows.items()):
                lines.append(f"| {changed_file} | {', '.join(task_ids)} |")
        else:
            lines.append("No overlapping file touches detected.")

        lines.extend(["", "## Recommended Codex actions", ""])
        lines.append("- Inspect each `result.md`, `events.jsonl`, `stderr.log`, and `patch.diff` before applying changes.")
        lines.append("- Treat `status.json` as a summary surface, not as final truth.")
        lines.append("- If collisions exist, resolve them manually or launch a focused reviewer task.")

    summary_path = out_dir / "summary.md"
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    summary_json = {
        "runtime_root": str(out_dir),
        "task_count": len(statuses),
        "tasks": statuses,
        "collisions": collision_rows,
        "warnings": warnings,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary_json, indent=2) + "\n", encoding="utf-8")
    print(summary_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
