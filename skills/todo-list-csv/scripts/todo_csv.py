#!/usr/bin/env python3
"""
CSV TODO tracker for the `todo-list-csv` skill.

Create a "{任务名} TO DO list.csv" file in the project root, mark rows DONE as work completes,
and delete the file when everything is finished.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


CSV_HEADER = ["id", "item", "status", "done_at", "notes"]
STATUS_TODO = "TODO"
STATUS_IN_PROGRESS = "IN_PROGRESS"
STATUS_DONE = "DONE"


def _now_iso() -> str:
    return dt.datetime.now().astimezone().replace(microsecond=0).isoformat()


def _sanitize_title(title: str, *, max_len: int = 80) -> str:
    cleaned = title.strip()
    cleaned = cleaned.replace(os.sep, "-")
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"[<>]", "", cleaned)
    cleaned = cleaned.strip(" .-_")
    if not cleaned:
        cleaned = "Task"
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len].rstrip(" .-_")
    return cleaned or "Task"


def _git_root(cwd: Path) -> Path | None:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(cwd),
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return Path(out) if out else None
    except Exception:
        return None


def _project_root(explicit_root: str | None) -> Path:
    if explicit_root:
        return Path(explicit_root).resolve()
    return _git_root(Path.cwd()) or Path.cwd().resolve()


def _todo_csv_path(*, title: str, root: Path) -> Path:
    safe_title = _sanitize_title(title)
    return root / f"{safe_title} TO DO list.csv"


def _is_int(value: str) -> bool:
    try:
        int(value)
        return True
    except Exception:
        return False


def _sorted_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    with_id = [r for r in rows if _is_int(str(r.get("id", "")).strip())]
    without_id = [r for r in rows if r not in with_id]
    with_id.sort(key=lambda r: int(str(r.get("id", "")).strip()))
    return with_id + without_id


def _ensure_single_in_progress(
    rows: list[dict[str, str]],
    *,
    promote_first_todo: bool,
) -> tuple[list[dict[str, str]], bool]:
    """
    Enforce: at most one IN_PROGRESS row.
    Optionally promote the first TODO row to IN_PROGRESS when none exist.
    """
    changed = False
    rows = _sorted_rows(rows)

    in_progress_indices = [i for i, r in enumerate(rows) if r.get("status") == STATUS_IN_PROGRESS]
    if len(in_progress_indices) > 1:
        keep_idx = in_progress_indices[0]
        for i in in_progress_indices[1:]:
            rows[i]["status"] = STATUS_TODO
            rows[i]["done_at"] = ""
            changed = True
        # Ensure kept row does not have a done timestamp.
        if rows[keep_idx].get("done_at"):
            rows[keep_idx]["done_at"] = ""
            changed = True

    if not in_progress_indices and promote_first_todo:
        for r in rows:
            if r.get("status") == STATUS_TODO:
                r["status"] = STATUS_IN_PROGRESS
                r["done_at"] = ""
                changed = True
                break

    return rows, changed


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != CSV_HEADER:
            raise ValueError(
                f"Unexpected CSV header in {path}: {reader.fieldnames!r} (expected {CSV_HEADER!r})"
            )
        return [dict(row) for row in reader]


def _atomic_write(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        newline="",
        delete=False,
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
    ) as tmp:
        tmp_path = Path(tmp.name)
        writer = csv.DictWriter(tmp, fieldnames=CSV_HEADER)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in CSV_HEADER})
    tmp_path.replace(path)


def cmd_path(args: argparse.Namespace) -> int:
    root = _project_root(args.root)
    print(_todo_csv_path(title=args.title, root=root))
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    root = _project_root(args.root)
    path = Path(args.file).resolve() if args.file else _todo_csv_path(title=args.title, root=root)
    if path.exists() and not args.force:
        print(f"Refusing to overwrite existing file: {path}", file=sys.stderr)
        return 2

    rows: list[dict[str, str]] = []
    for idx, item in enumerate(args.item, start=1):
        status = STATUS_TODO
        if idx == 1 and not args.no_in_progress:
            status = STATUS_IN_PROGRESS
        rows.append(
            {
                "id": str(idx),
                "item": item.strip(),
                "status": status,
                "done_at": "",
                "notes": "",
            }
        )

    _atomic_write(path, rows)
    print(path)
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    path = Path(args.file).resolve()
    if not path.exists():
        print(f"CSV not found: {path}", file=sys.stderr)
        return 2

    rows = _read_rows(path)
    next_id = 1
    for row in rows:
        try:
            next_id = max(next_id, int(row["id"]) + 1)
        except Exception:
            pass

    for item in args.item:
        rows.append(
            {
                "id": str(next_id),
                "item": item.strip(),
                "status": STATUS_TODO,
                "done_at": "",
                "notes": "",
            }
        )
        next_id += 1

    _atomic_write(path, rows)
    return 0


def _mark(
    path: Path,
    *,
    item_id: int,
    status: str,
    notes: str | None,
    require_current_status: set[str] | None,
) -> int:
    if not path.exists():
        print(f"CSV not found: {path}", file=sys.stderr)
        return 2

    rows = _read_rows(path)
    updated = False
    for row in rows:
        if row.get("id") == str(item_id):
            current = row.get("status", "")
            if require_current_status is not None and current not in require_current_status:
                print(
                    f"Refusing status transition for id={item_id}: {current} -> {status}",
                    file=sys.stderr,
                )
                print(f"Allowed current status: {sorted(require_current_status)}", file=sys.stderr)
                return 2
            row["status"] = status
            row["done_at"] = _now_iso() if status == STATUS_DONE else ""
            if notes is not None:
                row["notes"] = notes
            updated = True
            break

    if not updated:
        print(f"id not found: {item_id}", file=sys.stderr)
        return 2

    _atomic_write(path, rows)
    return 0


def cmd_done(args: argparse.Namespace) -> int:
    require = None if args.force else {STATUS_IN_PROGRESS}
    return _mark(
        Path(args.file).resolve(),
        item_id=args.id,
        status=STATUS_DONE,
        notes=args.notes,
        require_current_status=require,
    )


def cmd_todo(args: argparse.Namespace) -> int:
    return _mark(
        Path(args.file).resolve(),
        item_id=args.id,
        status=STATUS_TODO,
        notes=args.notes,
        require_current_status=None,
    )


def cmd_start(args: argparse.Namespace) -> int:
    path = Path(args.file).resolve()
    if not path.exists():
        print(f"CSV not found: {path}", file=sys.stderr)
        return 2

    rows = _sorted_rows(_read_rows(path))
    target = next((r for r in rows if r.get("id") == str(args.id)), None)
    if target is None:
        print(f"id not found: {args.id}", file=sys.stderr)
        return 2

    if target.get("status") == STATUS_DONE and not args.force:
        print(
            f"Refusing to start DONE item (id={args.id}). Use `todo` first or pass --force.",
            file=sys.stderr,
        )
        return 2

    changed = False
    for row in rows:
        if row.get("status") == STATUS_IN_PROGRESS and row.get("id") != str(args.id):
            row["status"] = STATUS_TODO
            row["done_at"] = ""
            changed = True

    if target.get("status") != STATUS_IN_PROGRESS:
        target["status"] = STATUS_IN_PROGRESS
        target["done_at"] = ""
        changed = True

    if args.notes is not None:
        target["notes"] = args.notes
        changed = True

    if changed:
        _atomic_write(path, rows)
    return 0


def cmd_advance(args: argparse.Namespace) -> int:
    path = Path(args.file).resolve()
    if not path.exists():
        print(f"CSV not found: {path}", file=sys.stderr)
        return 2

    rows = _sorted_rows(_read_rows(path))
    current_idx = next((i for i, r in enumerate(rows) if r.get("status") == STATUS_IN_PROGRESS), None)
    if current_idx is None:
        print("No IN_PROGRESS item found; run `start` first.", file=sys.stderr)
        return 2

    current = rows[current_idx]
    current["status"] = STATUS_DONE
    current["done_at"] = _now_iso()
    if args.notes is not None:
        current["notes"] = args.notes

    next_row = next((r for r in rows[current_idx + 1 :] if r.get("status") == STATUS_TODO), None)
    if next_row is not None:
        next_row["status"] = STATUS_IN_PROGRESS
        next_row["done_at"] = ""

    _atomic_write(path, rows)
    return 0


def _plan_status_for_csv_status(status: str) -> str:
    if status == STATUS_DONE:
        return "completed"
    if status == STATUS_IN_PROGRESS:
        return "in_progress"
    return "pending"


def cmd_plan(args: argparse.Namespace) -> int:
    path = Path(args.file).resolve()
    if not path.exists():
        print(f"CSV not found: {path}", file=sys.stderr)
        return 2

    rows_original = _sorted_rows(_read_rows(path))
    rows_for_plan, changed = _ensure_single_in_progress(
        [dict(r) for r in rows_original],
        promote_first_todo=args.normalize,
    )
    if args.normalize and changed:
        _atomic_write(path, rows_for_plan)

    # Ensure plan output always has a single in_progress when there are pending items.
    if not any(r.get("status") == STATUS_IN_PROGRESS for r in rows_for_plan) and any(
        r.get("status") == STATUS_TODO for r in rows_for_plan
    ):
        for r in rows_for_plan:
            if r.get("status") == STATUS_TODO:
                r["status"] = STATUS_IN_PROGRESS
                r["done_at"] = ""
                break

    payload = {
        "explanation": args.explanation or "",
        "plan": [
            {
                "step": str(r.get("item", "")).strip(),
                "status": _plan_status_for_csv_status(str(r.get("status", "")).strip()),
            }
            for r in rows_for_plan
            if str(r.get("item", "")).strip()
        ],
    }
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    path = Path(args.file).resolve()
    if not path.exists():
        print(f"CSV not found: {path}", file=sys.stderr)
        return 2

    rows = _read_rows(path)
    total = len(rows)
    done = sum(1 for r in rows if r.get("status") == STATUS_DONE)
    in_progress = next((r for r in rows if r.get("status") == STATUS_IN_PROGRESS), None)
    suffix = f" (IN_PROGRESS: {in_progress.get('id')})" if in_progress else ""
    print(f"{done}/{total} DONE{suffix}")
    if args.verbose:
        for r in rows:
            print(f'{r.get("id")}. [{r.get("status")}] {r.get("item")}')
    return 0


def cmd_cleanup(args: argparse.Namespace) -> int:
    path = Path(args.file).resolve()
    if not path.exists():
        return 0

    rows = _read_rows(path)
    if not rows:
        path.unlink(missing_ok=True)
        return 0

    if all(r.get("status") == STATUS_DONE for r in rows):
        path.unlink(missing_ok=True)
        return 0

    print("Not all items are DONE; refusing to delete.", file=sys.stderr)
    return 2


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="todo_csv.py")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_path = sub.add_parser("path", help="Print the expected CSV path for a task title.")
    p_path.add_argument("--title", required=True)
    p_path.add_argument("--root", help="Project root override (default: git root or cwd).")
    p_path.set_defaults(fn=cmd_path)

    p_init = sub.add_parser("init", help="Create a new TODO CSV.")
    p_init.add_argument("--title", help="Task title (used to derive the filename).")
    p_init.add_argument("--file", help="Explicit CSV path (overrides --title).")
    p_init.add_argument("--root", help="Project root override (default: git root or cwd).")
    p_init.add_argument("--force", action="store_true", help="Overwrite if exists.")
    p_init.add_argument(
        "--no-in-progress",
        action="store_true",
        help="Do not set the first item to IN_PROGRESS (default: first item is IN_PROGRESS).",
    )
    p_init.add_argument("--item", nargs="+", default=[], help="One or more TODO items.")
    p_init.set_defaults(fn=cmd_init)

    p_add = sub.add_parser("add", help="Append TODO items.")
    p_add.add_argument("--file", required=True)
    p_add.add_argument("--item", nargs="+", required=True)
    p_add.set_defaults(fn=cmd_add)

    p_start = sub.add_parser("start", help="Set exactly one item as IN_PROGRESS.")
    p_start.add_argument("--file", required=True)
    p_start.add_argument("--id", type=int, required=True)
    p_start.add_argument("--notes")
    p_start.add_argument("--force", action="store_true", help="Allow starting a DONE item (clears done_at).")
    p_start.set_defaults(fn=cmd_start)

    p_done = sub.add_parser("done", help="Mark an item as DONE.")
    p_done.add_argument("--file", required=True)
    p_done.add_argument("--id", type=int, required=True)
    p_done.add_argument("--notes")
    p_done.add_argument(
        "--force",
        action="store_true",
        help="Allow marking TODO directly to DONE (not recommended).",
    )
    p_done.set_defaults(fn=cmd_done)

    p_todo = sub.add_parser("todo", help="Mark an item back to TODO.")
    p_todo.add_argument("--file", required=True)
    p_todo.add_argument("--id", type=int, required=True)
    p_todo.add_argument("--notes")
    p_todo.set_defaults(fn=cmd_todo)

    p_advance = sub.add_parser("advance", help="Mark current IN_PROGRESS as DONE and start the next TODO.")
    p_advance.add_argument("--file", required=True)
    p_advance.add_argument("--notes")
    p_advance.set_defaults(fn=cmd_advance)

    p_plan = sub.add_parser("plan", help="Print an update_plan-compatible JSON payload derived from the CSV.")
    p_plan.add_argument("--file", required=True)
    p_plan.add_argument("--explanation")
    p_plan.add_argument(
        "--normalize",
        action="store_true",
        help="Normalize the CSV to have a single IN_PROGRESS (and promote the first TODO if none).",
    )
    p_plan.set_defaults(fn=cmd_plan)

    p_status = sub.add_parser("status", help="Show progress summary.")
    p_status.add_argument("--file", required=True)
    p_status.add_argument("--verbose", action="store_true")
    p_status.set_defaults(fn=cmd_status)

    p_cleanup = sub.add_parser("cleanup", help="Delete CSV if all items are DONE.")
    p_cleanup.add_argument("--file", required=True)
    p_cleanup.set_defaults(fn=cmd_cleanup)

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.cmd == "init" and not args.file and not args.title:
        parser.error("init requires either --file or --title")

    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
