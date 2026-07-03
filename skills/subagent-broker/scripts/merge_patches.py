#!/usr/bin/env python3
"""Check or apply a policy-approved subagent patch."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def print_process(process: subprocess.CompletedProcess[str]) -> None:
    if process.stdout:
        print(process.stdout, end="")
    if process.stderr:
        print(process.stderr, end="", file=sys.stderr)


def check_patch(patch: Path) -> int:
    process = run_git(["apply", "--check", str(patch)])
    print_process(process)
    return process.returncode


def load_result_for_patch(patch: Path) -> dict[str, object] | None:
    result_path = patch.parent / "result.json"
    if not result_path.exists():
        return None
    with result_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def policy_is_passed(patch: Path) -> tuple[bool, str]:
    result = load_result_for_patch(patch)
    if result is None:
        return False, f"Missing policy result: {patch.parent / 'result.json'}"

    policy = result.get("policy")
    if not isinstance(policy, dict) or policy.get("status") != "passed":
        return False, "Patch policy did not pass"

    patch_path = result.get("patch_path")
    if patch_path:
        recorded = Path(str(patch_path))
        if not recorded.is_absolute():
            recorded = Path.cwd() / recorded
        try:
            if recorded.resolve() != patch.resolve():
                return False, f"Patch path does not match result.json: {patch_path}"
        except OSError as exc:
            return False, f"Could not verify patch path: {exc}"

    return True, "passed"


def apply_patch(patch: Path) -> int:
    passed, message = policy_is_passed(patch)
    if not passed:
        print(message, file=sys.stderr)
        return 2

    check_result = run_git(["apply", "--check", str(patch)])
    if check_result.returncode != 0:
        print_process(check_result)
        return check_result.returncode

    apply_result = run_git(["apply", "--3way", str(patch)])
    print_process(apply_result)
    if apply_result.returncode != 0:
        print(
            "Patch did not apply cleanly. Resolve conflicts manually or regenerate the patch.",
            file=sys.stderr,
        )
    return apply_result.returncode


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check or apply a subagent patch")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", metavar="PATCH")
    group.add_argument("--apply", metavar="PATCH")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    patch = Path(args.check or args.apply)
    if not patch.exists():
        print(f"Patch not found: {patch}", file=sys.stderr)
        return 2
    if args.check:
        return check_patch(patch)
    return apply_patch(patch)


if __name__ == "__main__":
    raise SystemExit(main())
