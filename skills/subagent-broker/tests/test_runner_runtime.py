import asyncio
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR / "scripts"))

from harness_adapters import HarnessInvocation  # noqa: E402
from policy_check import DEFAULT_DENY  # noqa: E402
from runner_runtime import (  # noqa: E402
    RunnerRuntimeError,
    changed_snapshot_paths,
    collect_git_diff,
    git_changed_paths,
    prepare_workspace,
    restore_trusted_git_metadata,
    run_external_harness,
    snapshot_files,
)


def run(args, cwd, input_bytes=None):
    return subprocess.run(
        args,
        cwd=str(cwd),
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def init_repo(root):
    run(["git", "init", "--quiet"], root)
    run(["git", "config", "user.email", "test@example.com"], root)
    run(["git", "config", "user.name", "Test User"], root)


def commit_all(root, message="initial"):
    run(["git", "add", "-A"], root)
    process = run(["git", "commit", "--quiet", "-m", message], root)
    if process.returncode != 0:
        raise AssertionError(process.stderr.decode(errors="replace"))


class WorkspaceRuntimeTests(unittest.TestCase):
    def test_non_git_read_only_uses_copy_instead_of_source_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source = base / "source"
            source.mkdir()
            (source / "file.txt").write_text("source\n", encoding="utf-8")
            (source / ".env").write_text("SECRET=value\n", encoding="utf-8")
            context = prepare_workspace(source, base / "agent", list(DEFAULT_DENY), "read_only")
            self.assertNotEqual(context.harness_cwd, source)
            self.assertEqual((context.harness_cwd / "file.txt").read_text(), "source\n")
            self.assertFalse((context.harness_cwd / ".env").exists())
            (context.harness_cwd / "file.txt").write_text("agent\n", encoding="utf-8")
            self.assertEqual((source / "file.txt").read_text(), "source\n")

    def test_snapshot_detects_mode_and_symlink_type_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target.txt"
            changed = root / "changed.txt"
            target.write_text("same\n", encoding="utf-8")
            changed.write_text("same\n", encoding="utf-8")
            before = snapshot_files(root)
            changed.chmod(0o755)
            mode_after = snapshot_files(root)
            self.assertEqual(changed_snapshot_paths(before, mode_after), ["changed.txt"])
            changed.unlink()
            changed.symlink_to(target.name)
            symlink_after = snapshot_files(root)
            self.assertEqual(changed_snapshot_paths(mode_after, symlink_after), ["changed.txt"])
            (root / ".subagents").mkdir()
            (root / ".subagents" / "output.txt").write_text("created\n", encoding="utf-8")
            nested_output = snapshot_files(root)
            self.assertIn(".subagents/output.txt", changed_snapshot_paths(symlink_after, nested_output))

    def test_standalone_baseline_mirrors_dirty_tree_and_excludes_denied_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = base / "repo"
            repo.mkdir()
            init_repo(repo)
            (repo / ".gitignore").write_text("build/\n", encoding="utf-8")
            (repo / ".env").write_text("SECRET=tracked\n", encoding="utf-8")
            (repo / "tracked.txt").write_text("base\n", encoding="utf-8")
            (repo / "delete.txt").write_text("delete me\n", encoding="utf-8")
            (repo / "keep.log").write_text("tracked log\n", encoding="utf-8")
            (repo / "subdir").mkdir()
            (repo / "subdir" / "README.md").write_text("subdir\n", encoding="utf-8")
            commit_all(repo)

            (repo / "tracked.txt").write_text("user change\n", encoding="utf-8")
            (repo / "delete.txt").unlink()
            (repo / "untracked.txt").write_text("untracked\n", encoding="utf-8")
            (repo / "*").write_text("literal star\n", encoding="utf-8")
            (repo / "subdir" / ".env.local").write_text("SECRET=nested\n", encoding="utf-8")
            (repo / ".gitignore").write_text("build/\n*.log\n", encoding="utf-8")
            staged_then_deleted = repo / "gone-before-run.txt"
            staged_then_deleted.write_text("temporary\n", encoding="utf-8")
            run(["git", "add", staged_then_deleted.name], repo)
            staged_then_deleted.unlink()

            object_id = run(["git", "hash-object", "--stdin"], repo, b"untracked\n").stdout.strip()
            self.assertNotEqual(run(["git", "cat-file", "-e", object_id], repo).returncode, 0)

            agent_dir = base / "agent"
            context = prepare_workspace(repo / "subdir", agent_dir, list(DEFAULT_DENY), "patch_only")
            worktree = context.worktree
            self.assertIsNotNone(worktree)
            assert worktree is not None
            self.assertTrue((worktree / ".git").is_dir())
            self.assertEqual(context.harness_cwd, worktree)
            self.assertEqual((worktree / "tracked.txt").read_text(), "user change\n")
            self.assertEqual((worktree / "untracked.txt").read_text(), "untracked\n")
            self.assertEqual((worktree / "*").read_text(), "literal star\n")
            self.assertTrue((worktree / "keep.log").is_file())
            self.assertFalse((worktree / "delete.txt").exists())
            self.assertFalse((worktree / "gone-before-run.txt").exists())
            self.assertFalse((worktree / ".env").exists())
            self.assertFalse((worktree / "subdir" / ".env.local").exists())
            self.assertEqual(run(["git", "status", "--porcelain"], worktree).stdout, b"")
            self.assertNotEqual(run(["git", "cat-file", "-e", object_id], repo).returncode, 0)

    def test_unborn_repository_baseline_mirrors_visible_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = base / "repo"
            repo.mkdir()
            init_repo(repo)
            (repo / ".gitignore").write_text("build/\n", encoding="utf-8")
            (repo / "staged.txt").write_text("staged\n", encoding="utf-8")
            (repo / "gone.txt").write_text("gone\n", encoding="utf-8")
            (repo / ".env").write_text("SECRET=value\n", encoding="utf-8")
            run(["git", "add", ".gitignore", "staged.txt", "gone.txt", ".env"], repo)
            (repo / "staged.txt").write_text("visible\n", encoding="utf-8")
            (repo / "gone.txt").unlink()
            (repo / "untracked.txt").write_text("untracked\n", encoding="utf-8")
            (repo / "build").mkdir()
            (repo / "build" / "ignored.txt").write_text("ignored\n", encoding="utf-8")
            source_index = run(["git", "ls-files", "-z"], repo).stdout

            context = prepare_workspace(repo, base / "agent", list(DEFAULT_DENY), "patch_only")
            assert context.worktree is not None and context.baseline_commit is not None
            self.assertIsNotNone(context.baseline_bundle_sha256)
            self.assertEqual((context.worktree / "staged.txt").read_text(), "visible\n")
            self.assertEqual((context.worktree / "untracked.txt").read_text(), "untracked\n")
            self.assertTrue((context.worktree / ".gitignore").is_file())
            self.assertFalse((context.worktree / "gone.txt").exists())
            self.assertFalse((context.worktree / ".env").exists())
            self.assertFalse((context.worktree / "build").exists())
            self.assertEqual(run(["git", "status", "--porcelain"], context.worktree).stdout, b"")
            self.assertNotEqual(run(["git", "rev-parse", "--verify", "HEAD"], repo).returncode, 0)
            self.assertEqual(run(["git", "ls-files", "-z"], repo).stdout, source_index)

            (context.worktree / "staged.txt").write_text("agent\n", encoding="utf-8")
            restore_trusted_git_metadata(context)
            changed = git_changed_paths(context.worktree, context.baseline_commit)
            artifact = collect_git_diff(context.worktree, context.baseline_commit, changed)
            self.assertEqual(artifact.changed_paths, ("staged.txt",))
            self.assertIn(b"agent", artifact.data)

    def test_empty_unborn_repository_creates_read_only_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = base / "repo"
            repo.mkdir()
            init_repo(repo)

            context = prepare_workspace(repo, base / "agent", list(DEFAULT_DENY), "read_only")
            assert context.worktree is not None and context.baseline_commit is not None
            self.assertEqual(run(["git", "status", "--porcelain"], context.worktree).stdout, b"")
            self.assertEqual(snapshot_files(context.worktree), {})
            self.assertNotEqual(run(["git", "rev-parse", "--verify", "HEAD"], repo).returncode, 0)

    def test_agent_commit_is_diffed_against_immutable_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = base / "repo"
            repo.mkdir()
            init_repo(repo)
            (repo / "file.txt").write_text("base\n", encoding="utf-8")
            commit_all(repo)
            context = prepare_workspace(repo, base / "agent", list(DEFAULT_DENY), "patch_only")
            assert context.worktree is not None and context.baseline_commit is not None
            (context.worktree / "file.txt").write_text("committed by agent\n", encoding="utf-8")
            commit_all(context.worktree, "agent commit")
            restore_trusted_git_metadata(context)
            changed = git_changed_paths(context.worktree, context.baseline_commit)
            self.assertEqual(changed, ["file.txt"])
            artifact = collect_git_diff(context.worktree, context.baseline_commit, changed)
            self.assertEqual(artifact.changed_paths, ("file.txt",))
            self.assertIn(b"committed by agent", artifact.data)

    def test_patch_bytes_preserve_non_utf8_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = base / "repo"
            repo.mkdir()
            init_repo(repo)
            (repo / "raw.txt").write_bytes(b"base\n")
            commit_all(repo)
            context = prepare_workspace(repo, base / "agent", list(DEFAULT_DENY), "patch_only")
            assert context.worktree is not None and context.baseline_commit is not None
            (context.worktree / "raw.txt").write_bytes(b"agent:\xff\n")
            restore_trusted_git_metadata(context)
            changed = git_changed_paths(context.worktree, context.baseline_commit)
            artifact = collect_git_diff(context.worktree, context.baseline_commit, changed)
            self.assertIn(b"\xff", artifact.data)
            patch = base / "patch.diff"
            patch.write_bytes(artifact.data)
            self.assertEqual(patch.read_bytes(), artifact.data)

    def test_restore_discards_agent_git_hooks_and_filters(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = base / "repo"
            repo.mkdir()
            init_repo(repo)
            (repo / ".gitattributes").write_text("*.txt filter=agent\n", encoding="utf-8")
            (repo / "file.txt").write_text("base\n", encoding="utf-8")
            commit_all(repo)
            context = prepare_workspace(repo, base / "agent", list(DEFAULT_DENY), "patch_only")
            assert context.worktree is not None and context.baseline_commit is not None

            sentinel = base / "post-harness-command-ran"
            filter_script = base / "filter.py"
            filter_script.write_text(
                "#!/usr/bin/env python3\n"
                "import pathlib, sys\n"
                f"pathlib.Path({str(sentinel)!r}).write_text('ran')\n"
                "sys.stdout.buffer.write(sys.stdin.buffer.read())\n",
                encoding="utf-8",
            )
            filter_script.chmod(0o755)
            configured = run(
                ["git", "config", "filter.agent.clean", str(filter_script)], context.worktree
            )
            self.assertEqual(configured.returncode, 0)
            hook = context.worktree / ".git" / "hooks" / "post-index-change"
            hook.parent.mkdir()
            hook.write_text(
                f"#!/bin/sh\nprintf ran > {sentinel}\n",
                encoding="utf-8",
            )
            hook.chmod(0o755)
            (context.worktree / "file.txt").write_text("agent\n", encoding="utf-8")

            restore_trusted_git_metadata(context)
            changed = git_changed_paths(context.worktree, context.baseline_commit)
            artifact = collect_git_diff(context.worktree, context.baseline_commit, changed)
            self.assertEqual(artifact.changed_paths, ("file.txt",))
            self.assertFalse(sentinel.exists())

    def test_restore_replaces_redirected_git_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = base / "repo"
            repo.mkdir()
            init_repo(repo)
            (repo / "file.txt").write_text("base\n", encoding="utf-8")
            commit_all(repo)
            context = prepare_workspace(repo, base / "agent", list(DEFAULT_DENY), "patch_only")
            assert context.worktree is not None and context.baseline_commit is not None
            (context.worktree / "file.txt").write_text("agent\n", encoding="utf-8")

            external_git = base / "external-git"
            external_git.mkdir()
            marker = external_git / "marker"
            marker.write_text("keep", encoding="utf-8")
            shutil.rmtree(context.worktree / ".git")
            (context.worktree / ".git").symlink_to(external_git, target_is_directory=True)

            restore_trusted_git_metadata(context)
            self.assertTrue((context.worktree / ".git").is_dir())
            self.assertFalse((context.worktree / ".git").is_symlink())
            self.assertEqual(marker.read_text(encoding="utf-8"), "keep")
            changed = git_changed_paths(context.worktree, context.baseline_commit)
            self.assertEqual(changed, ["file.txt"])

    def test_restore_rejects_tampered_baseline_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = base / "repo"
            repo.mkdir()
            init_repo(repo)
            (repo / "file.txt").write_text("base\n", encoding="utf-8")
            commit_all(repo)
            context = prepare_workspace(repo, base / "agent", list(DEFAULT_DENY), "patch_only")
            assert context.baseline_bundle_path is not None
            context.baseline_bundle_path.write_bytes(b"tampered")
            with self.assertRaisesRegex(RunnerRuntimeError, "bundle was modified"):
                restore_trusted_git_metadata(context)


class ProcessRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def run_invocation(self, root, command, timeout=5, limit=10_000, idle=180):
        events = []

        def write_event(event, **fields):
            events.append((event, fields))

        invocation = HarnessInvocation(tuple(command), tuple(command))
        outcome = await run_external_harness(
            invocation,
            root,
            dict(os.environ),
            timeout,
            limit,
            root / "stdout.log",
            root / "stderr.log",
            write_event,
            idle_timeout_sec=idle,
        )
        return outcome, events

    async def test_output_limit_terminates_task_and_keeps_truncated_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outcome, _ = await self.run_invocation(
                root,
                [sys.executable, "-c", "print('x' * 10000)"],
                limit=100,
            )
            self.assertEqual(outcome.error_kind, "output_limit")
            self.assertIn(b"output truncated", (root / "stdout.log").read_bytes())

    async def test_timeout_terminates_process_group(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            started = time.monotonic()
            outcome, _ = await self.run_invocation(root, ["sh", "-c", "sleep 60"], timeout=1)
            self.assertEqual(outcome.error_kind, "timeout")
            self.assertLess(time.monotonic() - started, 3)
            self.assertTrue((root / "stdout.log").exists())

    async def test_stdout_is_visible_before_process_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = asyncio.create_task(
                self.run_invocation(
                    root,
                    [
                        sys.executable,
                        "-c",
                        "import time; print('first', flush=True); time.sleep(1); print('last')",
                    ],
                )
            )
            for _ in range(20):
                if (root / "stdout.log").exists() and b"first" in (root / "stdout.log").read_bytes():
                    break
                await asyncio.sleep(0.05)
            self.assertIn(b"first", (root / "stdout.log").read_bytes())
            self.assertFalse(task.done())
            outcome, _ = await task
            self.assertEqual(outcome.returncode, 0)

    async def test_idle_timeout_terminates_process_group(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            started = time.monotonic()
            outcome, _ = await self.run_invocation(
                root,
                ["sh", "-c", "sleep 60"],
                timeout=10,
                idle=1,
            )
            self.assertEqual(outcome.error_kind, "idle_timeout")
            self.assertLess(time.monotonic() - started, 3)

    async def test_async_cancellation_terminates_and_preserves_logs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = asyncio.create_task(
                self.run_invocation(root, ["sh", "-c", "echo started; sleep 60"], timeout=30)
            )
            await asyncio.sleep(0.2)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertIn(b"started", (root / "stdout.log").read_bytes())

    async def test_background_child_holding_pipes_does_not_hang(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            started = time.monotonic()
            outcome, _ = await self.run_invocation(root, ["sh", "-c", "sleep 60 &"], timeout=4)
            self.assertLess(time.monotonic() - started, 4)
            self.assertEqual(outcome.returncode, 0)

    async def test_redirected_background_child_is_terminated_after_leader_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outcome, events = await self.run_invocation(
                root,
                ["sh", "-c", "sleep 60 >/dev/null 2>&1 & echo $! > child.pid"],
            )
            self.assertEqual(outcome.returncode, 0)
            child_pid = int((root / "child.pid").read_text())
            for _ in range(20):
                if not Path(f"/proc/{child_pid}").exists():
                    break
                await asyncio.sleep(0.05)
            self.assertFalse(Path(f"/proc/{child_pid}").exists())
            self.assertTrue(any(event == "descendants_terminated" for event, _ in events))


if __name__ == "__main__":
    unittest.main()
