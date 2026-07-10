import json
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR / "scripts"))

from harness_adapters import build_harness_invocation, decode_harness_output  # noqa: E402


def base_agent(harness, mode="read_only", approval_policy="default"):
    return {
        "id": "agent",
        "goal": "Inspect the repository.",
        "harness": harness,
        "mode": mode,
        "approval_policy": approval_policy,
        "model": None,
        "agent": None,
        "session_persistence": False,
        "dangerously_bypass_approvals_and_sandbox": False,
    }


class HarnessAdapterTests(unittest.TestCase):
    def build(self, agent, prompt="secret prompt"):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prompt_file = root / "prompt.txt"
            prompt_file.write_text(prompt, encoding="utf-8")
            return build_harness_invocation(
                agent,
                prompt,
                prompt_file,
                root,
                root / "run",
                root / "run" / "agent",
                {},
            )

    def test_grok_read_only_uses_bounded_headless_flags(self):
        agent = base_agent("grok-build")
        agent.update({"model": "grok-code-fast", "agent": "explore"})
        invocation = self.build(agent)
        argv = list(invocation.argv)
        self.assertEqual(argv[0], "grok")
        for flag in (
            "--no-plan",
            "--no-subagents",
            "--no-leader",
            "--no-ask-user",
            "--no-memory",
            "--no-auto-update",
            "--prompt-file",
        ):
            self.assertIn(flag, argv)
        self.assertEqual(argv[argv.index("--output-format") + 1], "streaming-json")
        self.assertEqual(argv[argv.index("--sandbox") + 1], "read-only")
        self.assertNotIn("--always-approve", argv)
        self.assertNotIn("secret prompt", invocation.logged_argv)

    def test_grok_patch_unattended_maps_workspace_and_always_approve(self):
        invocation = self.build(base_agent("grok-build", "patch_only", "unattended"))
        argv = list(invocation.argv)
        self.assertEqual(argv[argv.index("--sandbox") + 1], "workspace")
        self.assertIn("--always-approve", argv)

    def test_approval_mapping_stays_harness_specific(self):
        opencode = list(self.build(base_agent("opencode", approval_policy="unattended")).argv)
        claude = list(self.build(base_agent("claude-code", approval_policy="unattended")).argv)
        codex = list(self.build(base_agent("codex-cli", "patch_only", "unattended")).argv)
        self.assertIn("--auto", opencode)
        self.assertIn("--dangerously-skip-permissions", claude)
        self.assertIn("--sandbox", codex)
        self.assertIn("workspace-write", codex)
        self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", codex)

    def test_codex_dangerous_escape_hatch_removes_native_sandbox(self):
        agent = base_agent("codex-cli", "patch_only", "unattended")
        agent["dangerously_bypass_approvals_and_sandbox"] = True
        argv = list(self.build(agent).argv)
        self.assertIn("--dangerously-bypass-approvals-and-sandbox", argv)
        self.assertNotIn("--sandbox", argv)
        self.assertIn("--ephemeral", argv)

    def test_custom_goal_placeholder_is_redacted_from_event_argv(self):
        agent = base_agent("opencode")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            invocation = build_harness_invocation(
                agent,
                "generated prompt",
                root / "prompt.txt",
                root,
                root / "run",
                root / "run" / "agent",
                {"harnesses": {"opencode": {"argv": ["tool", "{goal}"]}}},
            )
        self.assertEqual(invocation.argv[1], "Inspect the repository.")
        self.assertEqual(invocation.logged_argv[1], "<goal>")

    def test_grok_streaming_decoder_handles_unknown_events(self):
        stdout = "\n".join(
            [
                json.dumps({"type": "future_event", "data": "ignored"}),
                json.dumps({"type": "text", "data": "hello "}),
                json.dumps({"type": "text", "data": "world"}),
                json.dumps({"type": "end", "stopReason": "EndTurn", "sessionId": "s"}),
            ]
        )
        decoded = decode_harness_output("grok-build", stdout)
        self.assertEqual(decoded.text, "hello world")
        self.assertIsNone(decoded.error)
        self.assertEqual(decoded.metadata["sessionId"], "s")

    def test_grok_streaming_decoder_requires_terminal_text(self):
        missing_end = decode_harness_output(
            "grok-build", json.dumps({"type": "text", "data": "partial"})
        )
        self.assertIn("end event", missing_end.error)
        empty = decode_harness_output(
            "grok-build", json.dumps({"type": "end", "stopReason": "EndTurn"})
        )
        self.assertIn("response text", empty.error)

    def test_grok_streaming_decoder_rejects_incomplete_stop_reasons(self):
        for stop_reason in ("MaxTurnRequests", "max_turn_requests", "max_tokens"):
            with self.subTest(stop_reason=stop_reason):
                stdout = "\n".join(
                    [
                        json.dumps({"type": "text", "data": "partial"}),
                        json.dumps({"type": "end", "stopReason": stop_reason}),
                    ]
                )
                decoded = decode_harness_output("grok-build", stdout)
                self.assertIn(stop_reason, decoded.error)

    def test_codex_jsonl_decoder_extracts_final_message(self):
        stdout = "\n".join(
            [
                json.dumps({"type": "thread.started", "thread_id": "t"}),
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {"type": "agent_message", "text": "final response"},
                    }
                ),
                json.dumps({"type": "turn.completed"}),
            ]
        )
        decoded = decode_harness_output("codex-cli", stdout)
        self.assertEqual(decoded.text, "final response")
        self.assertIsNone(decoded.error)


if __name__ == "__main__":
    unittest.main()
