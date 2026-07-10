#!/usr/bin/env python3
"""Check or apply a policy-approved subagent patch."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FileState:
    mode: str
    sha256: str


def run_git(
    args: list[str],
    cwd: Path,
    *,
    input_bytes: bytes | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        env=env,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def process_message(process: subprocess.CompletedProcess[bytes]) -> str:
    return (process.stderr or process.stdout).decode("utf-8", errors="replace").strip()


def print_process(process: subprocess.CompletedProcess[bytes]) -> None:
    if process.stdout:
        print(process.stdout.decode("utf-8", errors="replace"), end="")
    if process.stderr:
        print(process.stderr.decode("utf-8", errors="replace"), end="", file=sys.stderr)


def find_git_root(cwd: Path) -> Path | None:
    process = run_git(["rev-parse", "--show-toplevel"], cwd)
    if process.returncode != 0:
        return None
    return Path(os.fsdecode(process.stdout).strip()).resolve()


def load_result_for_patch(patch: Path) -> dict[str, object] | None:
    result_path = patch.parent / "result.json"
    if not result_path.exists():
        return None
    with result_path.open("r", encoding="utf-8") as handle:
        loaded = json.load(handle)
    return loaded if isinstance(loaded, dict) else None


def working_tree_state(root: Path, path: str) -> FileState | None:
    target = root / path
    if not os.path.lexists(target):
        return None
    if target.is_symlink():
        mode = "120000"
        data = os.fsencode(os.readlink(target))
        return FileState(mode, hashlib.sha256(data).hexdigest())
    if not target.is_file():
        raise ValueError(f"current path is not a regular file or symlink: {path}")
    mode = "100755" if stat.S_IMODE(target.stat().st_mode) & 0o111 else "100644"
    return FileState(mode, hashlib.sha256(target.read_bytes()).hexdigest())


def verify_baseline(result: dict[str, object], patch: Path, repo_root: Path) -> tuple[bool, str]:
    baseline = result.get("baseline_commit")
    if not isinstance(baseline, str) or not baseline:
        return False, "Missing baseline_commit in result.json"
    manifest_path = patch.parent / "baseline_manifest.json"
    if not manifest_path.exists():
        return False, f"Missing baseline manifest: {manifest_path}"
    manifest_bytes = manifest_path.read_bytes()
    expected_manifest_hash = result.get("baseline_manifest_sha256")
    if (
        not isinstance(expected_manifest_hash, str)
        or hashlib.sha256(manifest_bytes).hexdigest() != expected_manifest_hash
    ):
        return False, "Baseline manifest SHA-256 does not match result.json"
    try:
        manifest = json.loads(manifest_bytes)
    except json.JSONDecodeError as exc:
        return False, f"Invalid baseline manifest: {exc}"
    files = manifest.get("files") if isinstance(manifest, dict) else None
    if not isinstance(files, dict):
        return False, "Invalid baseline manifest files"
    policy = result.get("policy")
    changed_files = policy.get("changed_files") if isinstance(policy, dict) else None
    if not isinstance(changed_files, list) or not all(isinstance(path, str) for path in changed_files):
        return False, "Missing changed_files in policy result"
    try:
        for path in changed_files:
            raw_expected = files.get(path)
            if raw_expected is None:
                expected = None
            elif (
                isinstance(raw_expected, dict)
                and isinstance(raw_expected.get("mode"), str)
                and isinstance(raw_expected.get("sha256"), str)
            ):
                expected = FileState(raw_expected["mode"], raw_expected["sha256"])
            else:
                return False, f"Invalid baseline manifest entry: {path}"
            if expected != working_tree_state(repo_root, path):
                return False, f"Working tree changed since the subagent baseline: {path}"
    except (OSError, ValueError) as exc:
        return False, str(exc)
    return True, "passed"


def verify_artifact(
    patch: Path,
    patch_bytes: bytes,
    repo_root: Path,
) -> tuple[bool, str]:
    result = load_result_for_patch(patch)
    if result is None:
        return False, f"Missing policy result: {patch.parent / 'result.json'}"
    if result.get("status") != "completed":
        return False, f"Subagent result is not completed: {result.get('status')}"
    source_repo_root = result.get("source_repo_root")
    if not isinstance(source_repo_root, str) or not Path(source_repo_root).is_absolute():
        return False, "Missing absolute source_repo_root in result.json"
    if Path(source_repo_root).resolve() != repo_root.resolve():
        return False, "Patch must be checked or applied from its original source repository"
    policy = result.get("policy")
    if not isinstance(policy, dict) or policy.get("status") != "passed":
        return False, "Patch policy did not pass"

    expected_hash = result.get("patch_sha256")
    actual_hash = hashlib.sha256(patch_bytes).hexdigest()
    if not isinstance(expected_hash, str) or expected_hash != actual_hash:
        return False, "Patch SHA-256 does not match result.json"

    recorded_path = result.get("patch_path")
    if not isinstance(recorded_path, str) or Path(recorded_path).name != patch.name:
        return False, "Patch path does not match result.json"
    return verify_baseline(result, patch, repo_root)


def check_patch(patch: Path, repo_root: Path, patch_bytes: bytes) -> int:
    passed, message = verify_artifact(patch, patch_bytes, repo_root)
    if not passed:
        print(message, file=sys.stderr)
        return 2
    process = run_git(["apply", "--check", "-"], repo_root, input_bytes=patch_bytes)
    print_process(process)
    if process.returncode == 0:
        result = load_result_for_patch(patch) or {}
        files = result.get("files_changed")
        count = len(files) if isinstance(files, list) else 0
        print(f"Patch check passed: {count} files; policy passed; baseline unchanged")
    return process.returncode


def apply_patch(patch: Path, repo_root: Path, patch_bytes: bytes) -> int:
    passed, message = verify_artifact(patch, patch_bytes, repo_root)
    if not passed:
        print(message, file=sys.stderr)
        return 2

    check_result = run_git(["apply", "--check", "-"], repo_root, input_bytes=patch_bytes)
    if check_result.returncode != 0:
        print_process(check_result)
        return check_result.returncode

    apply_result = run_git(["apply", "-"], repo_root, input_bytes=patch_bytes)
    print_process(apply_result)
    if apply_result.returncode != 0:
        print("Patch did not apply cleanly. Regenerate it against the current working tree.", file=sys.stderr)
    else:
        result = load_result_for_patch(patch) or {}
        files = result.get("files_changed")
        count = len(files) if isinstance(files, list) else 0
        print(f"Patch applied: {count} files")
    return apply_result.returncode


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check or apply a subagent patch")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", metavar="PATCH")
    group.add_argument("--apply", metavar="PATCH")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    patch = Path(args.check or args.apply).resolve()
    if not patch.exists():
        print(f"Patch not found: {patch}", file=sys.stderr)
        return 2
    repo_root = find_git_root(Path.cwd())
    if repo_root is None:
        print("Current directory is not inside a Git repository", file=sys.stderr)
        return 2
    patch_bytes = patch.read_bytes()
    if args.check:
        return check_patch(patch, repo_root, patch_bytes)
    return apply_patch(patch, repo_root, patch_bytes)


if __name__ == "__main__":
    raise SystemExit(main())
