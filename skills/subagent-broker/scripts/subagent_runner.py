#!/usr/bin/env python3
"""Run bounded subagent jobs through local harness CLIs."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import hashlib
import json
import os
import re
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from harness_adapters import (  # noqa: E402
    HarnessAdapterError,
    build_harness_invocation,
    decode_harness_output,
    normalize_harness_stream_line,
    supported_harnesses,
)
from policy_check import (  # noqa: E402
    DEFAULT_DENY,
    PolicyParseError,
    check_paths,
    check_policy,
    normalize_path,
)
from runner_runtime import (  # noqa: E402
    RunnerRuntimeError,
    append_bytes_no_follow,
    atomic_write_bytes,
    changed_snapshot_paths,
    cleanup_agent_dir,
    collect_git_diff,
    git_changed_paths,
    git_root,
    prepare_workspace,
    process_group_exists,
    process_start_token,
    restore_trusted_git_metadata,
    run_external_harness,
    snapshot_files,
    verify_workspace_identity,
)


SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
SUPPORTED_MODES = {"read_only", "patch_only"}
UNSUPPORTED_MODES = {"direct_write", "shared_workspace", "network_sandbox", "daemon"}
SUPPORTED_HOME_POLICIES = {"isolated", "host"}
SUPPORTED_APPROVAL_POLICIES = {"bounded", "default", "unattended"}
SECRET_ENV_RE = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|COOKIE|SESSION)", re.I)
JSON_START = "SUBAGENT_RESULT_JSON_START"
JSON_END = "SUBAGENT_RESULT_JSON_END"


class RunnerError(Exception):
    pass


class UserCancelled(Exception):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def rel_display(path: Path) -> str:
    with contextlib.suppress(ValueError):
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    return path.as_posix()


def ensure_safe_id(value: str, field: str) -> None:
    if not value or value in {".", ".."} or not SAFE_ID_RE.fullmatch(value):
        raise RunnerError(f"{field} must contain only letters, digits, underscore, dot, or hyphen: {value!r}")


def safe_child(base: Path, identifier: str, field: str) -> Path:
    if base.is_symlink():
        raise RunnerError(f"{field} output base must not be a symlink: {base}")
    candidate = base / identifier
    if candidate.is_symlink():
        raise RunnerError(f"{field} output path must not be a symlink: {candidate}")
    if candidate.resolve().parent != base.resolve():
        raise RunnerError(f"{field} escapes its output directory: {identifier!r}")
    return candidate


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def write_text(path: Path, text: str) -> None:
    try:
        data = text.encode("utf-8", errors="backslashreplace")
        atomic_write_bytes(path, data)
    except RunnerRuntimeError as exc:
        raise RunnerError(str(exc)) from exc


def write_json(path: Path, data: Any) -> None:
    write_text(path, json.dumps(data, indent=2, sort_keys=True) + "\n")


def load_task_packet(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    try:
        if suffix in {".yaml", ".yml"}:
            try:
                import yaml  # type: ignore
            except ImportError as exc:
                raise RunnerError("YAML task packets require PyYAML. Use JSON or install PyYAML.") from exc
            with path.open("r", encoding="utf-8") as handle:
                loaded = yaml.safe_load(handle)
        else:
            with path.open("r", encoding="utf-8") as handle:
                loaded = json.load(handle)
    except RunnerError:
        raise
    except (OSError, ValueError) as exc:
        raise RunnerError(f"Could not load task packet {path}: {exc}") from exc
    if not isinstance(loaded, dict):
        raise RunnerError("Task packet must be a JSON object")
    return loaded


def normalize_bool(value: Any, field: str, default: bool = False) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        raise RunnerError(f"{field} must be a boolean")
    return value


def normalize_positive_int(value: Any, field: str, default: int) -> int:
    if value is None:
        return default
    if type(value) is not int or value <= 0:
        raise RunnerError(f"{field} must be a positive integer")
    return value


def normalize_list(value: Any, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise RunnerError(f"{field} must be a list of strings")
    return list(value)


def normalize_source_root(value: Any, field: str) -> str:
    if value is None or value == ".":
        return "."
    if not isinstance(value, str):
        raise RunnerError(f"{field} must be a relative directory path")
    try:
        return normalize_path(value)
    except PolicyParseError as exc:
        raise RunnerError(f"{field}: {exc}") from exc


def validate_and_normalize(packet: dict[str, Any]) -> dict[str, Any]:
    run_id = packet.get("run_id")
    if not isinstance(run_id, str):
        raise RunnerError("run_id is required")
    ensure_safe_id(run_id, "run_id")

    defaults = packet.get("defaults", {})
    if defaults is None:
        defaults = {}
    if not isinstance(defaults, dict):
        raise RunnerError("defaults must be an object")

    raw_agents = packet.get("agents")
    if not isinstance(raw_agents, list) or not raw_agents:
        raise RunnerError("agents must be a non-empty list")

    harness_names = supported_harnesses()
    agents: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for raw in raw_agents:
        if not isinstance(raw, dict):
            raise RunnerError("each agent must be an object")
        agent = {**defaults, **raw}
        agent_id = agent.get("id")
        if not isinstance(agent_id, str):
            raise RunnerError("agent id is required")
        ensure_safe_id(agent_id, "agent id")
        if agent_id in seen_ids:
            raise RunnerError(f"duplicate agent id: {agent_id}")
        seen_ids.add(agent_id)

        goal = agent.get("goal")
        if not isinstance(goal, str) or not goal.strip():
            raise RunnerError(f"agent {agent_id}: goal is required")

        mode = agent.get("mode", "read_only")
        if isinstance(mode, str) and mode in UNSUPPORTED_MODES:
            raise RunnerError(f"agent {agent_id}: unsupported mode for MVP: {mode}")
        if not isinstance(mode, str) or mode not in SUPPORTED_MODES:
            raise RunnerError(f"agent {agent_id}: mode must be one of {sorted(SUPPORTED_MODES)}")

        harness = agent.get("harness", "fake")
        if not isinstance(harness, str) or harness not in harness_names:
            raise RunnerError(f"agent {agent_id}: harness must be one of {sorted(harness_names)}")

        for field in ("model", "agent"):
            value = agent.get(field)
            if value is not None and not isinstance(value, str):
                raise RunnerError(f"agent {agent_id}: {field} must be a string")

        timeout_sec = normalize_positive_int(
            agent.get("timeout_sec"), f"agent {agent_id}: timeout_sec", 1800
        )
        max_output_bytes = normalize_positive_int(
            agent.get("max_output_bytes"), f"agent {agent_id}: max_output_bytes", 2_000_000
        )
        allowed_paths = normalize_list(agent.get("allowed_paths", []), "allowed_paths")
        deny_paths = normalize_list(agent.get("deny_paths", []), "deny_paths")
        return_fields = normalize_list(agent.get("return", []), "return")
        inherit_env = normalize_bool(
            agent.get("inherit_env"), f"agent {agent_id}: inherit_env", True
        )

        home_policy = agent.get("home_policy", "isolated")
        if not isinstance(home_policy, str) or home_policy not in SUPPORTED_HOME_POLICIES:
            raise RunnerError(
                f"agent {agent_id}: home_policy must be one of {sorted(SUPPORTED_HOME_POLICIES)}"
            )
        if home_policy == "host" and not inherit_env:
            raise RunnerError(f"agent {agent_id}: home_policy 'host' requires inherit_env true")

        approval_explicit = "approval_policy" in agent
        approval_policy = agent.get(
            "approval_policy", "bounded" if harness == "claude-code" else "default"
        )
        if not isinstance(approval_policy, str) or approval_policy not in SUPPORTED_APPROVAL_POLICIES:
            raise RunnerError(
                f"agent {agent_id}: approval_policy must be one of "
                f"{sorted(SUPPORTED_APPROVAL_POLICIES)}"
            )
        if harness == "claude-code" and approval_policy == "default":
            raise RunnerError(
                f"agent {agent_id}: claude-code headless jobs cannot use approval_policy "
                "'default'; use 'bounded' or explicitly opt into 'unattended'"
            )
        if approval_policy == "bounded" and harness != "claude-code":
            raise RunnerError(
                f"agent {agent_id}: approval_policy 'bounded' is only valid for claude-code"
            )

        allowed_tools = normalize_list(agent.get("allowed_tools"), f"agent {agent_id}: allowed_tools")
        if allowed_tools and (harness != "claude-code" or approval_policy != "bounded"):
            raise RunnerError(
                f"agent {agent_id}: allowed_tools requires claude-code with approval_policy 'bounded'"
            )
        for tool in allowed_tools:
            normalized_tool = tool.strip()
            if normalized_tool in {"Bash", "Bash(*)"}:
                raise RunnerError(
                    f"agent {agent_id}: bounded Bash rules must name a command pattern"
                )
            if normalized_tool.startswith("Bash(") and not normalized_tool.endswith(")"):
                raise RunnerError(f"agent {agent_id}: invalid Bash tool rule: {tool!r}")
            if mode == "read_only" and normalized_tool.split("(", 1)[0] in {
                "Edit",
                "Write",
                "NotebookEdit",
            }:
                raise RunnerError(
                    f"agent {agent_id}: read_only jobs cannot allow mutating tool {tool!r}"
                )

        legacy_skip = normalize_bool(
            agent.get("dangerously_skip_permissions"),
            f"agent {agent_id}: dangerously_skip_permissions",
            False,
        )
        if "dangerously_skip_permissions" in agent and harness != "claude-code":
            raise RunnerError(
                f"agent {agent_id}: dangerously_skip_permissions is only valid for claude-code"
            )
        if legacy_skip:
            if approval_explicit and approval_policy != "unattended":
                raise RunnerError(
                    f"agent {agent_id}: dangerously_skip_permissions conflicts with approval_policy"
                )
            approval_policy = "unattended"

        codex_bypass = normalize_bool(
            agent.get("dangerously_bypass_approvals_and_sandbox"),
            f"agent {agent_id}: dangerously_bypass_approvals_and_sandbox",
            False,
        )
        if "dangerously_bypass_approvals_and_sandbox" in agent and harness != "codex-cli":
            raise RunnerError(
                f"agent {agent_id}: dangerously_bypass_approvals_and_sandbox is only valid for codex-cli"
            )
        if codex_bypass:
            if approval_explicit and approval_policy != "unattended":
                raise RunnerError(
                    f"agent {agent_id}: dangerously_bypass_approvals_and_sandbox conflicts "
                    "with approval_policy"
                )
            approval_policy = "unattended"
        if allowed_tools and approval_policy != "bounded":
            raise RunnerError(
                f"agent {agent_id}: allowed_tools cannot be combined with unattended permissions"
            )

        normalized = dict(agent)
        normalized.update(
            {
                "id": agent_id,
                "goal": goal,
                "mode": mode,
                "harness": harness,
                "approval_policy": approval_policy,
                "allowed_tools": allowed_tools,
                "timeout_sec": timeout_sec,
                "idle_timeout_sec": normalize_positive_int(
                    agent.get("idle_timeout_sec"),
                    f"agent {agent_id}: idle_timeout_sec",
                    180,
                ),
                "max_files_changed": normalize_positive_int(
                    agent.get("max_files_changed"),
                    f"agent {agent_id}: max_files_changed",
                    50,
                ),
                "source_root": normalize_source_root(
                    agent.get("source_root"), f"agent {agent_id}: source_root"
                ),
                "max_workspace_files": normalize_positive_int(
                    agent.get("max_workspace_files"),
                    f"agent {agent_id}: max_workspace_files",
                    25_000,
                ),
                "max_workspace_bytes": normalize_positive_int(
                    agent.get("max_workspace_bytes"),
                    f"agent {agent_id}: max_workspace_bytes",
                    1_073_741_824,
                ),
                "max_output_bytes": max_output_bytes,
                "allowed_paths": allowed_paths,
                "deny_paths": deny_paths,
                "effective_deny_paths": sorted(set([*DEFAULT_DENY, *deny_paths])),
                "return": return_fields,
                "allow_binary_changes": normalize_bool(
                    agent.get("allow_binary_changes"),
                    f"agent {agent_id}: allow_binary_changes",
                    False,
                ),
                "allow_deletes": normalize_bool(
                    agent.get("allow_deletes"), f"agent {agent_id}: allow_deletes", False
                ),
                "inherit_env": inherit_env,
                "home_policy": home_policy,
                "dangerously_skip_permissions": legacy_skip,
                "dangerously_bypass_approvals_and_sandbox": codex_bypass,
                "session_persistence": normalize_bool(
                    agent.get("session_persistence"),
                    f"agent {agent_id}: session_persistence",
                    False,
                ),
            }
        )
        agents.append(normalized)

    failure_policy = packet.get("failure_policy", "collect_all")
    if failure_policy not in {"collect_all", "fail_fast"}:
        raise RunnerError("failure_policy must be 'collect_all' or 'fail_fast'")
    success_policy = packet.get("success_policy", "require_all")
    if success_policy not in {"require_all", "require_any"}:
        raise RunnerError("success_policy must be 'require_all' or 'require_any'")
    return {
        "run_id": run_id,
        "defaults": defaults,
        "failure_policy": failure_policy,
        "success_policy": success_policy,
        "agents": agents,
    }


def load_config() -> dict[str, Any]:
    config_path = SKILL_DIR / "config.json"
    if not config_path.exists():
        return {}
    try:
        with config_path.open("r", encoding="utf-8") as handle:
            loaded = json.load(handle)
    except (OSError, ValueError) as exc:
        raise RunnerError(f"Could not load config.json: {exc}") from exc
    if not isinstance(loaded, dict):
        raise RunnerError("config.json must contain an object")
    return loaded


class EventLogger:
    def __init__(self, path: Path, agent_id: str) -> None:
        self.path = path
        self.agent_id = agent_id
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, event: str, **fields: Any) -> None:
        payload = {"event": event, "ts": now_iso(), "agent_id": self.agent_id, **fields}
        append_bytes_no_follow(
            self.path,
            (json.dumps(payload, sort_keys=True) + "\n").encode("utf-8"),
        )


class RuntimeTracker:
    def __init__(self, path: Path, events: EventLogger, harness: str) -> None:
        self.path = path
        self.events = events
        self.harness = harness
        self.active_tools: dict[str, dict[str, Any]] = {}
        self.state: dict[str, Any] = {
            "status": "preparing",
            "runner_pid": os.getpid(),
            "pid": None,
            "pgid": None,
            "process_start_token": None,
            "started_at": now_iso(),
            "last_activity_at": None,
            "current_tool": None,
            "tool_calls": 0,
            "stdout_bytes": 0,
            "stderr_bytes": 0,
        }
        self._persist()

    def _persist(self) -> None:
        write_json(self.path, self.state)

    def process_started(self, pid: int, pgid: int, start_token: str | None) -> None:
        self.state.update(
            {
                "status": "running",
                "pid": pid,
                "pgid": pgid,
                "process_start_token": start_token,
                "last_activity_at": now_iso(),
            }
        )
        self._persist()

    def activity(self, stream_name: str, total_bytes: int) -> None:
        self.state[f"{stream_name}_bytes"] = total_bytes
        self.state["last_activity_at"] = now_iso()
        self._persist()

    def stream_line(self, line: str) -> None:
        for payload in normalize_harness_stream_line(self.harness, line):
            event = str(payload.pop("event"))
            timestamp = now_iso()
            if event == "tool_started":
                tool_id = str(payload.get("tool_id") or f"tool-{self.state['tool_calls'] + 1}")
                tool = {
                    "id": tool_id,
                    "name": payload.get("tool_name"),
                    "started_at": timestamp,
                }
                self.active_tools[tool_id] = tool
                self.state["tool_calls"] += 1
                self.state["current_tool"] = tool
            elif event == "tool_finished":
                tool_id = str(payload.get("tool_id") or "")
                self.active_tools.pop(tool_id, None)
                self.state["current_tool"] = next(
                    reversed(self.active_tools.values()), None
                )
            self.state["last_activity_at"] = timestamp
            self.events.write(event, **payload)
            self._persist()

    def finish(self, status: str) -> None:
        self.state.update(
            {
                "status": "finished",
                "terminal_status": status,
                "current_tool": None,
                "ended_at": now_iso(),
            }
        )
        self._persist()


def cancel_marker(run_dir: Path) -> Path:
    return run_dir / "cancel.json"


def cancellation_requested(run_dir: Path) -> bool:
    return cancel_marker(run_dir).is_file()


def generate_prompt(agent: dict[str, Any]) -> str:
    allowed = "\n".join(f"- {path}" for path in agent["allowed_paths"]) or "- none"
    denied = "\n".join(f"- {path}" for path in agent["effective_deny_paths"]) or "- none"
    returns = "\n".join(f"- {field}" for field in agent["return"]) or "- summary"
    tool_rules = "\n".join(f"- {tool}" for tool in agent.get("allowed_tools", [])) or "- none"
    return f"""You are a bounded subagent launched by a parent Codex agent.

