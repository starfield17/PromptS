import json
import os
import importlib.util
import subprocess
import sys
import tempfile
import time
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

payload = {{"summary": "fake claude completed", "files_read": [], "files_changed": [], "tests_run": [], "risks": [], "recommendations": []}}
text = "SUBAGENT_RESULT_JSON_START\\n" + json.dumps(payload) + "\\nSUBAGENT_RESULT_JSON_END"
print(json.dumps({{"type": "system", "subtype": "init", "session_id": "fake-claude-session"}}))
print(json.dumps({{"type": "assistant", "message": {{"content": [{{"type": "tool_use", "id": "tool-1", "name": "Read", "input": {{"file_path": "/secret"}}}}]}}}}))
print(json.dumps({{"type": "user", "message": {{"content": [{{"type": "tool_result", "tool_use_id": "tool-1", "content": "redacted"}}]}}}}))
print(json.dumps({{"type": "result", "subtype": "success", "is_error": False, "result": text, "session_id": "fake-claude-session", "num_turns": 1}}))
""",
            encoding="utf-8",
        )
        fake_claude.chmod(0o755)
        return fake_claude

    def make_slow_fake_claude(self, bin_dir):
        fake_claude = bin_dir / "claude"
        fake_claude.write_text(
            f"""#!{sys.executable}
import json
import time

print(json.dumps({{"type": "system", "subtype": "init", "session_id": "slow"}}), flush=True)
time.sleep(60)
""",
            encoding="utf-8",
        )
        fake_claude.chmod(0o755)
        return fake_claude

    def make_fake_grok(self, bin_dir):
        fake_grok = bin_dir / "grok"
        fake_grok.write_text(
            f"""#!{sys.executable}
import json
import os
import sys

capture_path = os.environ["CAPTURE_PATH"]
with open(capture_path, "w", encoding="utf-8") as handle:
    json.dump({{
        "argv": sys.argv[1:],
        "cwd": os.getcwd(),
        "home": os.environ.get("HOME"),
        "grok_home": os.environ.get("GROK_HOME"),
    }}, handle)

payload = {{
    "summary": "fake grok completed",
    "files_read": [],
    "files_changed": [],
    "tests_run": [],
    "risks": [],
    "recommendations": [],
}}
text = "SUBAGENT_RESULT_JSON_START\\n" + json.dumps(payload) + "\\nSUBAGENT_RESULT_JSON_END"
print(json.dumps({{"type": "future_event", "data": "ignored"}}))
print(json.dumps({{"type": "text", "data": text[:20]}}))
print(json.dumps({{"type": "text", "data": text[20:]}}))
print(json.dumps({{"type": "end", "stopReason": "EndTurn", "sessionId": "fake-session", "requestId": "fake-request"}}))
""",
            encoding="utf-8",
        )
        fake_grok.chmod(0o755)
        return fake_grok

    def make_cancelled_fake_grok(self, bin_dir):
        fake_grok = bin_dir / "grok"
        fake_grok.write_text(
            f"""#!{sys.executable}
import json

print(json.dumps({{"type": "text", "data": "initial announcement"}}))
print(json.dumps({{"type": "end", "stopReason": "Cancelled", "sessionId": "cancelled-session", "requestId": "cancelled-request"}}))
""",
            encoding="utf-8",
        )
        fake_grok.chmod(0o755)
        return fake_grok

    def make_failing_fake_grok(self, bin_dir):
        fake_grok = bin_dir / "grok"
        fake_grok.write_text(
            f"""#!{sys.executable}
import json
import sys

