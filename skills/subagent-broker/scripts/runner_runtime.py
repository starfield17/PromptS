#!/usr/bin/env python3
"""Workspace isolation and bounded subprocess execution for the broker."""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import os
import shutil
import signal
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from harness_adapters import HarnessInvocation
from policy_check import match_path


class RunnerRuntimeError(Exception):
    pass


EventWriter = Callable[..., None]


@dataclass(frozen=True)
class WorkspaceContext:
    repo_root: Path | None
    worktree: Path | None
    harness_cwd: Path
    baseline_commit: str | None
    baseline_manifest_sha256: str | None
    baseline_bundle_path: Path | None
    baseline_bundle_sha256: str | None
    worktree_identity: tuple[int, int]


@dataclass(frozen=True)
class ProcessOutcome:
    returncode: int | None
    stdout: str
    stderr: str
    error_kind: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class PatchArtifact:
    data: bytes
    changed_paths: tuple[str, ...]
    has_binary_changes: bool
    has_deletes: bool


@dataclass(frozen=True)
class _CapturedStream:
    data: bytes
    total_bytes: int
    truncated: bool


def run_sync(
    args: list[str],
    cwd: Path,
    *,
    env: dict[str, str] | None = None,
    input_bytes: bytes | None = None,
) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            args,
            cwd=str(cwd),
            env=env,
            input=input_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except FileNotFoundError:
        return subprocess.CompletedProcess(args, 127, b"", f"Command not found: {args[0]}".encode())


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Replace an artifact without following a destination symlink."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise RunnerRuntimeError(f"refusing to write symlink output: {path}")
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def append_bytes_no_follow(path: Path, data: bytes) -> None:
    """Append an event record without following a destination symlink."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise RunnerRuntimeError(f"refusing to append to symlink output: {path}")
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError as exc:
        raise RunnerRuntimeError(f"could not safely append output {path}: {exc}") from exc
    with os.fdopen(descriptor, "ab") as handle:
        handle.write(data)


def _process_error(process: subprocess.CompletedProcess[bytes]) -> str:
    return (process.stderr or process.stdout).decode("utf-8", errors="replace").strip()


def git_root(cwd: Path) -> Path | None:
    process = run_sync(["git", "rev-parse", "--show-toplevel"], cwd)
    if process.returncode != 0:
        return None
    return Path(os.fsdecode(process.stdout).strip()).resolve()


def _git_output(args: list[str], cwd: Path, *, env: dict[str, str] | None = None) -> bytes:
    process = run_sync(["git", *args], cwd, env=env)
    if process.returncode != 0:
        raise RunnerRuntimeError(_process_error(process) or f"git {' '.join(args)} failed")
    return process.stdout


def _nul_paths(data: bytes) -> list[str]:
    return [os.fsdecode(item) for item in data.split(b"\0") if item]


def git_changed_paths(cwd: Path, baseline: str) -> list[str]:
    trusted_env = _trusted_worktree_env(cwd)
    tracked = _nul_paths(
        _git_output(
            ["diff", "--no-renames", "--name-only", "-z", baseline, "--"],
            cwd,
            env=trusted_env,
        )
    )
    untracked = _nul_paths(
        _git_output(
            ["ls-files", "--others", "--exclude-standard", "-z", "--"],
            cwd,
            env=trusted_env,
        )
    )
    return sorted(set([*tracked, *untracked]))


def _is_denied(path: str, deny_patterns: list[str]) -> bool:
    normalized = path.replace(os.sep, "/")
    return any(match_path(normalized, pattern) for pattern in deny_patterns)


def _pathspec_input(paths: list[str]) -> bytes:
    return b"".join(os.fsencode(path) + b"\0" for path in paths)


def _remove_path(path: Path) -> None:
    if not os.path.lexists(path):
        return
    if path.is_symlink() or not path.is_dir():
        path.unlink()
    else:
        shutil.rmtree(path)


def _directory_identity(path: Path) -> tuple[int, int]:
    metadata = path.lstat()
    if path.is_symlink() or not stat.S_ISDIR(metadata.st_mode):
        raise RunnerRuntimeError(f"workspace root is not a real directory: {path}")
    return metadata.st_dev, metadata.st_ino


def verify_workspace_identity(context: WorkspaceContext) -> None:
    if context.worktree is None:
        return
    try:
        identity = _directory_identity(context.worktree)
    except OSError as exc:
        raise RunnerRuntimeError(f"workspace root is unavailable: {context.worktree}") from exc
    if identity != context.worktree_identity:
        raise RunnerRuntimeError("workspace root was replaced while the harness was running")


def _clean_git_env() -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_ATTR_NOSYSTEM": "1",
        }
    )
    return env


def _trusted_worktree_env(worktree: Path) -> dict[str, str]:
    env = _clean_git_env()
    env.update(
        {
            "GIT_DIR": str((worktree / ".git").resolve()),
            "GIT_WORK_TREE": str(worktree.resolve()),
            "GIT_LITERAL_PATHSPECS": "1",
            "GIT_CONFIG_COUNT": "2",
            "GIT_CONFIG_KEY_0": "core.hooksPath",
            "GIT_CONFIG_VALUE_0": os.devnull,
            "GIT_CONFIG_KEY_1": "core.fsmonitor",
            "GIT_CONFIG_VALUE_1": "false",
        }
    )
    return env


def _sha256_regular_file_no_follow(path: Path) -> str:
    if path.is_symlink():
        raise RunnerRuntimeError(f"trusted baseline artifact became a symlink: {path}")
    flags = os.O_RDONLY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise RunnerRuntimeError(f"could not read trusted baseline artifact {path}: {exc}") from exc
    digest = hashlib.sha256()
    with os.fdopen(descriptor, "rb") as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise RunnerRuntimeError(f"trusted baseline artifact is not a regular file: {path}")
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _overlay_visible_paths(repo_root: Path, worktree: Path, paths: list[str]) -> None:
    for raw_path in paths:
        relative = Path(raw_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise RunnerRuntimeError(f"unsafe Git path in working tree: {raw_path}")
        source = repo_root / relative
        target = worktree / relative
        if not os.path.lexists(source):
            if os.path.lexists(target):
                _remove_path(target)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if os.path.lexists(target):
            _remove_path(target)
        if source.is_symlink():
            target.symlink_to(os.readlink(source))
        elif source.is_file():
            shutil.copy2(source, target, follow_symlinks=False)
        else:
            raise RunnerRuntimeError(f"unsupported changed path type: {raw_path}")


def copy_non_git_workspace(source: Path, destination: Path, deny_patterns: list[str]) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    files_to_copy: list[str] = []
    for dirpath, dirnames, filenames in os.walk(source, followlinks=False):
        current = Path(dirpath)
        relative_dir = current.relative_to(source)
        if relative_dir != Path("."):
            (destination / relative_dir).mkdir(parents=True, exist_ok=True)
        kept_dirs: list[str] = []
        for dirname in dirnames:
            path = current / dirname
            relative = path.relative_to(source).as_posix()
            if _is_denied(relative, deny_patterns):
                continue
            if path.is_symlink():
                files_to_copy.append(relative)
            else:
                kept_dirs.append(dirname)
        dirnames[:] = kept_dirs
        for filename in filenames:
            path = current / filename
            relative = path.relative_to(source).as_posix()
            if not _is_denied(relative, deny_patterns):
                files_to_copy.append(relative)
    _overlay_visible_paths(source, destination, files_to_copy)


def _manifest_entry(path: Path) -> dict[str, str]:
    if path.is_symlink():
        mode = "120000"
        data = os.fsencode(os.readlink(path))
    elif path.is_file():
        mode = "100755" if path.stat().st_mode & 0o111 else "100644"
        data = path.read_bytes()
    else:
        raise RunnerRuntimeError(f"unsupported baseline path type: {path}")
    return {"mode": mode, "sha256": hashlib.sha256(data).hexdigest()}


def write_baseline_manifest(worktree: Path, manifest_path: Path) -> str:
    files: dict[str, dict[str, str]] = {}
    for dirpath, dirnames, filenames in os.walk(worktree, followlinks=False):
        current = Path(dirpath)
        kept_dirs: list[str] = []
        for dirname in dirnames:
            path = current / dirname
            if dirname == ".git":
                continue
            if path.is_symlink():
                files[path.relative_to(worktree).as_posix()] = _manifest_entry(path)
            else:
                kept_dirs.append(dirname)
        dirnames[:] = kept_dirs
        for filename in filenames:
            path = current / filename
            files[path.relative_to(worktree).as_posix()] = _manifest_entry(path)
    data = json.dumps({"files": files}, sort_keys=True, separators=(",", ":")).encode("utf-8")
    atomic_write_bytes(manifest_path, data)
    return hashlib.sha256(data).hexdigest()


def _temporary_index_env(index_path: Path, object_dir: Path, source_objects: Path) -> dict[str, str]:
    env = _clean_git_env()
    env.update(
        {
            "GIT_INDEX_FILE": str(index_path.resolve()),
            "GIT_OBJECT_DIRECTORY": str(object_dir.resolve()),
            "GIT_ALTERNATE_OBJECT_DIRECTORIES": str(source_objects.resolve()),
            "GIT_LITERAL_PATHSPECS": "1",
            "GIT_AUTHOR_NAME": "Subagent Broker",
            "GIT_AUTHOR_EMAIL": "subagent-broker@localhost",
            "GIT_COMMITTER_NAME": "Subagent Broker",
            "GIT_COMMITTER_EMAIL": "subagent-broker@localhost",
        }
    )
    return env


def _resolve_git_path(repo_root: Path, git_path: str) -> Path:
    path = Path(git_path)
    return path.resolve() if path.is_absolute() else (repo_root / path).resolve()


def export_working_tree_baseline(
    repo_root: Path,
    index_path: Path,
    object_dir: Path,
    worktree: Path,
    manifest_path: Path,
    bundle_path: Path | None,
    deny_patterns: list[str],
) -> tuple[str, str, str | None]:
    """Export the visible, non-denied tree into a standalone one-commit repository."""
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.unlink(missing_ok=True)
    shutil.rmtree(object_dir, ignore_errors=True)
    object_dir.mkdir(parents=True)
    source_objects_raw = os.fsdecode(_git_output(["rev-parse", "--git-path", "objects"], repo_root)).strip()
    source_objects = _resolve_git_path(repo_root, source_objects_raw)
    env = _temporary_index_env(index_path, object_dir, source_objects)
    try:
        head = os.fsdecode(_git_output(["rev-parse", "HEAD"], repo_root)).strip()
        _git_output(["read-tree", head], repo_root, env=env)

        staged_entries = _git_output(["ls-files", "--stage", "-z"], repo_root, env=env)
        if any(entry.startswith(b"160000 ") for entry in staged_entries.split(b"\0") if entry):
            raise RunnerRuntimeError("repositories containing Git submodules are not supported")

        tracked_changes = _nul_paths(
            _git_output(["diff", "--no-renames", "--name-only", "-z", "HEAD", "--"], repo_root)
        )
        untracked = _nul_paths(
            _git_output(["ls-files", "--others", "--exclude-standard", "-z", "--"], repo_root)
        )
        candidates = sorted(set([*tracked_changes, *untracked]))
        stage_paths = [path for path in candidates if not _is_denied(path, deny_patterns)]
        if stage_paths:
            process = run_sync(
                [
                    "git",
                    "add",
                    "-A",
                    "--pathspec-from-file=-",
                    "--pathspec-file-nul",
                ],
                repo_root,
                env=env,
                input_bytes=_pathspec_input(stage_paths),
            )
            if process.returncode != 0:
                raise RunnerRuntimeError(_process_error(process) or "git add into temporary index failed")

        tracked = _nul_paths(_git_output(["ls-files", "-z"], repo_root, env=env))
        denied_tracked = [path for path in tracked if _is_denied(path, deny_patterns)]
        if denied_tracked:
            process = run_sync(
                ["git", "update-index", "--force-remove", "-z", "--stdin"],
                repo_root,
                env=env,
                input_bytes=_pathspec_input(denied_tracked),
            )
            if process.returncode != 0:
                raise RunnerRuntimeError(
                    _process_error(process) or "removing denied paths from temporary index failed"
                )

        worktree.mkdir(parents=True, exist_ok=True)
        prefix = str(worktree.resolve()) + os.sep
        process = run_sync(
            ["git", "checkout-index", "--all", "--force", f"--prefix={prefix}"],
            repo_root,
            env=env,
        )
        if process.returncode != 0:
            raise RunnerRuntimeError(_process_error(process) or "git checkout-index failed")

        _overlay_visible_paths(repo_root, worktree, stage_paths)
        manifest_sha256 = write_baseline_manifest(worktree, manifest_path)

        template_dir = index_path.parent / "git-template"
        _remove_path(template_dir)
        template_dir.mkdir()
        process = run_sync(
            ["git", "init", "--quiet", f"--template={template_dir}"],
            worktree,
            env=_clean_git_env(),
        )
        if process.returncode != 0:
            raise RunnerRuntimeError(_process_error(process) or "git init failed")
        trusted_env = _trusted_worktree_env(worktree)
        process = run_sync(
            ["git", "add", "-f", "-A", "--", "."], worktree, env=trusted_env
        )
        if process.returncode != 0:
            raise RunnerRuntimeError(_process_error(process) or "git add baseline failed")
        tree = os.fsdecode(_git_output(["write-tree"], worktree, env=trusted_env)).strip()
        commit_env = dict(trusted_env)
        commit_env.update(
            {
                "GIT_AUTHOR_NAME": "Subagent Broker",
                "GIT_AUTHOR_EMAIL": "subagent-broker@localhost",
                "GIT_COMMITTER_NAME": "Subagent Broker",
                "GIT_COMMITTER_EMAIL": "subagent-broker@localhost",
            }
        )
        process = run_sync(
            ["git", "commit-tree", tree],
            worktree,
            env=commit_env,
            input_bytes=b"subagent-broker working tree baseline\n",
        )
        if process.returncode != 0:
            raise RunnerRuntimeError(_process_error(process) or "git commit-tree failed")
        commit = os.fsdecode(process.stdout).strip()
        process = run_sync(["git", "update-ref", "HEAD", commit], worktree, env=trusted_env)
        if process.returncode != 0:
            raise RunnerRuntimeError(_process_error(process) or "git update-ref failed")
        bundle_sha256 = None
        if bundle_path is not None:
            bundle_path.unlink(missing_ok=True)
            process = run_sync(
                ["git", "bundle", "create", str(bundle_path.resolve()), "HEAD"],
                worktree,
                env=trusted_env,
            )
            if process.returncode != 0:
                raise RunnerRuntimeError(_process_error(process) or "git bundle create failed")
            bundle_sha256 = _sha256_regular_file_no_follow(bundle_path)
        return commit, manifest_sha256, bundle_sha256
    finally:
        index_path.unlink(missing_ok=True)
        shutil.rmtree(object_dir, ignore_errors=True)
        shutil.rmtree(index_path.parent / "git-template", ignore_errors=True)


def restore_trusted_git_metadata(context: WorkspaceContext) -> None:
    """Discard harness-controlled Git metadata and restore the immutable baseline."""
    verify_workspace_identity(context)
    worktree = context.worktree
    baseline = context.baseline_commit
    bundle_path = context.baseline_bundle_path
    expected_bundle_sha256 = context.baseline_bundle_sha256
    if (
        worktree is None
        or baseline is None
        or bundle_path is None
        or expected_bundle_sha256 is None
    ):
        raise RunnerRuntimeError("trusted Git baseline metadata is unavailable")
    if _sha256_regular_file_no_follow(bundle_path) != expected_bundle_sha256:
        raise RunnerRuntimeError("trusted Git baseline bundle was modified by the harness")

    _remove_path(worktree / ".git")
    template_dir = bundle_path.parent / "restore-git-template"
    _remove_path(template_dir)
    template_dir.mkdir()
    try:
        process = run_sync(
            ["git", "init", "--quiet", f"--template={template_dir}"],
            worktree,
            env=_clean_git_env(),
        )
        if process.returncode != 0:
            raise RunnerRuntimeError(_process_error(process) or "trusted git init failed")
        trusted_env = _trusted_worktree_env(worktree)
        process = run_sync(
            ["git", "bundle", "unbundle", str(bundle_path.resolve())],
            worktree,
            env=trusted_env,
        )
        if process.returncode != 0:
            raise RunnerRuntimeError(_process_error(process) or "trusted git bundle restore failed")
        process = run_sync(
            ["git", "cat-file", "-e", f"{baseline}^{{commit}}"],
            worktree,
            env=trusted_env,
        )
        if process.returncode != 0:
            raise RunnerRuntimeError("trusted baseline commit is missing from restored metadata")
        process = run_sync(
            ["git", "update-ref", "HEAD", baseline], worktree, env=trusted_env
        )
        if process.returncode != 0:
            raise RunnerRuntimeError(_process_error(process) or "trusted git update-ref failed")
        process = run_sync(["git", "read-tree", baseline], worktree, env=trusted_env)
        if process.returncode != 0:
            raise RunnerRuntimeError(_process_error(process) or "trusted git read-tree failed")
    finally:
        shutil.rmtree(template_dir, ignore_errors=True)
    bundle_path.unlink()


def cleanup_agent_dir(agent_dir: Path, repo_root: Path | None) -> None:
    worktree = agent_dir / "worktree"
    if worktree.exists() and repo_root is not None and (worktree / ".git").is_file():
        run_sync(["git", "worktree", "remove", "--force", str(worktree)], repo_root)
    if agent_dir.exists():
        shutil.rmtree(agent_dir)


def prepare_workspace(
    source_cwd: Path,
    agent_dir: Path,
    deny_patterns: list[str],
    mode: str,
) -> WorkspaceContext:
    repo_root = git_root(source_cwd)
    agent_dir.mkdir(parents=True, exist_ok=True)
    if repo_root is None:
        if mode == "patch_only":
            raise RunnerRuntimeError("patch_only requires a Git repository")
        worktree = agent_dir / "worktree"
        copy_non_git_workspace(source_cwd.resolve(), worktree, deny_patterns)
        return WorkspaceContext(
            None,
            worktree,
            worktree,
            None,
            None,
            None,
            None,
            _directory_identity(worktree),
        )

    try:
        cwd_relative = source_cwd.resolve().relative_to(repo_root)
    except ValueError as exc:
        raise RunnerRuntimeError("working directory is outside the detected Git root") from exc

    worktree = agent_dir / "worktree"
    bundle_path = agent_dir / "baseline.bundle" if mode == "patch_only" else None
    baseline, manifest_sha256, bundle_sha256 = export_working_tree_baseline(
        repo_root,
        agent_dir / "baseline.index",
        agent_dir / "baseline-objects",
        worktree,
        agent_dir / "baseline_manifest.json",
        bundle_path,
        deny_patterns,
    )
    requested_cwd = worktree / cwd_relative
    if not requested_cwd.is_dir():
        raise RunnerRuntimeError(
            f"working directory is absent from the sanitized baseline: {cwd_relative.as_posix()}"
        )
    # Run from the standalone repository root so all repo-root-relative policy paths
    # share the same writable sandbox. The original subdirectory stays in the prompt.
    return WorkspaceContext(
        repo_root,
        worktree,
        worktree,
        baseline,
        manifest_sha256,
        bundle_path,
        bundle_sha256,
        _directory_identity(worktree),
    )


def collect_git_diff(worktree: Path, baseline: str, prechecked_paths: list[str]) -> PatchArtifact:
    trusted_env = _trusted_worktree_env(worktree)
    reset = run_sync(["git", "read-tree", baseline], worktree, env=trusted_env)
    if reset.returncode != 0:
        raise RunnerRuntimeError(_process_error(reset) or "git read-tree baseline failed")
    if prechecked_paths:
        stage = run_sync(
            ["git", "add", "-A", "--pathspec-from-file=-", "--pathspec-file-nul"],
            worktree,
            env=trusted_env,
            input_bytes=_pathspec_input(prechecked_paths),
        )
        if stage.returncode != 0:
            raise RunnerRuntimeError(_process_error(stage) or "git add agent changes failed")
    process = run_sync(
        [
            "git",
            "-c",
            "core.quotePath=false",
            "diff",
            "--cached",
            "--binary",
            "--no-renames",
            baseline,
            "--",
        ],
        worktree,
        env=trusted_env,
    )
    if process.returncode != 0:
        raise RunnerRuntimeError(_process_error(process) or "git diff failed")
    staged_paths = tuple(
        _nul_paths(
            _git_output(
                [
                    "diff",
                    "--cached",
                    "--no-renames",
                    "--name-only",
                    "-z",
                    baseline,
                    "--",
                ],
                worktree,
                env=trusted_env,
            )
        )
    )
    numstat = _git_output(
        ["diff", "--cached", "--numstat", "-z", "--no-renames", baseline, "--"],
        worktree,
        env=trusted_env,
    )
    has_binary_changes = any(
        entry.startswith(b"-\t-\t") for entry in numstat.split(b"\0") if entry
    )
    deleted = _git_output(
        [
            "diff",
            "--cached",
            "--diff-filter=D",
            "--name-only",
            "-z",
            "--no-renames",
            baseline,
            "--",
        ],
        worktree,
        env=trusted_env,
    )
    return PatchArtifact(process.stdout, staged_paths, has_binary_changes, bool(deleted))


SnapshotEntry = tuple[str, int, int, str]


def _snapshot_entry(path: Path) -> SnapshotEntry:
    metadata = path.lstat()
    if stat.S_ISLNK(metadata.st_mode):
        data = os.fsencode(os.readlink(path))
        return ("symlink", 0o120000, len(data), hashlib.sha256(data).hexdigest())
    if stat.S_ISREG(metadata.st_mode):
        data = path.read_bytes()
        mode = 0o100755 if metadata.st_mode & 0o111 else 0o100644
        return ("file", mode, len(data), hashlib.sha256(data).hexdigest())
    return ("other", stat.S_IFMT(metadata.st_mode), metadata.st_size, "")


def snapshot_files(root: Path) -> dict[str, SnapshotEntry]:
    snapshot: dict[str, SnapshotEntry] = {}
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(dirpath)
        kept_dirs: list[str] = []
        for dirname in dirnames:
            path = current / dirname
            if current == root and dirname == ".git":
                continue
            if path.is_symlink():
                snapshot[path.relative_to(root).as_posix()] = _snapshot_entry(path)
            else:
                kept_dirs.append(dirname)
        dirnames[:] = kept_dirs
        for filename in filenames:
            path = current / filename
            try:
                rel = path.relative_to(root).as_posix()
                snapshot[rel] = _snapshot_entry(path)
            except OSError:
                continue
    return snapshot


def changed_snapshot_paths(
    before: dict[str, SnapshotEntry],
    after: dict[str, SnapshotEntry],
) -> list[str]:
    return [path for path in sorted(set(before) | set(after)) if before.get(path) != after.get(path)]


async def _capture_stream(
    reader: asyncio.StreamReader,
    path: Path,
    limit: int,
    overflow: asyncio.Event,
) -> _CapturedStream:
    captured = bytearray()
    total = 0
    try:
        while True:
            chunk = await reader.read(64 * 1024)
            if not chunk:
                break
            total += len(chunk)
            remaining = limit - len(captured)
            if remaining > 0:
                captured.extend(chunk[:remaining])
            if total > limit:
                overflow.set()
    finally:
        truncated = total > limit
        data = bytes(captured)
        persisted = data
        if truncated:
            persisted += b"\n[output truncated: max_output_bytes exceeded]\n"
        atomic_write_bytes(path, persisted)
    return _CapturedStream(data, total, truncated)


def _signal_process_group(
    process: asyncio.subprocess.Process,
    process_group_id: int,
    sig: signal.Signals,
) -> None:
    if os.name == "posix":
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process_group_id, sig)
    elif process.returncode is None and sig == signal.SIGTERM:
        process.terminate()
    elif process.returncode is None:
        process.kill()


def _process_group_exists(process_group_id: int) -> bool:
    if os.name != "posix":
        return False
    try:
        os.killpg(process_group_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


async def _terminate_process_group(
    process: asyncio.subprocess.Process,
    process_group_id: int,
    wait_task: asyncio.Task[int],
) -> None:
    _signal_process_group(process, process_group_id, signal.SIGTERM)
    await asyncio.sleep(0.25)
    _signal_process_group(process, process_group_id, signal.SIGKILL)
    if not wait_task.done():
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(asyncio.shield(wait_task), timeout=2.0)


async def run_external_harness(
    invocation: HarnessInvocation,
    cwd: Path,
    env: dict[str, str],
    timeout_sec: int,
    max_output_bytes: int,
    stdout_path: Path,
    stderr_path: Path,
    event_writer: EventWriter,
) -> ProcessOutcome:
    event_writer("command", argv=list(invocation.logged_argv))
    subprocess_kwargs: dict[str, Any] = {"start_new_session": True} if os.name == "posix" else {}
    try:
        process = await asyncio.create_subprocess_exec(
            *invocation.argv,
            cwd=str(cwd),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            **subprocess_kwargs,
        )
    except FileNotFoundError:
        atomic_write_bytes(stdout_path, b"")
        atomic_write_bytes(stderr_path, b"")
        event_writer("stdout", bytes=0, truncated=False)
        event_writer("stderr", bytes=0, truncated=False)
        command = invocation.argv[0] if invocation.argv else "<empty>"
        return ProcessOutcome(
            None,
            "",
            "",
            "command_not_found",
            f"Harness command not found: {command}. Install it or configure the broker config.json.",
        )

    assert process.stdout is not None
    assert process.stderr is not None
    overflow = asyncio.Event()
    stdout_task = asyncio.create_task(
        _capture_stream(process.stdout, stdout_path, max_output_bytes, overflow)
    )
    stderr_task = asyncio.create_task(
        _capture_stream(process.stderr, stderr_path, max_output_bytes, overflow)
    )
    wait_task = asyncio.create_task(process.wait())
    overflow_task = asyncio.create_task(overflow.wait())
    capture_future = asyncio.gather(stdout_task, stderr_task)
    process_group_id = process.pid
    error_kind: str | None = None
    error: str | None = None
    try:
        done, _ = await asyncio.wait(
            {wait_task, overflow_task},
            timeout=timeout_sec,
            return_when=asyncio.FIRST_COMPLETED,
        )
        if overflow_task in done and overflow.is_set():
            error_kind = "output_limit"
            error = "stdout or stderr exceeded max_output_bytes"
            await _terminate_process_group(process, process_group_id, wait_task)
        elif wait_task not in done:
            error_kind = "timeout"
            error = "timeout"
            await _terminate_process_group(process, process_group_id, wait_task)

        try:
            stdout_capture, stderr_capture = await asyncio.wait_for(
                asyncio.shield(capture_future), timeout=1.0
            )
        except asyncio.TimeoutError:
            await _terminate_process_group(process, process_group_id, wait_task)
            try:
                stdout_capture, stderr_capture = await asyncio.wait_for(
                    asyncio.shield(capture_future), timeout=2.0
                )
            except asyncio.TimeoutError as exc:
                capture_future.cancel()
                raise RunnerRuntimeError(
                    "harness descendants kept stdout or stderr open after termination"
                ) from exc
        if _process_group_exists(process_group_id):
            await _terminate_process_group(process, process_group_id, wait_task)
            event_writer("descendants_terminated", process_group_id=process_group_id)
        if (stdout_capture.truncated or stderr_capture.truncated) and error_kind is None:
            error_kind = "output_limit"
            error = "stdout or stderr exceeded max_output_bytes"
        event_writer(
            "stdout", bytes=stdout_capture.total_bytes, truncated=stdout_capture.truncated
        )
        event_writer(
            "stderr", bytes=stderr_capture.total_bytes, truncated=stderr_capture.truncated
        )
        return ProcessOutcome(
            process.returncode,
            stdout_capture.data.decode("utf-8", errors="replace"),
            stderr_capture.data.decode("utf-8", errors="replace"),
            error_kind,
            error,
        )
    except asyncio.CancelledError:
        await _terminate_process_group(process, process_group_id, wait_task)
        try:
            stdout_capture, stderr_capture = await asyncio.wait_for(
                asyncio.shield(capture_future), timeout=2.0
            )
            event_writer(
                "stdout", bytes=stdout_capture.total_bytes, truncated=stdout_capture.truncated
            )
            event_writer(
                "stderr", bytes=stderr_capture.total_bytes, truncated=stderr_capture.truncated
            )
        except asyncio.TimeoutError:
            capture_future.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await capture_future
            event_writer("stdout", bytes=stdout_path.stat().st_size if stdout_path.exists() else 0)
            event_writer("stderr", bytes=stderr_path.stat().st_size if stderr_path.exists() else 0)
        raise
    finally:
        overflow_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await overflow_task