Agent ID: {agent['id']}
Mode: {agent['mode']}
Original repository subdirectory: {agent.get('repo_subdir') or '.'}
Goal:
{agent['goal']}

Allowed paths:
{allowed}

Denied paths:
{denied}

Expected return fields:
{returns}

Explicit additional tool rules:
{tool_rules}

Rules:
- Work only on the assigned goal.
- Do not inspect files outside allowed paths unless necessary for imports or references.
- Never read secrets, credentials, .env files, .git internals, SSH keys, or token caches.
- Do not communicate with other subagents.
- Do not rely on prior conversation context.
- Return concise results.
- If mode is read_only, do not modify files.
- If mode is patch_only, edit only files under allowed paths.
- Invoke Bash only with a command that matches an explicit allowed tool rule.
- Do not apply patches to the parent workspace.

At the end, include a final JSON object between these markers:

{JSON_START}
{{
  "summary": "...",
  "files_read": [],
  "files_changed": [],
  "tests_run": [],
  "risks": [],
  "recommendations": []
}}
{JSON_END}
"""


def initial_result(
    run_id: str,
    agent: dict[str, Any],
    agent_dir: Path,
    started_at: str,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "agent_id": agent["id"],
        "status": "running",
        "mode": agent["mode"],
        "harness": agent["harness"],
        "model": agent.get("model"),
        "approval_policy": agent["approval_policy"],
        "source_repo_root": agent.get("source_repo_root"),
        "source_root": agent.get("resolved_source_root"),
        "baseline_commit": None,
        "baseline_manifest_path": None,
        "baseline_manifest_sha256": None,
        "repo_subdir": agent.get("repo_subdir") or ".",
        "summary": "",
        "files_read": [],
        "files_changed": [],
        "patch_path": None,
        "patch_sha256": None,
        "tests_run": [],
        "risks": [],
        "recommendations": [],
        "harness_metadata": {},
        "runtime_path": rel_display(agent_dir / "runtime.json"),
        "policy": None,
        "error": None,
        "started_at": started_at,
        "ended_at": None,
        "duration_sec": 0.0,
        "log_path": rel_display(agent_dir / "events.jsonl"),
    }


def parse_subagent_result(stdout: str) -> dict[str, Any]:
    pattern = re.compile(
        re.escape(JSON_START) + r"\s*(\{.*?\})\s*" + re.escape(JSON_END),
        re.DOTALL,
    )
    match = pattern.search(stdout)
    if not match:
        summary = stdout.strip()
        return {"summary": summary[:2000] if summary else "No structured result returned."}
    try:
        loaded = json.loads(match.group(1))
        if isinstance(loaded, dict):
            return loaded
    except json.JSONDecodeError:
        pass
    return {"summary": stdout.strip()[:2000] or "Structured result block could not be parsed."}


def merge_result_fields(base: dict[str, Any], parsed: dict[str, Any]) -> None:
    for key in ("summary", "files_read", "files_changed", "tests_run", "risks", "recommendations"):
        value = parsed.get(key)
        if key == "summary" and isinstance(value, str):
            base[key] = value
        elif key != "summary" and isinstance(value, list):
            base[key] = value


def build_env(agent: dict[str, Any], agent_dir: Path, cwd: Path) -> dict[str, str]:
    env = dict(os.environ) if agent.get("inherit_env", True) else {}
    if agent["harness"] == "fake" or not agent.get("inherit_env", True):
        env = {key: value for key, value in env.items() if not SECRET_ENV_RE.search(key)}

    absolute_agent_dir = agent_dir.resolve()
    absolute_cwd = cwd.resolve()
    tmp = absolute_agent_dir / "tmp"
    cache = absolute_agent_dir / "cache"
    config = absolute_agent_dir / "config"
    data = absolute_agent_dir / "data"
    home = absolute_agent_dir / "home"
    if agent.get("home_policy", "isolated") == "host":
        host_home = env.get("HOME")
        if not host_home:
            raise RunnerError("home_policy 'host' requires HOME in the inherited environment")
        home_value = host_home
        directories = (tmp, cache)
    else:
        home_value = str(home)
        directories = (home, tmp, cache, config, data)
    for path in directories:
        path.mkdir(parents=True, exist_ok=True)

    env.update(
        {
            "SUBAGENT_RUN_ID": str(agent["run_id"]),
            "SUBAGENT_AGENT_ID": str(agent["id"]),
            "SUBAGENT_MODE": str(agent["mode"]),
            "SUBAGENT_DIR": str(absolute_agent_dir),
            "HOME": home_value,
            "TMPDIR": str(tmp),
            "XDG_CACHE_HOME": str(cache),
            "PWD": str(absolute_cwd),
        }
    )
    if agent.get("home_policy", "isolated") == "isolated":
        vendor_home = absolute_agent_dir / "vendor-home"
        grok_home = vendor_home / "grok"
        codex_home = vendor_home / "codex"
        claude_home = vendor_home / "claude"
        for path in (grok_home, codex_home, claude_home):
            path.mkdir(parents=True, exist_ok=True)
        env.update(
            {
                "XDG_CONFIG_HOME": str(config),
                "XDG_DATA_HOME": str(data),
                "GROK_HOME": str(grok_home),
                "CODEX_HOME": str(codex_home),
                "CLAUDE_CONFIG_DIR": str(claude_home),
            }
        )
    return env


def _safe_fake_patch_target(cwd: Path, raw_path: str) -> tuple[Path, str]:
    try:
        normalized = normalize_path(raw_path)
    except PolicyParseError as exc:
        raise RunnerError(f"fake_patch path is unsafe: {exc}") from exc
    root = cwd.resolve()
    target = cwd / Path(normalized)
    try:
        target.parent.resolve(strict=False).relative_to(root)
    except ValueError as exc:
        raise RunnerError(f"fake_patch path escapes the isolated workspace: {raw_path}") from exc
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.parent.resolve().relative_to(root)
    except ValueError as exc:
        raise RunnerError(f"fake_patch parent escapes the isolated workspace: {raw_path}") from exc
    if target.is_symlink():
        raise RunnerError(f"fake_patch target must not be a symlink: {raw_path}")
    return target, normalized


def _persist_fake_stream(
    text: str,
    path: Path,
    limit: int,
    events: EventLogger,
    event: str,
) -> tuple[str, bool]:
    raw = text.encode("utf-8")
    truncated = len(raw) > limit
    captured = raw[:limit]
    persisted = captured
    if truncated:
        persisted += b"\n[output truncated: max_output_bytes exceeded]\n"
    atomic_write_bytes(path, persisted)
    events.write(event, bytes=len(raw), truncated=truncated)
    return captured.decode("utf-8", errors="replace"), truncated


async def run_fake_harness(
    agent: dict[str, Any],
    cwd: Path,
    stdout_path: Path,
    stderr_path: Path,
    events: EventLogger,
    max_output_bytes: int,
) -> tuple[int, str, str, bool]:
    events.write("command", argv=["fake-harness", agent["id"]])
    response = {
        "summary": "Fake analysis completed.",
        "files_read": [],
        "files_changed": [],
        "tests_run": [],
        "risks": ["No real harness was used."],
        "recommendations": [],
    }
    fake_response = agent.get("fake_response")
    if isinstance(fake_response, dict):
        response.update(fake_response)

    if agent.get("fake_fail"):
        stdout = "Fake harness requested failure.\n"
        stderr = "fake_fail was true\n"
        stdout, stdout_truncated = _persist_fake_stream(
            stdout, stdout_path, max_output_bytes, events, "stdout"
        )
        stderr, stderr_truncated = _persist_fake_stream(
            stderr, stderr_path, max_output_bytes, events, "stderr"
        )
        return 1, stdout, stderr, stdout_truncated or stderr_truncated

    fake_patches: list[dict[str, Any]] = []
    if isinstance(agent.get("fake_patch"), dict):
        fake_patches.append(agent["fake_patch"])
    if isinstance(agent.get("fake_patches"), list):
        fake_patches.extend(item for item in agent["fake_patches"] if isinstance(item, dict))
    if agent["mode"] == "patch_only":
        for fake_patch in fake_patches:
            raw_path = str(fake_patch.get("path", "subagent_fake_patch.txt"))
            target, normalized_path = _safe_fake_patch_target(cwd, raw_path)
            content = str(fake_patch.get("content", "fake patch\n"))
            if fake_patch.get("append"):
                append_bytes_no_follow(target, content.encode("utf-8"))
            else:
                atomic_write_bytes(target, content.encode("utf-8"))
            response["files_changed"] = sorted(
                set([*response.get("files_changed", []), normalized_path])
            )

    stdout = (
        "Fake harness completed.\n"
        f"{JSON_START}\n"
        f"{json.dumps(response, indent=2, sort_keys=True)}\n"
        f"{JSON_END}\n"
    )
    stderr = ""
    stdout, stdout_truncated = _persist_fake_stream(
        stdout, stdout_path, max_output_bytes, events, "stdout"
    )
    stderr, stderr_truncated = _persist_fake_stream(
        stderr, stderr_path, max_output_bytes, events, "stderr"
    )
    await asyncio.sleep(0)
    return 0, stdout, stderr, stdout_truncated or stderr_truncated


def append_error(result: dict[str, Any], message: str) -> None:
    current = result.get("error")
    result["error"] = f"{current}; {message}" if current else message


async def run_agent(
    run_id: str,
    agent: dict[str, Any],
    run_dir: Path,
    repo_cwd: Path,
    config: dict[str, Any],
) -> dict[str, Any]:
    agent = dict(agent)
    agent["run_id"] = run_id
    invocation_root = repo_cwd.resolve()
    source_cwd = (invocation_root / agent["source_root"]).resolve()
    try:
        source_cwd.relative_to(invocation_root)
    except ValueError as exc:
        raise RunnerError(f"agent {agent['id']}: source_root escapes the invocation directory") from exc
    if not source_cwd.is_dir():
        raise RunnerError(f"agent {agent['id']}: source_root is not a directory: {source_cwd}")
    agent["resolved_source_root"] = str(source_cwd)
    repo_root = git_root(source_cwd)
    if repo_root is not None:
        agent["repo_subdir"] = source_cwd.relative_to(repo_root).as_posix() or "."
        agent["source_repo_root"] = str(repo_root)
    else:
        agent["repo_subdir"] = "."
        agent["source_repo_root"] = None
    agent_dir = safe_child(run_dir, agent["id"], "agent id")
    cleanup_agent_dir(agent_dir, repo_root)
    agent_dir.mkdir(parents=True, exist_ok=True)

    prompt_path = agent_dir / "prompt.txt"
    stdout_path = agent_dir / "stdout.log"
    stderr_path = agent_dir / "stderr.log"
    events_path = agent_dir / "events.jsonl"
    result_path = agent_dir / "result.json"
    runtime_path = agent_dir / "runtime.json"
    task_path = agent_dir / "task.json"
    patch_path = agent_dir / "patch.diff"

    prompt = generate_prompt(agent)
    write_json(task_path, agent)
    write_text(prompt_path, prompt)
    write_text(stdout_path, "")
    write_text(stderr_path, "")

    events = EventLogger(events_path, agent["id"])
    runtime = RuntimeTracker(runtime_path, events, agent["harness"])
    started_at = now_iso()
    started_time = time.monotonic()
    result = initial_result(run_id, agent, agent_dir, started_at)
    write_json(result_path, result)
    events.write("started", message="started")

    cancelled: asyncio.CancelledError | None = None
    before_snapshot: dict[str, tuple[str, int, int, str]] | None = None
    workspace = None
    try:
        if cancellation_requested(run_dir):
            raise UserCancelled("cancelled before workspace preparation")
        workspace = prepare_workspace(
            source_cwd,
            agent_dir,
            agent["effective_deny_paths"],
            agent["mode"],
            agent["max_workspace_files"],
            agent["max_workspace_bytes"],
        )
        result["baseline_commit"] = workspace.baseline_commit
        if workspace.baseline_manifest_sha256:
            result["baseline_manifest_path"] = rel_display(agent_dir / "baseline_manifest.json")
            result["baseline_manifest_sha256"] = workspace.baseline_manifest_sha256
        if agent["mode"] == "read_only":
            before_snapshot = snapshot_files(workspace.worktree or repo_cwd)

        env = build_env(agent, agent_dir, workspace.harness_cwd)
        if cancellation_requested(run_dir):
            raise UserCancelled("cancelled before harness launch")
        decode_error: str | None = None
        process_error_kind: str | None = None
        process_error: str | None = None
        if agent["harness"] == "fake":
            returncode, stdout_text, stderr_text, output_truncated = await run_fake_harness(
                agent,
                workspace.harness_cwd,
                stdout_path,
                stderr_path,
                events,
                agent["max_output_bytes"],
            )
            if output_truncated:
                process_error_kind = "output_limit"
                process_error = "stdout or stderr exceeded max_output_bytes"
            normalized_output = stdout_text
        else:
            invocation = build_harness_invocation(
                agent,
                prompt,
                prompt_path,
                workspace.harness_cwd,
                run_dir,
                agent_dir,
                config,
            )
            def process_started(pid: int, pgid: int, start_token: str | None) -> None:
                runtime.process_started(pid, pgid, start_token)
                if cancellation_requested(run_dir) and os.name == "posix":
                    with contextlib.suppress(ProcessLookupError):
                        os.killpg(pgid, signal.SIGTERM)

            outcome = await run_external_harness(
                invocation,
                workspace.harness_cwd,
                env,
                agent["timeout_sec"],
                agent["max_output_bytes"],
                stdout_path,
                stderr_path,
                events.write,
                idle_timeout_sec=agent["idle_timeout_sec"],
                process_started_writer=process_started,
                activity_writer=runtime.activity,
                stdout_line_writer=runtime.stream_line,
            )
            returncode = outcome.returncode
            stdout_text = outcome.stdout
            stderr_text = outcome.stderr
            process_error_kind = outcome.error_kind
            process_error = outcome.error
            normalized_output = stdout_text
            if process_error_kind not in {"output_limit", "timeout", "command_not_found"}:
                decoded = decode_harness_output(agent["harness"], stdout_text)
                normalized_output = decoded.text
                decode_error = decoded.error
                result["harness_metadata"] = decoded.metadata

        merge_result_fields(result, parse_subagent_result(normalized_output))
        if cancellation_requested(run_dir):
            result["status"] = "cancelled"
            result["error"] = "cancelled by broker request"
        elif process_error_kind == "timeout":
            result["status"] = "timeout"
            result["error"] = process_error or "timeout"
        elif process_error_kind == "output_limit":
            result["status"] = "output_limit"
            result["error"] = process_error or "output limit exceeded"
        elif process_error_kind == "idle_timeout":
            result["status"] = "idle_timeout"
            current_tool = runtime.state.get("current_tool")
            tool_name = current_tool.get("name") if isinstance(current_tool, dict) else None
            suffix = f"; current tool: {tool_name}" if tool_name else ""
            result["error"] = (process_error or "idle timeout") + suffix
        elif process_error_kind:
            result["status"] = "failed"
            result["error"] = process_error or process_error_kind
        elif returncode != 0:
            result["status"] = "failed"
            details = list(
                dict.fromkeys(
                    detail
                    for detail in (stderr_text.strip(), decode_error)
                    if isinstance(detail, str) and detail
                )
            )
            if not details and normalized_output.strip():
                details.append(normalized_output.strip()[:2000])
            details.append(f"harness exited with code {returncode}")
            result["error"] = "; ".join(details)
        elif decode_error:
            result["status"] = "failed"
            result["error"] = decode_error
        else:
            result["status"] = "completed"

        verify_workspace_identity(workspace)
        if agent["mode"] == "read_only":
            if workspace.worktree is not None:
                assert before_snapshot is not None
                changed = changed_snapshot_paths(
                    before_snapshot,
                    snapshot_files(workspace.worktree),
                )
                if changed:
                    result["files_changed"] = changed
                    result["status"] = "failed"
                    append_error(result, "read_only job modified files")
            elif before_snapshot is not None:
                changed = changed_snapshot_paths(before_snapshot, snapshot_files(source_cwd))
                if changed:
                    result["files_changed"] = changed
                    result["status"] = "failed"
                    append_error(result, "read_only job modified files")

        if agent["mode"] == "patch_only":
            assert workspace.worktree is not None
            assert workspace.baseline_commit is not None
            restore_trusted_git_metadata(workspace)
            changed = git_changed_paths(workspace.worktree, workspace.baseline_commit)
            result["files_changed"] = changed
            if result["status"] != "completed" or not changed:
                result["policy"] = None
            elif len(changed) > agent["max_files_changed"]:
                violation = (
                    f"Changed file count {len(changed)} exceeds max_files_changed "
                    f"{agent['max_files_changed']}"
                )
                result["policy"] = {
                    "status": "failed",
                    "changed_files": changed,
                    "violations": [violation],
                }
                result["status"] = "policy_failed"
                result["error"] = violation
                events.write("policy_check", status="failed", phase="file_count")
            else:
                path_policy = check_paths(
                    changed,
                    agent["allowed_paths"],
                    agent["effective_deny_paths"],
                )
                result["files_changed"] = path_policy["changed_files"]
                if path_policy["status"] != "passed":
                    result["policy"] = path_policy
                    events.write("policy_check", status="failed", phase="paths")
                    result["status"] = "policy_failed"
                    result["error"] = "; ".join(path_policy["violations"])

            if result["status"] == "completed" and changed:
                artifact = collect_git_diff(
                    workspace.worktree,
                    workspace.baseline_commit,
                    changed,
                )
                staged_policy = check_paths(
                    artifact.changed_paths,
                    agent["allowed_paths"],
                    agent["effective_deny_paths"],
                )
                current_paths = git_changed_paths(
                    workspace.worktree,
                    workspace.baseline_commit,
                )
                current_policy = check_paths(
                    current_paths,
                    agent["allowed_paths"],
                    agent["effective_deny_paths"],
                )
                if staged_policy["status"] != "passed" or current_policy["status"] != "passed":
                    policy = (
                        staged_policy if staged_policy["status"] != "passed" else current_policy
                    )
                    result["policy"] = policy
                    result["files_changed"] = policy["changed_files"]
                    events.write("policy_check", status="failed", phase="staged_paths")
                    result["status"] = "policy_failed"
                    result["error"] = "; ".join(policy["violations"])
                else:
                    policy = check_policy(
                        artifact.data,
                        agent["allowed_paths"],
                        agent["effective_deny_paths"],
                        allow_binary_changes=agent["allow_binary_changes"],
                        allow_deletes=agent["allow_deletes"],
                        changed_paths=artifact.changed_paths,
                        has_binary_changes=artifact.has_binary_changes,
                        has_deletes=artifact.has_deletes,
                    )
                    result["policy"] = policy
                    result["files_changed"] = policy["changed_files"]
                    if policy["status"] != "passed":
                        events.write("policy_check", status="failed", phase="patch")
                        result["status"] = "policy_failed"
                        result["error"] = (
                            "; ".join(policy["violations"]) or "patch policy failed"
                        )
                    else:
                        atomic_write_bytes(patch_path, artifact.data)
                        result["patch_path"] = rel_display(patch_path)
                        result["patch_sha256"] = hashlib.sha256(artifact.data).hexdigest()
                        events.write("patch_created", path=rel_display(patch_path))
                        events.write("policy_check", status="passed", phase="patch")

    except UserCancelled as exc:
        result["status"] = "cancelled"
        result["error"] = str(exc)
    except asyncio.CancelledError as exc:
        result["status"] = "cancelled"
        result["error"] = "cancelled"
        cancelled = exc
    except (RunnerError, RunnerRuntimeError, HarnessAdapterError) as exc:
        result["status"] = "failed"
        result["error"] = str(exc)
    except Exception as exc:  # noqa: BLE001 - result.json must be written on all failures.
        result["status"] = "failed"
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        result["ended_at"] = now_iso()
        result["duration_sec"] = round(time.monotonic() - started_time, 3)
        if result["status"] == "completed":
            events.write("completed", status=result["status"])
        elif result["status"] == "cancelled":
            events.write("cancelled", error=result["error"])
        else:
            events.write("failed", error=result.get("error") or result["status"])
        write_json(result_path, result)
        runtime.finish(result["status"])
    if cancelled is not None:
        raise cancelled
    return result


def aggregate_status(results: list[dict[str, Any]]) -> str:
    statuses = [result.get("status") for result in results]
    if statuses and all(status == "completed" for status in statuses):
        return "completed"
    if any(status in {"queued", "running"} for status in statuses):
        return "running"
    if any(status == "completed" for status in statuses):
        return "partial_success"
    if statuses and all(status == "cancelled" for status in statuses):
        return "cancelled"
    return "failed"


def write_run_result(
    run_dir: Path,
    run_id: str,
    results: list[dict[str, Any]],
    started_at: str,
    failure_policy: str = "collect_all",
    success_policy: str = "require_all",
) -> dict[str, Any]:
    status = aggregate_status(results)
    payload = {
        "run_id": run_id,
        "status": status,
        "failure_policy": failure_policy,
        "success_policy": success_policy,
        "success_policy_satisfied": status == "completed"
        or (status == "partial_success" and success_policy == "require_any"),
        "started_at": started_at,
        "ended_at": now_iso(),
        "agents": results,
    }
    write_json(run_dir / "result.json", payload)
    write_summary(run_dir, payload)
    return payload


def queued_result(run_id: str, agent: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "agent_id": agent["id"],
        "status": "queued",
        "mode": agent["mode"],
        "harness": agent["harness"],
        "model": agent.get("model"),
        "approval_policy": agent["approval_policy"],
        "files_changed": [],
    }


def write_running_run_result(run_dir: Path, packet: dict[str, Any], started_at: str) -> None:
    write_json(
        run_dir / "result.json",
        {
            "run_id": packet["run_id"],
            "status": "running",
            "failure_policy": packet["failure_policy"],
            "success_policy": packet["success_policy"],
            "success_policy_satisfied": False,
            "started_at": started_at,
            "ended_at": None,
            "agents": [queued_result(packet["run_id"], agent) for agent in packet["agents"]],
        },
    )


def write_cancelled_placeholder(
    run_dir: Path,
    run_id: str,
    agent: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    agent_dir = safe_child(run_dir, agent["id"], "agent id")
    agent_dir.mkdir(parents=True, exist_ok=True)
    started_at = now_iso()
    result = initial_result(run_id, agent, agent_dir, started_at)
    result.update(
        {
            "status": "cancelled",
            "error": reason,
            "ended_at": started_at,
        }
    )
    write_json(agent_dir / "result.json", result)
    return result


def format_list(items: list[Any]) -> str:
    if not items:
        return "- none"
    return "\n".join(f"- {item}" for item in items)


def write_summary(run_dir: Path, aggregate: dict[str, Any]) -> None:
    lines = [
        f"# Subagent Run Summary: {aggregate['run_id']}",
        "",
        f"Status: {aggregate['status']}",
        f"Started: {aggregate.get('started_at')}",
        f"Ended: {aggregate.get('ended_at')}",
        f"Failure policy: {aggregate.get('failure_policy', 'collect_all')}",
        f"Success policy: {aggregate.get('success_policy', 'require_all')}",
        "",
        "## Agents",
        "",
    ]
    for result in aggregate.get("agents", []):
        lines.extend(
            [
                f"### {result.get('agent_id')}",
                "",
                f"Status: {result.get('status')}",
                f"Harness: {result.get('harness')}",
                f"Mode: {result.get('mode')}",
                f"Approval: {result.get('approval_policy')}",
                f"Model: {result.get('model') or 'none'}",
                f"Baseline: {result.get('baseline_commit') or 'none'}",
                "",
                "Summary:",
                str(result.get("summary") or "No summary returned."),
                "",
                "Files changed:",
                format_list(result.get("files_changed") or []),
                "",
                "Patch:",
                f"- {result['patch_path']}" if result.get("patch_path") else "- none",
            ]
        )
        policy = result.get("policy")
        if isinstance(policy, dict):
            lines.extend(["", "Policy:", f"- {policy.get('status', 'unknown')}"])
        lines.extend(
            [
                "",
                "Risks:",
                format_list(result.get("risks") or []),
                "",
                "Recommendations:",
                format_list(result.get("recommendations") or []),
                "",
                "Logs:",
                f"- {result.get('log_path')}",
                f"- {rel_display(run_dir / str(result.get('agent_id')) / 'stdout.log')}",
                f"- {rel_display(run_dir / str(result.get('agent_id')) / 'stderr.log')}",
                "",
            ]
        )
        if result.get("error"):
            lines.extend(["Error:", str(result["error"]), ""])
    write_text(run_dir / "summary.md", "\n".join(lines).rstrip() + "\n")


async def run_packet(args: argparse.Namespace) -> int:
    if not args.wait:
        print("Non-wait mode is not implemented in the MVP. Rerun with --wait.", file=sys.stderr)
        return 2

    packet = validate_and_normalize(load_task_packet(Path(args.task_packet)))
    config = load_config()
    run_id = packet["run_id"]
    output_root = Path(".subagents")
    if output_root.is_symlink():
        raise RunnerError(".subagents output root must not be a symlink")
    run_dir = safe_child(output_root, run_id, "run_id")
    run_dir.mkdir(parents=True, exist_ok=True)
    write_json(run_dir / "tasks.normalized.json", packet)

    max_concurrency = args.max_concurrency or min(4, len(packet["agents"]))
    max_concurrency = max(1, max_concurrency)
    semaphore = asyncio.Semaphore(max_concurrency)
    started_at = now_iso()
    write_running_run_result(run_dir, packet, started_at)

    async def limited(agent: dict[str, Any]) -> dict[str, Any]:
        async with semaphore:
            result = await run_agent(run_id, agent, run_dir, Path.cwd(), config)
            if packet["failure_policy"] == "fail_fast" and result.get("status") != "completed":
                write_json(
                    cancel_marker(run_dir),
                    {"requested_at": now_iso(), "reason": "failure_policy fail_fast"},
                )
            return result

    task_agents = {
        asyncio.create_task(limited(agent)): agent for agent in packet["agents"]
    }
    tasks = list(task_agents)
    try:
        if packet["failure_policy"] == "collect_all":
            results = await asyncio.gather(*tasks)
        else:
            pending = set(tasks)
            results = []
            while pending:
                done, pending = await asyncio.wait(
                    pending, return_when=asyncio.FIRST_COMPLETED
                )
                failed = False
                for task in done:
                    try:
                        result = task.result()
                    except asyncio.CancelledError:
                        continue
                    results.append(result)
                    failed = failed or result.get("status") != "completed"
                if failed and pending:
                    write_json(
                        cancel_marker(run_dir),
                        {"requested_at": now_iso(), "reason": "failure_policy fail_fast"},
                    )
                    for task in pending:
                        task.cancel()
                    await asyncio.gather(*pending, return_exceptions=True)
                    break
    except asyncio.CancelledError:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        partial_results = load_agent_results(run_dir)
        if partial_results:
            write_run_result(
                run_dir,
                run_id,
                partial_results,
                started_at,
                packet["failure_policy"],
                packet["success_policy"],
            )
        raise
    loaded_results = {result["agent_id"]: result for result in load_agent_results(run_dir)}
    for agent in packet["agents"]:
        if agent["id"] not in loaded_results:
            loaded_results[agent["id"]] = write_cancelled_placeholder(
                run_dir,
                run_id,
                agent,
                "cancelled before agent launch",
            )
    results = [loaded_results[agent["id"]] for agent in packet["agents"]]
    aggregate = write_run_result(
        run_dir,
        run_id,
        results,
        started_at,
        packet["failure_policy"],
        packet["success_policy"],
    )
    print(rel_display(run_dir / "summary.md"))
    return 0 if aggregate["success_policy_satisfied"] else 1


def load_agent_results(run_dir: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for result_path in sorted(run_dir.glob("*/result.json")):
        with result_path.open("r", encoding="utf-8") as handle:
            loaded = json.load(handle)
        if isinstance(loaded, dict):
            results.append(loaded)
    return results


def load_json_object(path: Path) -> dict[str, Any] | None:
    if not path.is_file() or path.is_symlink():
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            loaded = json.load(handle)
    except (OSError, ValueError):
        return None
    return loaded if isinstance(loaded, dict) else None


def current_changed_count(agent_dir: Path) -> int | None:
    manifest = load_json_object(agent_dir / "baseline_manifest.json")
    worktree = agent_dir / "worktree"
    if not manifest or not worktree.is_dir():
        return None
    baseline = manifest.get("files")
    if not isinstance(baseline, dict):
        return None
    current = {
        path: {"mode": f"{entry[1]:o}", "sha256": entry[3]}
        for path, entry in snapshot_files(worktree).items()
    }
    return sum(
        1
        for path in set(baseline) | set(current)
        if baseline.get(path) != current.get(path)
    )


def elapsed_seconds(result: dict[str, Any]) -> float | None:
    if isinstance(result.get("duration_sec"), (int, float)) and result.get("status") not in {
        "queued",
        "running",
    }:
        return float(result["duration_sec"])
    started_at = result.get("started_at")
    if not isinstance(started_at, str):
        return None
    try:
        started = datetime.fromisoformat(started_at)
    except ValueError:
        return None
    return max(0.0, (datetime.now(timezone.utc) - started).total_seconds())


def command_status(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir)
    run_id = run_dir.name
    aggregate_path = run_dir / "result.json"
    aggregate: dict[str, Any] | None = None
    if aggregate_path.exists():
        with aggregate_path.open("r", encoding="utf-8") as handle:
            loaded = json.load(handle)
        if isinstance(loaded, dict):
            aggregate = loaded
            run_id = str(aggregate.get("run_id") or run_id)

    live_results = {result["agent_id"]: result for result in load_agent_results(run_dir)}
    aggregate_results = aggregate.get("agents", []) if aggregate else []
    ordered_ids = [str(result.get("agent_id")) for result in aggregate_results]
    ordered_ids.extend(agent_id for agent_id in live_results if agent_id not in ordered_ids)
    results = []
    for agent_id in ordered_ids:
        fallback = next(
            (item for item in aggregate_results if item.get("agent_id") == agent_id),
            {"agent_id": agent_id, "status": "queued"},
        )
        results.append(live_results.get(agent_id, fallback))
    status = aggregate_status(results) if results else "unknown"
    print(f"Run: {run_id}")
    print(f"Status: {status}")
    print()
    print("Agents:")
    if not results:
        print("- none")
    for result in results:
        agent_dir = run_dir / str(result.get("agent_id"))
        runtime = load_json_object(agent_dir / "runtime.json")
        details = [str(result.get("status"))]
        elapsed = elapsed_seconds(result)
        if elapsed is not None:
            details.append(f"duration={elapsed:.1f}s")
        if runtime:
            if runtime.get("status") == "running" and runtime.get("pid"):
                details.append(f"pid={runtime['pid']}")
            if runtime.get("status") == "running" and runtime.get("pgid"):
                details.append(f"pgid={runtime['pgid']}")
            if runtime.get("last_activity_at"):
                details.append(f"last_activity={runtime['last_activity_at']}")
            tool = runtime.get("current_tool")
            if isinstance(tool, dict) and tool.get("name"):
                details.append(f"tool={tool['name']}")
        live_changed = current_changed_count(agent_dir)
        changed_count = live_changed if live_changed is not None else len(result.get("files_changed") or [])
        details.append(f"files_changed={changed_count}")
        print(f"- {result.get('agent_id')}: {', '.join(details)}")
    return 0


def command_collect(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir)
    if not run_dir.exists():
        print(f"Run directory not found: {run_dir}", file=sys.stderr)
        return 2
    results = load_agent_results(run_dir)
    if not results:
        print(f"No agent result.json files found under {run_dir}", file=sys.stderr)
        return 2
    started_values = [str(result.get("started_at")) for result in results if result.get("started_at")]
    started_at = min(started_values) if started_values else now_iso()
    previous = load_json_object(run_dir / "result.json") or {}
    aggregate = write_run_result(
        run_dir,
        run_dir.name,
        results,
        started_at,
        str(previous.get("failure_policy") or "collect_all"),
        str(previous.get("success_policy") or "require_all"),
    )
    print(rel_display(run_dir / "summary.md"))
    return 0 if aggregate["success_policy_satisfied"] else 1


def command_cancel(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir)
    if not run_dir.is_dir():
        print(f"Run directory not found: {run_dir}", file=sys.stderr)
        return 2
    if args.grace_sec < 0:
        print("--grace-sec must be non-negative", file=sys.stderr)
        return 2
    write_json(
        cancel_marker(run_dir),
        {"requested_at": now_iso(), "reason": "user request"},
    )
    groups: set[int] = set()
    signalled = 0
    refused = 0
    for runtime_path in sorted(run_dir.glob("*/runtime.json")):
        runtime = load_json_object(runtime_path)
        if not runtime or runtime.get("status") != "running":
            continue
        pid = runtime.get("pid")
        pgid = runtime.get("pgid")
        token = runtime.get("process_start_token")
        if type(pid) is not int or type(pgid) is not int:
            continue
        if os.name != "posix" or not token or process_start_token(pid) != token:
            refused += 1
            print(f"Refused stale or unverifiable process identity: pid={pid}", file=sys.stderr)
            continue
        try:
            if os.getpgid(pid) != pgid:
                refused += 1
                continue
            os.killpg(pgid, signal.SIGTERM)
            groups.add(pgid)
            signalled += 1
        except (ProcessLookupError, PermissionError):
            refused += 1

    deadline = time.monotonic() + args.grace_sec
    while groups and time.monotonic() < deadline:
        groups = {pgid for pgid in groups if process_group_exists(pgid)}
        if groups:
            time.sleep(0.05)
    for pgid in groups:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(pgid, signal.SIGKILL)
    print(f"Cancellation requested: signalled={signalled}, refused={refused}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run subagent broker jobs")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="run a task packet")
    run_parser.add_argument("task_packet")
    run_parser.add_argument("--wait", action="store_true")
    run_parser.add_argument("--max-concurrency", type=int, default=None)

    status_parser = subparsers.add_parser("status", help="show run status")
    status_parser.add_argument("run_dir")

    collect_parser = subparsers.add_parser("collect", help="regenerate aggregate files")
    collect_parser.add_argument("run_dir")

    cancel_parser = subparsers.add_parser("cancel", help="cancel a run")
    cancel_parser.add_argument("run_dir")
    cancel_parser.add_argument("--grace-sec", type=float, default=2.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if args.command == "run":
            return asyncio.run(run_packet(args))
        if args.command == "status":
            return command_status(args)
        if args.command == "collect":
            return command_collect(args)
        if args.command == "cancel":
            return command_cancel(args)
    except RunnerError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("cancelled", file=sys.stderr)
        return 130
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