print(json.dumps({{"type": "error", "message": "simulated Grok API failure"}}))
print(json.dumps({{"type": "end", "stopReason": "Error"}}))
sys.exit(7)
""",
            encoding="utf-8",
        )
        fake_grok.chmod(0o755)
        return fake_grok

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

    def test_claude_bounded_validation_and_defaults(self):
        runner = load_runner_module()
        packet = runner.validate_and_normalize(
            {
                "run_id": "bounded-default",
                "agents": [
                    {
                        "id": "a",
                        "goal": "g",
                        "harness": "claude-code",
                        "mode": "patch_only",
                        "allowed_paths": ["**"],
                        "allowed_tools": ["Bash(python -m pytest *)"],
                    }
                ],
            }
        )
        self.assertEqual(packet["agents"][0]["approval_policy"], "bounded")
        self.assertEqual(packet["agents"][0]["idle_timeout_sec"], 180)
        self.assertEqual(packet["agents"][0]["max_files_changed"], 50)

        invalid_agents = [
            {"harness": "claude-code", "approval_policy": "default"},
            {"harness": "opencode", "approval_policy": "bounded"},
            {
                "harness": "claude-code",
                "approval_policy": "bounded",
                "allowed_tools": ["Bash(*)"],
            },
        ]
        for index, fields in enumerate(invalid_agents):
            with self.subTest(fields=fields), self.assertRaises(runner.RunnerError):
                runner.validate_and_normalize(
                    {
                        "run_id": f"invalid-{index}",
                        "agents": [
                            {"id": "a", "goal": "g", "allowed_paths": ["**"], **fields}
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
            self.assertEqual(result["harness_metadata"], {})
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

    def test_failed_and_no_change_patch_jobs_do_not_create_patch_artifacts(self):
        for fake_fail, expected_status in ((True, "failed"), (False, "completed")):
            with self.subTest(fake_fail=fake_fail), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                init_git_repo(root)
                task = self.write_tasks(
                    root,
                    {
                        "run_id": "no-patch",
                        "defaults": {"harness": "fake", "mode": "patch_only"},
                        "agents": [
                            {
                                "id": "patcher",
                                "goal": "Return without changes.",
                                "allowed_paths": ["**"],
                                "fake_fail": fake_fail,
                            }
                        ],
                    },
                )
                process = run_cmd([sys.executable, str(RUNNER), "run", str(task), "--wait"], root)
                self.assertEqual(process.returncode, 1 if fake_fail else 0)
                agent_dir = root / ".subagents" / "no-patch" / "patcher"
                result = json.loads((agent_dir / "result.json").read_text())
                self.assertEqual(result["status"], expected_status)
                self.assertIsNone(result["patch_path"])
                self.assertIsNone(result["patch_sha256"])
                self.assertIsNone(result["policy"])
                self.assertFalse((agent_dir / "patch.diff").exists())

    def test_partial_success_policies(self):
        for success_policy, expected_code in (("require_all", 1), ("require_any", 0)):
            with self.subTest(success_policy=success_policy), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                task = self.write_tasks(
                    root,
                    {
                        "run_id": "partial",
                        "success_policy": success_policy,
                        "agents": [
                            {"id": "ok", "goal": "ok", "allowed_paths": ["**"]},
                            {
                                "id": "bad",
                                "goal": "bad",
                                "allowed_paths": ["**"],
                                "fake_fail": True,
                            },
                        ],
                    },
                )
                process = run_cmd([sys.executable, str(RUNNER), "run", str(task), "--wait"], root)
                self.assertEqual(process.returncode, expected_code)
                aggregate = json.loads((root / ".subagents" / "partial" / "result.json").read_text())
                self.assertEqual(aggregate["status"], "partial_success")
                self.assertEqual(aggregate["success_policy_satisfied"], expected_code == 0)

    def test_fail_fast_cancels_queued_agents(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = self.write_tasks(
                root,
                {
                    "run_id": "fail-fast",
                    "failure_policy": "fail_fast",
                    "agents": [
                        {
                            "id": "bad",
                            "goal": "bad",
                            "allowed_paths": ["**"],
                            "fake_fail": True,
                        },
                        {"id": "queued", "goal": "queued", "allowed_paths": ["**"]},
                    ],
                },
            )
            process = run_cmd(
                [sys.executable, str(RUNNER), "run", str(task), "--wait", "--max-concurrency", "1"],
                root,
            )
            self.assertEqual(process.returncode, 1)
            aggregate = json.loads((root / ".subagents" / "fail-fast" / "result.json").read_text())
            statuses = {item["agent_id"]: item["status"] for item in aggregate["agents"]}
            self.assertEqual(statuses, {"bad": "failed", "queued": "cancelled"})

    def test_unborn_repository_runs_read_and_patch_agents(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_cmd(["git", "init"], root)
            (root / "source.txt").write_text("source\n", encoding="utf-8")
            task = self.write_tasks(
                root,
                {
                    "run_id": "unborn",
                    "defaults": {"harness": "fake"},
                    "agents": [
                        {
                            "id": "reader",
                            "mode": "read_only",
                            "goal": "Inspect the repository.",
                            "allowed_paths": ["**"],
                            "fake_response": {"summary": "read completed"},
                        },
                        {
                            "id": "patcher",
                            "mode": "patch_only",
                            "goal": "Create a test file.",
                            "allowed_paths": ["tests/**"],
                            "fake_patch": {
                                "path": "tests/test_generated.py",
                                "content": "def test_generated():\n    assert True\n",
                            },
                        },
                    ],
                },
            )
            process = run_cmd([sys.executable, str(RUNNER), "run", str(task), "--wait"], root)
            self.assertEqual(process.returncode, 0, process.stderr)
            run_dir = root / ".subagents" / "unborn"
            reader = json.loads((run_dir / "reader" / "result.json").read_text())
            patcher = json.loads((run_dir / "patcher" / "result.json").read_text())
            self.assertEqual(reader["status"], "completed")
            self.assertEqual(patcher["status"], "completed")
            self.assertIn("tests/test_generated.py", (run_dir / "patcher" / "patch.diff").read_text())
            self.assertNotEqual(run_cmd(["git", "rev-parse", "--verify", "HEAD"], root).returncode, 0)

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

    def test_max_files_changed_blocks_patch_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_git_repo(root)
            task = self.write_tasks(
                root,
                {
                    "run_id": "file-limit",
                    "defaults": {"harness": "fake", "mode": "patch_only"},
                    "agents": [
                        {
                            "id": "patcher",
                            "goal": "Create two files.",
                            "allowed_paths": ["tests/**"],
                            "max_files_changed": 1,
                            "fake_patches": [
                                {"path": "tests/one.py", "content": "one = 1\n"},
                                {"path": "tests/two.py", "content": "two = 2\n"},
                            ],
                        }
                    ],
                },
            )
            process = run_cmd([sys.executable, str(RUNNER), "run", str(task), "--wait"], root)
            self.assertEqual(process.returncode, 1)
            agent_dir = root / ".subagents" / "file-limit" / "patcher"
            result = json.loads((agent_dir / "result.json").read_text())
            self.assertEqual(result["status"], "policy_failed")
            self.assertIn("exceeds max_files_changed", result["error"])
            self.assertIsNone(result["patch_path"])
            self.assertFalse((agent_dir / "patch.diff").exists())

    def test_fake_patch_rejects_paths_outside_workspace(self):
        for path_kind in ("absolute", "parent"):
            with self.subTest(path_kind=path_kind), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp)
                root = base / "repo"
                root.mkdir()
                init_git_repo(root)
                outside = base / "outside.txt"
                outside.write_text("keep\n", encoding="utf-8")
                raw_path = str(outside) if path_kind == "absolute" else "../escaped.txt"
                task = self.write_tasks(
                    root,
                    {
                        "run_id": "fake-escape",
                        "defaults": {"harness": "fake"},
                        "agents": [
                            {
                                "id": "patcher",
                                "mode": "patch_only",
                                "goal": "Create a file.",
                                "allowed_paths": ["**"],
                                "fake_patch": {"path": raw_path, "content": "changed\n"},
                            }
                        ],
                    },
                )
                process = run_cmd(
                    [sys.executable, str(RUNNER), "run", str(task), "--wait"], root
                )
                self.assertEqual(process.returncode, 1, process.stderr)
                result_path = root / ".subagents" / "fake-escape" / "patcher" / "result.json"
                result = json.loads(result_path.read_text(encoding="utf-8"))
                self.assertEqual(result["status"], "failed")
                self.assertIn("fake_patch", result["error"])
                self.assertEqual(outside.read_text(encoding="utf-8"), "keep\n")
                self.assertFalse((result_path.parent / "escaped.txt").exists())

    def test_fake_harness_enforces_output_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = self.write_tasks(
                root,
                {
                    "run_id": "fake-output-limit",
                    "defaults": {
                        "harness": "fake",
                        "mode": "read_only",
                        "max_output_bytes": 32,
                    },
                    "agents": [
                        {
                            "id": "reader",
                            "goal": "Return a large fake response.",
                            "allowed_paths": ["**"],
                            "fake_response": {"summary": "x" * 1000},
                        }
                    ],
                },
            )
            process = run_cmd(
                [sys.executable, str(RUNNER), "run", str(task), "--wait"], root
            )
            self.assertEqual(process.returncode, 1, process.stderr)
            agent_dir = root / ".subagents" / "fake-output-limit" / "reader"
            result = json.loads((agent_dir / "result.json").read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "output_limit")
            self.assertIn("output truncated", (agent_dir / "stdout.log").read_text())

    def test_non_git_source_root_and_copy_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            (project / "inside.txt").write_text("inside\n")
            (root / "outside.txt").write_text("outside\n")
            task = self.write_tasks(
                root,
                {
                    "run_id": "source-root",
                    "agents": [
                        {
                            "id": "reader",
                            "goal": "read",
                            "source_root": "project",
                            "allowed_paths": ["**"],
                        }
                    ],
                },
            )
            process = run_cmd([sys.executable, str(RUNNER), "run", str(task), "--wait"], root)
            self.assertEqual(process.returncode, 0, process.stderr)
            worktree = root / ".subagents" / "source-root" / "reader" / "worktree"
            self.assertTrue((worktree / "inside.txt").is_file())
            self.assertFalse((worktree / "outside.txt").exists())

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "one.txt").write_text("1")
            (root / "two.txt").write_text("2")
            task = self.write_tasks(
                root,
                {
                    "run_id": "copy-limit",
                    "agents": [
                        {
                            "id": "reader",
                            "goal": "read",
                            "allowed_paths": ["**"],
                            "max_workspace_files": 1,
                        }
                    ],
                },
            )
            process = run_cmd([sys.executable, str(RUNNER), "run", str(task), "--wait"], root)
            self.assertEqual(process.returncode, 1)
            result = json.loads(
                (root / ".subagents" / "copy-limit" / "reader" / "result.json").read_text()
            )
            self.assertIn("exceeds copy limits", result["error"])

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

    def test_claude_bounded_default_uses_isolated_home_and_no_session_persistence(self):
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
            self.assertEqual(
                capture["argv"][capture["argv"].index("--permission-mode") + 1],
                "dontAsk",
            )
            self.assertIn("--output-format", capture["argv"])
            self.assertNotIn("--dangerously-skip-permissions", capture["argv"])
            result = json.loads(
                (root / ".subagents" / "claude-default" / "reader" / "result.json").read_text()
            )
            self.assertEqual(result["harness_metadata"]["session_id"], "fake-claude-session")
            events = (
                root / ".subagents" / "claude-default" / "reader" / "events.jsonl"
            ).read_text()
            self.assertIn('"event": "tool_started"', events)
            self.assertNotIn("/secret", events)

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

    @unittest.skipIf(os.name != "posix", "process-group cancellation requires POSIX")
    def test_status_and_cancel_running_and_queued_agents(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "repo"
            root.mkdir()
            bin_dir = base / "bin"
            bin_dir.mkdir()
            self.make_slow_fake_claude(bin_dir)
            task = self.write_tasks(
                root,
                {
                    "run_id": "cancel-live",
                    "defaults": {
                        "harness": "claude-code",
                        "mode": "read_only",
                    },
                    "agents": [
                        {"id": "running", "goal": "wait", "allowed_paths": ["**"]},
                        {"id": "queued", "goal": "wait", "allowed_paths": ["**"]},
                    ],
                },
            )
            env = dict(os.environ)
            env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
            runner_process = subprocess.Popen(
                [
                    sys.executable,
                    str(RUNNER),
                    "run",
                    str(task),
                    "--wait",
                    "--max-concurrency",
                    "1",
                ],
                cwd=root,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            runtime_path = root / ".subagents" / "cancel-live" / "running" / "runtime.json"
            runtime = None
            for _ in range(100):
                if runtime_path.exists():
                    runtime = json.loads(runtime_path.read_text())
                    if runtime.get("status") == "running":
                        break
                time.sleep(0.05)
            self.assertIsNotNone(runtime)
            assert runtime is not None
            pid = int(runtime["pid"])
            status = run_cmd(
                [sys.executable, str(RUNNER), "status", ".subagents/cancel-live"],
                root,
                env=env,
            )
            self.assertIn("Status: running", status.stdout)
            self.assertIn(f"pid={pid}", status.stdout)
            self.assertIn("queued: queued", status.stdout)

            cancel = run_cmd(
                [sys.executable, str(RUNNER), "cancel", ".subagents/cancel-live"],
                root,
                env=env,
            )
            self.assertEqual(cancel.returncode, 0, cancel.stderr)
            self.assertIn("signalled=1", cancel.stdout)
            runner_process.communicate(timeout=10)
            aggregate = json.loads(
                (root / ".subagents" / "cancel-live" / "result.json").read_text()
            )
            statuses = {item["agent_id"]: item["status"] for item in aggregate["agents"]}
            self.assertEqual(statuses, {"running": "cancelled", "queued": "cancelled"})
            self.assertFalse(Path(f"/proc/{pid}").exists())

    def test_runner_reports_idle_timeout(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "repo"
            root.mkdir()
            bin_dir = base / "bin"
            bin_dir.mkdir()
            self.make_slow_fake_claude(bin_dir)
            task = self.write_tasks(
                root,
                {
                    "run_id": "idle-timeout",
                    "defaults": {
                        "harness": "claude-code",
                        "mode": "read_only",
                        "idle_timeout_sec": 1,
                    },
                    "agents": [
                        {"id": "reader", "goal": "wait", "allowed_paths": ["**"]}
                    ],
                },
            )
            env = dict(os.environ)
            env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
            process = run_cmd([sys.executable, str(RUNNER), "run", str(task), "--wait"], root, env=env)
            self.assertEqual(process.returncode, 1)
            result = json.loads(
                (root / ".subagents" / "idle-timeout" / "reader" / "result.json").read_text()
            )
            self.assertEqual(result["status"], "idle_timeout")
            self.assertIn("no activity for 1 seconds", result["error"])

    def test_grok_adapter_runs_streaming_json_and_preserves_explicit_host_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "repo"
            root.mkdir()
            bin_dir = base / "bin"
            bin_dir.mkdir()
            capture_path = base / "capture.json"
            host_home = base / "host-home"
            host_home.mkdir()
            host_grok_home = base / "host-grok-home"
            host_grok_home.mkdir()
            self.make_fake_grok(bin_dir)
            task = self.write_tasks(
                root,
                {
                    "run_id": "grok-read",
                    "defaults": {"harness": "grok-build", "mode": "read_only"},
                    "agents": [
                        {
                            "id": "reader",
                            "goal": "Run fake Grok.",
                            "home_policy": "host",
                            "allowed_paths": ["**"],
                        }
                    ],
                },
            )
            env = dict(os.environ)
            env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
            env["CAPTURE_PATH"] = str(capture_path)
            env["HOME"] = str(host_home)
            env["GROK_HOME"] = str(host_grok_home)
            process = run_cmd([sys.executable, str(RUNNER), "run", str(task), "--wait"], root, env=env)
            self.assertEqual(process.returncode, 0, process.stderr)
            result = json.loads(
                (root / ".subagents" / "grok-read" / "reader" / "result.json").read_text()
            )
            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["summary"], "fake grok completed")
            self.assertEqual(
                result["harness_metadata"],
                {
                    "stopReason": "EndTurn",
                    "sessionId": "fake-session",
                    "requestId": "fake-request",
                },
            )
            capture = json.loads(capture_path.read_text())
            self.assertEqual(capture["home"], str(host_home))
            self.assertEqual(capture["grok_home"], str(host_grok_home))
            self.assertIn("--no-leader", capture["argv"])
            self.assertIn("--prompt-file", capture["argv"])
            self.assertNotIn("--always-approve", capture["argv"])
            events = (root / ".subagents" / "grok-read" / "reader" / "events.jsonl").read_text()
            self.assertNotIn("Run fake Grok.", events)

    def test_grok_nonzero_exit_preserves_stream_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "repo"
            root.mkdir()
            bin_dir = base / "bin"
            bin_dir.mkdir()
            self.make_failing_fake_grok(bin_dir)
            task = self.write_tasks(
                root,
                {
                    "run_id": "grok-failure",
                    "defaults": {"harness": "grok-build", "mode": "read_only"},
                    "agents": [
                        {"id": "reader", "goal": "Run failing Grok.", "allowed_paths": ["**"]}
                    ],
                },
            )
            env = dict(os.environ)
            env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
            process = run_cmd(
                [sys.executable, str(RUNNER), "run", str(task), "--wait"],
                root,
                env=env,
            )
            self.assertEqual(process.returncode, 1, process.stderr)
            result = json.loads(
                (root / ".subagents" / "grok-failure" / "reader" / "result.json").read_text()
            )
            self.assertEqual(result["status"], "failed")
            self.assertIn("simulated Grok API failure", result["error"])
            self.assertIn("harness exited with code 7", result["error"])

    def test_grok_cancelled_result_preserves_correlation_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "repo"
            root.mkdir()
            bin_dir = base / "bin"
            bin_dir.mkdir()
            self.make_cancelled_fake_grok(bin_dir)
            task = self.write_tasks(
                root,
                {
                    "run_id": "grok-cancelled",
                    "defaults": {"harness": "grok-build", "mode": "read_only"},
                    "agents": [
                        {"id": "reader", "goal": "Run cancelled Grok.", "allowed_paths": ["**"]}
                    ],
                },
            )
            env = dict(os.environ)
            env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
            process = run_cmd(
                [sys.executable, str(RUNNER), "run", str(task), "--wait"],
                root,
                env=env,
            )
            self.assertEqual(process.returncode, 1, process.stderr)
            result = json.loads(
                (root / ".subagents" / "grok-cancelled" / "reader" / "result.json").read_text()
            )
            self.assertEqual(result["status"], "failed")
            self.assertIn("Cancelled", result["error"])
            self.assertEqual(
                result["harness_metadata"],
                {
                    "stopReason": "Cancelled",
                    "sessionId": "cancelled-session",
                    "requestId": "cancelled-request",
                },
            )

    def test_grok_isolated_home_overrides_inherited_grok_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "repo"
            root.mkdir()
            bin_dir = base / "bin"
            bin_dir.mkdir()
            capture_path = base / "capture.json"
            inherited_grok_home = base / "host-grok-home"
            inherited_grok_home.mkdir()
            self.make_fake_grok(bin_dir)
            task = self.write_tasks(
                root,
                {
                    "run_id": "grok-isolated",
                    "defaults": {"harness": "grok-build", "mode": "read_only"},
                    "agents": [
                        {"id": "reader", "goal": "Run fake Grok.", "allowed_paths": ["**"]}
                    ],
                },
            )
            env = dict(os.environ)
            env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
            env["CAPTURE_PATH"] = str(capture_path)
            env["GROK_HOME"] = str(inherited_grok_home)
            process = run_cmd([sys.executable, str(RUNNER), "run", str(task), "--wait"], root, env=env)
            self.assertEqual(process.returncode, 0, process.stderr)
            capture = json.loads(capture_path.read_text())
            self.assertNotEqual(capture["grok_home"], str(inherited_grok_home))
            self.assertTrue(capture["grok_home"].endswith("/vendor-home/grok"))
            self.assertTrue(Path(capture["grok_home"]).is_dir())

    def test_invalid_protocol_types_fail_without_traceback(self):
        for field, value in (("mode", []), ("approval_policy", []), ("timeout_sec", 1.9)):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                agent = {"id": "reader", "goal": "g", "allowed_paths": ["**"], field: value}
                task = self.write_tasks(root, {"run_id": "invalid", "agents": [agent]})
                process = run_cmd([sys.executable, str(RUNNER), "run", str(task), "--wait"], root)
                self.assertEqual(process.returncode, 2)
                self.assertNotIn("Traceback", process.stderr)

    def test_malformed_task_json_fails_without_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = root / "bad.json"
            task.write_text("{bad", encoding="utf-8")
            process = run_cmd([sys.executable, str(RUNNER), "run", str(task), "--wait"], root)
            self.assertEqual(process.returncode, 2)
            self.assertIn("Could not load task packet", process.stderr)
            self.assertNotIn("Traceback", process.stderr)

    def test_dot_segment_ids_are_rejected_before_output_cleanup(self):
        for run_id, agent_id in (("..", "reader"), ("safe", ".."), (".", "reader")):
            with self.subTest(run_id=run_id, agent_id=agent_id), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                sentinel = root / ".subagents" / "sentinel.txt"
                sentinel.parent.mkdir()
                sentinel.write_text("keep", encoding="utf-8")
                task = self.write_tasks(
                    root,
                    {
                        "run_id": run_id,
                        "agents": [
                            {"id": agent_id, "goal": "g", "allowed_paths": ["**"]}
                        ],
                    },
                )
                process = run_cmd([sys.executable, str(RUNNER), "run", str(task), "--wait"], root)
                self.assertEqual(process.returncode, 2)
                self.assertTrue(sentinel.exists())

    @unittest.skipIf(os.name == "nt", "symlink semantics differ on Windows")
    def test_output_symlinks_are_rejected_before_cleanup(self):
        for symlink_run in (False, True):
            with self.subTest(symlink_run=symlink_run), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                outside = root / "outside"
                outside.mkdir()
                sentinel = outside / "sentinel.txt"
                sentinel.write_text("keep", encoding="utf-8")
                output_root = root / ".subagents"
                if symlink_run:
                    output_root.mkdir()
                    (output_root / "safe").symlink_to(outside, target_is_directory=True)
                else:
                    output_root.symlink_to(outside, target_is_directory=True)
                task = self.write_tasks(
                    root,
                    {
                        "run_id": "safe",
                        "agents": [{"id": "reader", "goal": "g", "allowed_paths": ["**"]}],
                    },
                )
                process = run_cmd([sys.executable, str(RUNNER), "run", str(task), "--wait"], root)
                self.assertEqual(process.returncode, 2)
                self.assertTrue(sentinel.exists())

    @unittest.skipIf(os.name == "nt", "symlink semantics differ on Windows")
    def test_output_leaf_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outside = root / "outside.txt"
            outside.write_text("keep\n", encoding="utf-8")
            run_dir = root / ".subagents" / "safe"
            run_dir.mkdir(parents=True)
            (run_dir / "tasks.normalized.json").symlink_to(outside)
            task = self.write_tasks(
                root,
                {
                    "run_id": "safe",
                    "agents": [{"id": "reader", "goal": "g", "allowed_paths": ["**"]}],
                },
            )
            process = run_cmd(
                [sys.executable, str(RUNNER), "run", str(task), "--wait"], root
            )
            self.assertEqual(process.returncode, 2)
            self.assertIn("symlink output", process.stderr)
            self.assertEqual(outside.read_text(encoding="utf-8"), "keep\n")

    @unittest.skipIf(os.name == "nt", "requires POSIX surrogateescape filenames")
    def test_non_utf8_changed_filename_does_not_break_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_git_repo(root)
            raw_name = b"bad-\xff.txt"
            name = os.fsdecode(raw_name)
            path_bytes = os.fsencode(root) + b"/" + raw_name
            fd = os.open(path_bytes, os.O_WRONLY | os.O_CREAT, 0o644)
            with os.fdopen(fd, "wb") as handle:
                handle.write(b"base\n")
            run_cmd(["git", "add", "--", name], root)
            run_cmd(["git", "commit", "-m", "add non-utf8 file"], root)
            task = self.write_tasks(
                root,
                {
                    "run_id": "non-utf8",
                    "defaults": {"harness": "fake", "mode": "patch_only"},
                    "agents": [
                        {
                            "id": "patcher",
                            "goal": "Append to the file.",
                            "allowed_paths": ["**"],
                            "fake_patch": {"path": name, "content": "agent\n", "append": True},
                        }
                    ],
                },
            )
            process = run_cmd([sys.executable, str(RUNNER), "run", str(task), "--wait"], root)
            self.assertEqual(process.returncode, 0, process.stderr)
            summary = root / ".subagents" / "non-utf8" / "summary.md"
            self.assertTrue(summary.exists())
            self.assertIn(b"bad-\\udcff.txt", summary.read_bytes())


if __name__ == "__main__":
    unittest.main()
