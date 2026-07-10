import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
RUNNER = SKILL_DIR / "scripts" / "subagent_runner.py"
MERGE = SKILL_DIR / "scripts" / "merge_patches.py"


def run(args, cwd):
    return subprocess.run(
        args,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False,
        check=False,
    )


def init_repo(root):
    run(["git", "init", "--quiet"], root)
    run(["git", "config", "user.email", "test@example.com"], root)
    run(["git", "config", "user.name", "Test User"], root)


def commit_all(root):
    run(["git", "add", "-A"], root)
    process = run(["git", "commit", "--quiet", "-m", "initial"], root)
    if process.returncode != 0:
        raise AssertionError(process.stderr.decode(errors="replace"))


class MergePatchTests(unittest.TestCase):
    def generate_patch(self, base, *, crlf=False):
        repo = base / "repo"
        repo.mkdir()
        init_repo(repo)
        if crlf:
            (repo / ".gitattributes").write_text("*.txt text eol=crlf\n", encoding="utf-8")
            (repo / "file.txt").write_bytes(b"base\r\n")
        else:
            (repo / "file.txt").write_text("base\n", encoding="utf-8")
        (repo / "staged.txt").write_text("staged base\n", encoding="utf-8")
        commit_all(repo)

        if crlf:
            (repo / "file.txt").write_bytes(b"user change\r\n")
        else:
            (repo / "file.txt").write_text("user change\n", encoding="utf-8")
        (repo / "staged.txt").write_text("staged user change\n", encoding="utf-8")
        run(["git", "add", "staged.txt"], repo)

        task = repo / "tasks.json"
        task.write_text(
            json.dumps(
                {
                    "run_id": "merge-run",
                    "defaults": {"harness": "fake", "mode": "patch_only"},
                    "agents": [
                        {
                            "id": "patcher",
                            "goal": "Append one line.",
                            "allowed_paths": ["file.txt"],
                            "fake_patch": {
                                "path": "file.txt",
                                "content": "agent change\n",
                                "append": True,
                            },
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        process = run([sys.executable, str(RUNNER), "run", str(task), "--wait"], repo)
        self.assertEqual(process.returncode, 0, process.stderr.decode(errors="replace"))
        patch = repo / ".subagents" / "merge-run" / "patcher" / "patch.diff"
        result = json.loads((patch.parent / "result.json").read_text())
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["policy"]["status"], "passed")
        return repo, patch

    def test_apply_from_subdirectory_preserves_dirty_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, patch = self.generate_patch(Path(tmp))
            patch_bytes = patch.read_bytes()
            self.assertNotIn(b"-base", patch_bytes)
            self.assertIn(b"agent change", patch_bytes)
            cached_before = run(["git", "diff", "--cached", "--binary"], repo).stdout
            subdir = repo / "subdir"
            subdir.mkdir()

            check = run([sys.executable, str(MERGE), "--check", str(patch)], subdir)
            self.assertEqual(check.returncode, 0, check.stderr.decode(errors="replace"))
            self.assertIn(b"Patch check passed: 1 files", check.stdout)
            apply = run([sys.executable, str(MERGE), "--apply", str(patch)], subdir)
            self.assertEqual(apply.returncode, 0, apply.stderr.decode(errors="replace"))
            self.assertIn(b"Patch applied: 1 files", apply.stdout)
            self.assertEqual(
                (repo / "file.txt").read_text(), "user change\nagent change\n"
            )
            cached_after = run(["git", "diff", "--cached", "--binary"], repo).stdout
            self.assertEqual(cached_after, cached_before)

    def test_tampered_patch_and_changed_baseline_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, patch = self.generate_patch(Path(tmp))
            original = patch.read_bytes()
            patch.write_bytes(original + b"\n# tampered\n")
            tampered = run([sys.executable, str(MERGE), "--check", str(patch)], repo)
            self.assertEqual(tampered.returncode, 2)
            self.assertIn(b"SHA-256", tampered.stderr)

            patch.write_bytes(original)
            (repo / "file.txt").write_text("changed after run\n", encoding="utf-8")
            drifted = run([sys.executable, str(MERGE), "--check", str(patch)], repo)
            self.assertEqual(drifted.returncode, 2)
            self.assertIn(b"changed since", drifted.stderr)

    def test_patch_is_rejected_from_a_different_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _, patch = self.generate_patch(base)
            other = base / "other"
            other.mkdir()
            init_repo(other)
            (other / "file.txt").write_text("user change\n", encoding="utf-8")
            commit_all(other)

            checked = run([sys.executable, str(MERGE), "--check", str(patch)], other)
            self.assertEqual(checked.returncode, 2)
            self.assertIn(b"original source repository", checked.stderr)

    def test_crlf_working_tree_matches_raw_baseline_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, patch = self.generate_patch(Path(tmp), crlf=True)
            check = run([sys.executable, str(MERGE), "--check", str(patch)], repo)
            self.assertEqual(check.returncode, 0, check.stderr.decode(errors="replace"))


if __name__ == "__main__":
    unittest.main()
