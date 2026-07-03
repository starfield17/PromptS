import json
import os
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
RUNNER = SKILL_DIR / "scripts" / "subagent_runner.py"


def load_runner_module():
    spec = importlib.util.spec_from_file_location("subagent_runner_under_test", RUNNER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def run_cmd(args, cwd, env=None):
    return subprocess.run(
        args,
        cwd=str(cwd),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def init_git_repo(path):
    run_cmd(["git", "init"], path)
    run_cmd(["git", "config", "user.email", "test@example.com"], path)
    run_cmd(["git", "config", "user.name", "Test User"], path)
    (path / "README.md").write_text("# Test\n", encoding="utf-8")
    run_cmd(["git", "add", "README.md"], path)
    run_cmd(["git", "commit", "-m", "initial"], path)


class RunnerFakeHarnessTests(unittest.TestCase):
    def write_tasks(self, root, payload):
        path = root / "tasks.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def make_fake_claude(self, bin_dir):
        fake_claude = bin_dir / "claude"
        fake_claude.write_text(
            f"""#!{sys.executable}
import json
import os
import sys

capture_path = os.environ["CAPTURE_PATH"]
with open(capture_path, "w", encoding="utf-8") as handle:
    json.dump({{
        "argv": sys.argv[1:],
        "home": os.environ.get("HOME"),
        "tmpdir": os.environ.get("TMPDIR"),
        "xdg_cache_home": os.environ.get("XDG_CACHE_HOME"),
        "pwd": os.environ.get("PWD"),
    }}, handle)

print("SUBAGENT_RESULT_JSON_START")
print(json.dumps({{"summary": "fake claude completed", "files_read": [], "files_changed": [], "tests_run": [], "risks": [], "recommendations": []}}))
print("SUBAGENT_RESULT_JSON_END")
""",
            encoding="utf-8",
        )
        fake_claude.chmod(0o755)
        return fake_claude

    def test_home_policy_validation_defaults_and_rejections(self):
        runner = load_runner_module()
        packet = runner.validate_and_normalize(
            {
                "run_id": "validate-home",
                "agents": [{"id": "a", "goal": "g", "allowed_paths": ["**"]}],
            }
        )
        self.assertEqual(packet["agents"][0]["home_policy"], "isolated")

        packet = runner.validate_and_normalize(
            {
                "run_id": "validate-host",
                "agents": [
                    {
                        "id": "a",
                        "goal": "g",
                        "harness": "claude-code",
                        "home_policy": "host",
                        "allowed_paths": ["**"],
                    }
                ],
            }
        )
        self.assertEqual(packet["agents"][0]["home_policy"], "host")

        with self.assertRaisesRegex(runner.RunnerError, "requires inherit_env true"):
            runner.validate_and_normalize(
                {
                    "run_id": "bad-host",
                    "agents": [
                        {
                            "id": "a",
                            "goal": "g",
                            "harness": "claude-code",
                            "home_policy": "host",
                            "inherit_env": False,
                            "allowed_paths": ["**"],
                        }
                    ],
                }
            )

        with self.assertRaisesRegex(runner.RunnerError, "home_policy"):
            runner.validate_and_normalize(
                {
                    "run_id": "bad-policy",
                    "agents": [
                        {
                            "id": "a",
                            "goal": "g",
                            "harness": "claude-code",
                            "home_policy": "shared",
                            "allowed_paths": ["**"],
                        }
                    ],
                }
            )

    def test_fake_read_only_agent_completes_and_summary_is_generated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = self.write_tasks(
                root,
                {
                    "run_id": "fake-read",
                    "defaults": {"harness": "fake", "mode": "read_only"},
                    "agents": [
                        {
                            "id": "reader",
                            "goal": "Return a fake analysis.",
                            "allowed_paths": ["**"],
                            "fake_response": {"summary": "Fake read-only completed."},
                        }
                    ],
                },
            )
            process = run_cmd([sys.executable, str(RUNNER), "run", str(task), "--wait"], root)
            self.assertEqual(process.returncode, 0, process.stderr)
            result_path = root / ".subagents" / "fake-read" / "reader" / "result.json"
            summary_path = root / ".subagents" / "fake-read" / "summary.md"
            result = json.loads(result_path.read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["summary"], "Fake read-only completed.")
            self.assertTrue(summary_path.exists())

    def test_fake_patch_only_agent_creates_patch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_git_repo(root)
            task = self.write_tasks(
                root,
                {
                    "run_id": "fake-patch",
                    "defaults": {"harness": "fake"},
                    "agents": [
                        {
                            "id": "patcher",
                            "mode": "patch_only",
                            "goal": "Create a test file.",
                            "allowed_paths": ["tests/**"],
                            "fake_patch": {
                                "path": "tests/test_generated.py",
                                "content": "def test_generated():\n    assert True\n",
                            },
                        }
                    ],
                },
            )
            process = run_cmd([sys.executable, str(RUNNER), "run", str(task), "--wait"], root)
            self.assertEqual(process.returncode, 0, process.stderr)
            agent_dir = root / ".subagents" / "fake-patch" / "patcher"
            result = json.loads((agent_dir / "result.json").read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["policy"]["status"], "passed")
            self.assertIn("tests/test_generated.py", (agent_dir / "patch.diff").read_text(encoding="utf-8"))

    def test_fake_patch_only_denied_path_becomes_policy_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_git_repo(root)
            task = self.write_tasks(
                root,
                {
                    "run_id": "fake-denied",
                    "defaults": {"harness": "fake"},
                    "agents": [
                        {
                            "id": "patcher",
                            "mode": "patch_only",
                            "goal": "Touch a denied file.",
                            "allowed_paths": ["**"],
                            "deny_paths": [".env*"],
                            "fake_patch": {"path": ".env", "content": "TOKEN=bad\n"},
                        }
                    ],
                },
            )
            process = run_cmd([sys.executable, str(RUNNER), "run", str(task), "--wait"], root)
            self.assertNotEqual(process.returncode, 0)
            result = json.loads(
                (root / ".subagents" / "fake-denied" / "patcher" / "result.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(result["status"], "policy_failed")
            self.assertEqual(result["policy"]["status"], "failed")

    def test_collect_and_status_read_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = self.write_tasks(
                root,
                {
                    "run_id": "fake-collect",
                    "defaults": {"harness": "fake", "mode": "read_only"},
                    "agents": [{"id": "reader", "goal": "Return fake result.", "allowed_paths": ["**"]}],
                },
            )
            run_cmd([sys.executable, str(RUNNER), "run", str(task), "--wait"], root)
            collect = run_cmd(
                [sys.executable, str(RUNNER), "collect", ".subagents/fake-collect"],
                root,
            )
            self.assertEqual(collect.returncode, 0, collect.stderr)
            self.assertIn(".subagents/fake-collect/summary.md", collect.stdout)
            status = run_cmd(
                [sys.executable, str(RUNNER), "status", ".subagents/fake-collect"],
                root,
            )
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("- reader: completed", status.stdout)

    def test_missing_real_harness_command_fails_gracefully(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = self.write_tasks(
                root,
                {
                    "run_id": "missing-harness",
                    "defaults": {"harness": "opencode", "mode": "read_only"},
                    "agents": [{"id": "reader", "goal": "Try missing opencode.", "allowed_paths": ["**"]}],
                },
            )
            env = dict(os.environ)
            env["PATH"] = ""
            process = run_cmd([sys.executable, str(RUNNER), "run", str(task), "--wait"], root, env=env)
            self.assertNotEqual(process.returncode, 0)
            result = json.loads(
                (root / ".subagents" / "missing-harness" / "reader" / "result.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(result["status"], "failed")
            self.assertIn("Harness command not found: opencode.", result["error"])

    def test_claude_default_uses_isolated_home_and_no_session_persistence(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "repo"
            root.mkdir()
            bin_dir = base / "bin"
            bin_dir.mkdir()
            capture_path = base / "capture.json"
            host_home = base / "host-home"
            host_home.mkdir()
            self.make_fake_claude(bin_dir)
            task = self.write_tasks(
                root,
                {
                    "run_id": "claude-default",
                    "defaults": {"harness": "claude-code", "mode": "read_only"},
                    "agents": [
                        {
                            "id": "reader",
                            "goal": "Run fake Claude.",
                            "allowed_paths": ["**"],
                        }
                    ],
                },
            )
            env = dict(os.environ)
            env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
            env["CAPTURE_PATH"] = str(capture_path)
            env["HOME"] = str(host_home)
            process = run_cmd([sys.executable, str(RUNNER), "run", str(task), "--wait"], root, env=env)
            self.assertEqual(process.returncode, 0, process.stderr)
            capture = json.loads(capture_path.read_text(encoding="utf-8"))
            self.assertNotEqual(capture["home"], str(host_home))
            self.assertTrue(capture["home"].endswith(".subagents/claude-default/reader/home"))
            self.assertIn("--no-session-persistence", capture["argv"])
            self.assertNotIn("--dangerously-skip-permissions", capture["argv"])

    def test_claude_host_home_and_permission_flags_are_opt_in(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "repo"
            root.mkdir()
            bin_dir = base / "bin"
            bin_dir.mkdir()
            capture_path = base / "capture.json"
            host_home = base / "host-home"
            host_home.mkdir()
            self.make_fake_claude(bin_dir)
            task = self.write_tasks(
                root,
                {
                    "run_id": "claude-host-home",
                    "defaults": {"harness": "claude-code", "mode": "read_only"},
                    "agents": [
                        {
                            "id": "reader",
                            "goal": "Run fake Claude.",
                            "allowed_paths": ["**"],
                            "home_policy": "host",
                            "dangerously_skip_permissions": True,
                            "session_persistence": True,
                            "model": "test-model",
                            "agent": "reviewer",
                        }
                    ],
                },
            )
            env = dict(os.environ)
            env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
            env["CAPTURE_PATH"] = str(capture_path)
            env["HOME"] = str(host_home)
            process = run_cmd([sys.executable, str(RUNNER), "run", str(task), "--wait"], root, env=env)
            self.assertEqual(process.returncode, 0, process.stderr)
            capture = json.loads(capture_path.read_text(encoding="utf-8"))
            self.assertEqual(capture["home"], str(host_home))
            self.assertIn("--dangerously-skip-permissions", capture["argv"])
            self.assertNotIn("--no-session-persistence", capture["argv"])
            self.assertIn("--model", capture["argv"])
            self.assertIn("test-model", capture["argv"])
            self.assertIn("--agent", capture["argv"])
            self.assertIn("reviewer", capture["argv"])


if __name__ == "__main__":
    unittest.main()
