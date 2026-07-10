#!/usr/bin/env python3
"""Check a unified Git patch against allow/deny path policy."""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from pathlib import PurePosixPath
from typing import Iterable


DIFF_RE = re.compile(r"^diff --git a/(.+?) b/(.+)$")
DEFAULT_DENY = [
    ".env*",
    "**/.env*",
    ".git",
    ".git/**",
    "**/.git",
    "**/.git/**",
    ".subagents",
    ".subagents/**",
    "**/.subagents",
    "**/.subagents/**",
    "secrets/**",
    "**/secrets/**",
]


class PolicyParseError(ValueError):
    pass


def normalize_path(path: str) -> str:
    if not isinstance(path, str) or not path or "\0" in path:
        raise PolicyParseError("Invalid empty or null path")
    if path != path.strip():
        # Leading and trailing spaces are valid Git path bytes and must remain exact.
        path = path
    if path.startswith("/") or re.match(r"^[A-Za-z]:[/\\]", path):
        raise PolicyParseError(f"Absolute path is not allowed: {path}")
    parts = PurePosixPath(path).parts
    if any(part in ("", ".", "..") for part in parts):
        raise PolicyParseError(f"Unsafe relative path is not allowed: {path}")
    return "/".join(parts)


def normalize_diff_path(path: str) -> str:
    path = path.strip()
    if path.startswith("a/") or path.startswith("b/"):
        path = path[2:]
    if path == "/dev/null":
        raise PolicyParseError("Invalid empty or null path")
    return normalize_path(path)


def normalize_pattern(pattern: str) -> str:
    return pattern.strip()


def match_path(path: str, pattern: str) -> bool:
    pattern = normalize_pattern(pattern)
    path_parts = path.split("/")
    pattern_parts = pattern.split("/")

    def matches(path_index: int, pattern_index: int) -> bool:
        if pattern_index == len(pattern_parts):
            return path_index == len(path_parts)
        part = pattern_parts[pattern_index]
        if part == "**":
            return matches(path_index, pattern_index + 1) or (
                path_index < len(path_parts) and matches(path_index + 1, pattern_index)
            )
        return (
            path_index < len(path_parts)
            and fnmatch.fnmatchcase(path_parts[path_index], part)
            and matches(path_index + 1, pattern_index + 1)
        )

    return matches(0, 0)


def parse_diff_paths(diff_text: str) -> tuple[list[str], bool, bool, list[str]]:
    changed: set[str] = set()
    binary = False
    deleted = False
    violations: list[str] = []
    current_paths: set[str] = set()

    def add_path(raw_path: str) -> None:
        try:
            changed.add(normalize_path(raw_path))
        except PolicyParseError as exc:
            violations.append(str(exc))

    for line in diff_text.splitlines():
        match = DIFF_RE.match(line)
        if match:
            current_paths = set()
            for raw_path in match.groups():
                try:
                    path = normalize_diff_path(raw_path)
                except PolicyParseError as exc:
                    violations.append(str(exc))
                    continue
                changed.add(path)
                current_paths.add(path)
            continue

        if line.startswith("rename from "):
            add_path(line.removeprefix("rename from "))
            continue

        if line.startswith("rename to "):
            add_path(line.removeprefix("rename to "))
            continue

        if line.startswith("deleted file mode"):
            deleted = True
            continue

        if line == "GIT binary patch" or line.startswith("Binary files "):
            binary = True
            continue

        if line.startswith("--- ") or line.startswith("+++ "):
            marker_path = line[4:].split("\t", 1)[0]
            if marker_path == "/dev/null":
                if line.startswith("+++ "):
                    deleted = True
                continue
            try:
                path = normalize_diff_path(marker_path)
            except PolicyParseError as exc:
                violations.append(str(exc))
                continue
            changed.add(path)
            current_paths.add(path)

    if diff_text.strip() and not changed:
        violations.append("Patch did not contain parseable changed paths")

    return sorted(changed), binary, deleted, violations


def check_paths(
    paths: Iterable[str],
    allowed_paths: Iterable[str],
    deny_paths: Iterable[str],
) -> dict[str, object]:
    changed: set[str] = set()
    violations: list[str] = []
    for raw_path in paths:
        try:
            changed.add(normalize_path(raw_path))
        except PolicyParseError as exc:
            violations.append(str(exc))

    allowed = [normalize_pattern(pattern) for pattern in allowed_paths]
    denied = [normalize_pattern(pattern) for pattern in [*DEFAULT_DENY, *deny_paths]]
    changed_files = sorted(changed)
    if not allowed and changed_files:
        violations.append("No allowed paths were provided")
    for path in changed_files:
        if any(match_path(path, pattern) for pattern in denied):
            violations.append(f"Denied path modified: {path}")
        elif not any(match_path(path, pattern) for pattern in allowed):
            violations.append(f"Path outside allowed paths: {path}")

    deduped = list(dict.fromkeys(violations))
    return {
        "status": "failed" if deduped else "passed",
        "changed_files": changed_files,
        "violations": deduped,
    }


def check_policy(
    diff_text: str | bytes,
    allowed_paths: Iterable[str],
    deny_paths: Iterable[str],
    allow_binary_changes: bool = False,
    allow_deletes: bool = False,
    changed_paths: Iterable[str] | None = None,
    has_binary_changes: bool | None = None,
    has_deletes: bool | None = None,
) -> dict[str, object]:
    decoded = diff_text.decode("latin-1") if isinstance(diff_text, bytes) else diff_text
    if changed_paths is None:
        changed_files, has_binary, has_deletes, violations = parse_diff_paths(decoded)
    else:
        changed_files = list(changed_paths)
        has_binary = bool(has_binary_changes)
        has_deletes = bool(has_deletes)
        violations = []
    path_result = check_paths(changed_files, allowed_paths, deny_paths)
    violations.extend(path_result["violations"])

    if has_binary and not allow_binary_changes:
        violations.append("Binary file changes are not allowed")
    if has_deletes and not allow_deletes:
        violations.append("File deletions are not allowed")

    deduped: list[str] = []
    seen: set[str] = set()
    for violation in violations:
        if violation not in seen:
            deduped.append(violation)
            seen.add(violation)

    return {
        "status": "failed" if deduped else "passed",
        "changed_files": changed_files,
        "violations": deduped,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check a patch against path policy")
    parser.add_argument("--patch", required=True, help="Patch file to check")
    parser.add_argument("--allowed", action="append", default=[], help="Allowed glob pattern")
    parser.add_argument("--deny", action="append", default=[], help="Denied glob pattern")
    parser.add_argument("--allow-binary-changes", action="store_true")
    parser.add_argument("--allow-deletes", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        with open(args.patch, "rb") as handle:
            diff_text = handle.read()
        result = check_policy(
            diff_text,
            args.allowed,
            args.deny,
            allow_binary_changes=args.allow_binary_changes,
            allow_deletes=args.allow_deletes,
        )
    except OSError as exc:
        result = {
            "status": "failed",
            "changed_files": [],
            "violations": [f"Could not read patch: {exc}"],
        }
        print(json.dumps(result, indent=2, sort_keys=True), flush=True)
        return 2

    print(json.dumps(result, indent=2, sort_keys=True), flush=True)
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
