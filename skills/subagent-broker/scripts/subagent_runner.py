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
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
POLICY_SCRIPT = SCRIPT_DIR / "policy_check.py"
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
SUPPORTED_MODES = {"read_only", "patch_only"}
UNSUPPORTED_MODES = {"direct_write", "shared_workspace", "network_sandbox", "daemon"}
SUPPORTED_HARNESSES = {"fake", "opencode", "claude-code", "codex-cli"}
SUPPORTED_HOME_POLICIES = {"isolated", "host"}
DEFAULT_DENY_PATHS = [".env*", ".git/**", ".subagents/**", "secrets/**"]
SECRET_ENV_RE = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|COOKIE|SESSION)", re.I)
JSON_START = "SUBAGENT_RESULT_JSON_START"
JSON_END = "SUBAGENT_RESULT_JSON_END"


class RunnerError(Exception):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def rel_display(path: Path) -> str:
    with contextlib.suppress(ValueError):
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    return path.as_posix()


def ensure_safe_id(value: str, field: str) -> None:
    if not value or not SAFE_ID_RE.fullmatch(value):
        raise RunnerError(f"{field} must contain only letters, digits, underscore, dot, or hyphen: {value!r}")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_task_packet(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
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
    if not isinstance(loaded, dict):
        raise RunnerError("Task packet must be a JSON object")
    return loaded


def normalize_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    return bool(value)


def normalize_list(value: Any, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise RunnerError(f"{field} must be a list of strings")
    return list(value)


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
        if mode in UNSUPPORTED_MODES:
            raise RunnerError(f"agent {agent_id}: unsupported mode for MVP: {mode}")
        if mode not in SUPPORTED_MODES:
            raise RunnerError(f"agent {agent_id}: mode must be one of {sorted(SUPPORTED_MODES)}")

        harness = agent.get("harness", "fake")
        if harness not in SUPPORTED_HARNESSES:
            raise RunnerError(f"agent {agent_id}: harness must be one of {sorted(SUPPORTED_HARNESSES)}")

        timeout_sec = int(agent.get("timeout_sec", 1800))
        if timeout_sec <= 0:
            raise RunnerError(f"agent {agent_id}: timeout_sec must be positive")

        max_output_bytes = int(agent.get("max_output_bytes", 2_000_000))
        if max_output_bytes <= 0:
            raise RunnerError(f"agent {agent_id}: max_output_bytes must be positive")

        allowed_paths = normalize_list(agent.get("allowed_paths", []), "allowed_paths")
        deny_paths = normalize_list(agent.get("deny_paths", []), "deny_paths")
        return_fields = normalize_list(agent.get("return", []), "return")
        inherit_env = normalize_bool(agent.get("inherit_env"), True)

        home_policy = agent.get("home_policy", "isolated")
        if not isinstance(home_policy, str) or home_policy not in SUPPORTED_HOME_POLICIES:
            raise RunnerError(
                f"agent {agent_id}: home_policy must be one of {sorted(SUPPORTED_HOME_POLICIES)}"
            )
        if home_policy == "host" and not inherit_env:
            raise RunnerError(f"agent {agent_id}: home_policy 'host' requires inherit_env true")

        normalized = dict(agent)
        normalized.update(
            {
                "id": agent_id,
                "goal": goal,
                "mode": mode,
                "harness": harness,
                "timeout_sec": timeout_sec,
                "max_output_bytes": max_output_bytes,
                "allowed_paths": allowed_paths,
                "deny_paths": deny_paths,
                "effective_deny_paths": sorted(set([*DEFAULT_DENY_PATHS, *deny_paths])),
                "return": return_fields,
                "allow_binary_changes": normalize_bool(agent.get("allow_binary_changes"), False),
                "allow_deletes": normalize_bool(agent.get("allow_deletes"), False),
                "inherit_env": inherit_env,
                "home_policy": home_policy,
                "dangerously_skip_permissions": normalize_bool(
                    agent.get("dangerously_skip_permissions"), False
                ),
                "session_persistence": normalize_bool(agent.get("session_persistence"), False),
            }
        )
        agents.append(normalized)

    return {"run_id": run_id, "defaults": defaults, "agents": agents}


def load_config() -> dict[str, Any]:
    config_path = SKILL_DIR / "config.json"
    if not config_path.exists():
        return {}
    with config_path.open("r", encoding="utf-8") as handle:
        loaded = json.load(handle)
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
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")


def generate_prompt(agent: dict[str, Any]) -> str:
    allowed = "\n".join(f"- {path}" for path in agent["allowed_paths"]) or "- none"
    denied = "\n".join(f"- {path}" for path in agent["effective_deny_paths"]) or "- none"
    returns = "\n".join(f"- {field}" for field in agent["return"]) or "- summary"
    return f"""You are a bounded subagent launched by a parent Codex agent.

Agent ID: {agent['id']}
Mode: {agent['mode']}
Goal:
{agent['goal']}

Allowed paths:
{allowed}

Denied paths:
{denied}

Expected return fields:
{returns}

Rules:
- Work only on the assigned goal.
- Do not inspect files outside allowed paths unless necessary for imports or references.
- Never read secrets, credentials, .env files, .git internals, SSH keys, or token caches.
- Do not communicate with other subagents.
- Do not rely on prior conversation context.
- Return concise results.
- If mode is read_only, do not modify files.
- If mode is patch_only, edit only files under allowed paths.
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
    status: str = "running",
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "agent_id": agent["id"],
        "status": status,
        "mode": agent["mode"],
        "harness": agent["harness"],
        "model": agent.get("model"),
        "summary": "",
        "files_read": [],
        "files_changed": [],
        "patch_path": None,
        "tests_run": [],
        "risks": [],
        "recommendations": [],
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


def truncate_bytes(data: bytes, limit: int) -> bytes:
    if len(data) <= limit:
        return data
    suffix = b"\n[output truncated]\n"
    return data[: max(0, limit - len(suffix))] + suffix


def run_sync(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            cwd=str(cwd),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except FileNotFoundError:
        return subprocess.CompletedProcess(args, 127, "", f"Command not found: {args[0]}")


def git_root(cwd: Path) -> Path | None:
    process = run_sync(["git", "rev-parse", "--show-toplevel"], cwd)
    if process.returncode != 0:
        return None
    return Path(process.stdout.strip()).resolve()


def cleanup_agent_dir(agent_dir: Path, repo_root: Path | None) -> None:
    worktree = agent_dir / "worktree"
    if worktree.exists() and repo_root is not None:
        run_sync(["git", "worktree", "remove", "--force", str(worktree)], repo_root)
    if agent_dir.exists():
        shutil.rmtree(agent_dir)


def create_worktree(repo_root: Path, worktree: Path) -> None:
    worktree.parent.mkdir(parents=True, exist_ok=True)
    process = run_sync(["git", "worktree", "add", "--detach", str(worktree), "HEAD"], repo_root)
    if process.returncode != 0:
        raise RunnerError(f"git worktree add failed: {process.stderr.strip() or process.stdout.strip()}")


def git_status_paths(cwd: Path) -> list[str]:
    process = run_sync(["git", "-c", "core.quotePath=false", "status", "--porcelain"], cwd)
    if process.returncode != 0:
        return []
    paths: list[str] = []
    for line in process.stdout.splitlines():
        text = line[3:] if len(line) >= 3 else line
        if " -> " in text:
            paths.extend(text.split(" -> ", 1))
        elif text:
            paths.append(text)
    return sorted(set(paths))


def collect_git_diff(cwd: Path, patch_path: Path) -> str:
    # Include untracked files as additions without staging content for commit.
    run_sync(["git", "add", "-N", "--", "."], cwd)
    process = run_sync(["git", "-c", "core.quotePath=false", "diff", "--binary", "HEAD", "--"], cwd)
    diff_text = process.stdout if process.returncode == 0 else ""
    write_text(patch_path, diff_text)
    return diff_text


def snapshot_files(root: Path) -> dict[str, tuple[int, str]]:
    snapshot: dict[str, tuple[int, str]] = {}
    skip_dirs = {".git", ".subagents"}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in skip_dirs]
        current = Path(dirpath)
        for filename in filenames:
            path = current / filename
            try:
                rel = path.relative_to(root).as_posix()
                data = path.read_bytes()
            except OSError:
                continue
            snapshot[rel] = (len(data), hashlib.sha256(data).hexdigest())
    return snapshot


def changed_snapshot_paths(before: dict[str, tuple[int, str]], after: dict[str, tuple[int, str]]) -> list[str]:
    changed = []
    for path in sorted(set(before) | set(after)):
        if before.get(path) != after.get(path):
            changed.append(path)
    return changed


def build_env(agent: dict[str, Any], agent_dir: Path, cwd: Path) -> dict[str, str]:
    env = dict(os.environ) if agent.get("inherit_env", True) else {}
    if agent["harness"] == "fake" or not agent.get("inherit_env", True):
        env = {key: value for key, value in env.items() if not SECRET_ENV_RE.search(key)}

    absolute_agent_dir = agent_dir.resolve()
    absolute_cwd = cwd.resolve()
    tmp = absolute_agent_dir / "tmp"
    cache = absolute_agent_dir / "cache"
    home = absolute_agent_dir / "home"
    if agent.get("home_policy", "isolated") == "host":
        host_home = env.get("HOME")
        if not host_home:
            raise RunnerError("home_policy 'host' requires HOME in the inherited environment")
        home_value = host_home
        directories = (tmp, cache)
    else:
        home_value = str(home)
        directories = (home, tmp, cache)
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
    return env


def format_custom_argv(template: list[Any], values: dict[str, str]) -> list[str]:
    argv: list[str] = []
    i = 0
    while i < len(template):
        token = str(template[i])
        if token.startswith("-") and i + 1 < len(template):
            next_token = str(template[i + 1])
            if next_token.startswith("{") and next_token.endswith("}") and values.get(next_token[1:-1], "") == "":
                i += 2
                continue
        for key, value in values.items():
            token = token.replace("{" + key + "}", value)
        if token != "":
            argv.append(token)
        i += 1
    return argv


def build_harness_argv(
    agent: dict[str, Any],
    prompt: str,
    prompt_file: Path,
    cwd: Path,
    run_dir: Path,
    agent_dir: Path,
    config: dict[str, Any],
) -> list[str]:
    harness = agent["harness"]
    values = {
        "model": str(agent.get("model") or ""),
        "agent": str(agent.get("agent") or ""),
        "goal": str(agent["goal"]),
        "prompt": prompt,
        "prompt_file": str(prompt_file.resolve()),
        "cwd": str(cwd.resolve()),
        "run_dir": str(run_dir.resolve()),
        "agent_dir": str(agent_dir.resolve()),
    }
    harnesses = config.get("harnesses", {})
    if isinstance(harnesses, dict):
        entry = harnesses.get(harness)
        if isinstance(entry, dict) and isinstance(entry.get("argv"), list):
            return format_custom_argv(entry["argv"], values)

    if harness == "opencode":
        argv = ["opencode", "run"]
        if values["model"]:
            argv.extend(["--model", values["model"]])
        if values["agent"]:
            argv.extend(["--agent", values["agent"]])
        argv.append(prompt)
        return argv
    if harness == "claude-code":
        argv = ["claude"]
        if values["model"]:
            argv.extend(["--model", values["model"]])
        if values["agent"]:
            argv.extend(["--agent", values["agent"]])
        if agent.get("dangerously_skip_permissions"):
            argv.append("--dangerously-skip-permissions")
        if not agent.get("session_persistence"):
            argv.append("--no-session-persistence")
        argv.extend(["-p", prompt])
        return argv
    if harness == "codex-cli":
        argv = ["codex", "exec", "--json"]
        if values["model"]:
            argv.extend(["--model", values["model"]])
        argv.append(prompt)
        return argv
    raise RunnerError(f"No adapter for harness: {harness}")


async def run_external_harness(
    argv: list[str],
    cwd: Path,
    env: dict[str, str],
    timeout_sec: int,
    max_output_bytes: int,
    stdout_path: Path,
    stderr_path: Path,
    events: EventLogger,
) -> tuple[int | None, bytes, bytes, str | None]:
    events.write("command", argv=argv)
    try:
        process = await asyncio.create_subprocess_exec(
            *argv,
            cwd=str(cwd),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        command = argv[0] if argv else "<empty>"
        write_text(stdout_path, "")
        write_text(stderr_path, "")
        events.write("stdout", bytes=0)
        events.write("stderr", bytes=0)
        return None, b"", b"", (
            f"Harness command not found: {command}. "
            "Install it or configure .agents/skills/subagent-broker/config.json."
        )

    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout_sec)
    except asyncio.TimeoutError:
        process.kill()
        stdout, stderr = await process.communicate()
        write_text(stdout_path, truncate_bytes(stdout, max_output_bytes).decode("utf-8", errors="replace"))
        write_text(stderr_path, truncate_bytes(stderr, max_output_bytes).decode("utf-8", errors="replace"))
        events.write("stdout", bytes=len(stdout))
        events.write("stderr", bytes=len(stderr))
        return None, stdout, stderr, "timeout"

    write_text(stdout_path, truncate_bytes(stdout, max_output_bytes).decode("utf-8", errors="replace"))
    write_text(stderr_path, truncate_bytes(stderr, max_output_bytes).decode("utf-8", errors="replace"))
    events.write("stdout", bytes=len(stdout))
    events.write("stderr", bytes=len(stderr))
    return process.returncode, stdout, stderr, None


async def run_fake_harness(
    agent: dict[str, Any],
    cwd: Path,
    stdout_path: Path,
    stderr_path: Path,
    events: EventLogger,
) -> tuple[int, str, str]:
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
        write_text(stdout_path, stdout)
        write_text(stderr_path, stderr)
        events.write("stdout", bytes=len(stdout.encode("utf-8")))
        events.write("stderr", bytes=len(stderr.encode("utf-8")))
        return 1, stdout, stderr

    fake_patch = agent.get("fake_patch")
    if agent["mode"] == "patch_only" and isinstance(fake_patch, dict):
        raw_path = str(fake_patch.get("path", "subagent_fake_patch.txt"))
        target = cwd / raw_path
        target.parent.mkdir(parents=True, exist_ok=True)
        content = str(fake_patch.get("content", "fake patch\n"))
        if fake_patch.get("append"):
            with target.open("a", encoding="utf-8") as handle:
                handle.write(content)
        else:
            target.write_text(content, encoding="utf-8")
        response["files_changed"] = sorted(set([*response.get("files_changed", []), raw_path]))

    stdout = (
        "Fake harness completed.\n"
        f"{JSON_START}\n"
        f"{json.dumps(response, indent=2, sort_keys=True)}\n"
        f"{JSON_END}\n"
    )
    stderr = ""
    write_text(stdout_path, stdout)
    write_text(stderr_path, stderr)
    events.write("stdout", bytes=len(stdout.encode("utf-8")))
    events.write("stderr", bytes=0)
    await asyncio.sleep(0)
    return 0, stdout, stderr


async def run_policy_check(agent: dict[str, Any], patch_path: Path, events: EventLogger) -> dict[str, Any]:
    argv = [sys.executable, str(POLICY_SCRIPT), "--patch", str(patch_path)]
    for pattern in agent["allowed_paths"]:
        argv.extend(["--allowed", pattern])
    # DEFAULT_DENY_PATHS are included inside policy_check.py; pass only task deny paths.
    for pattern in agent["deny_paths"]:
        argv.extend(["--deny", pattern])
    if agent.get("allow_binary_changes"):
        argv.append("--allow-binary-changes")
    if agent.get("allow_deletes"):
        argv.append("--allow-deletes")

    process = await asyncio.create_subprocess_exec(
        *argv,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    try:
        result = json.loads(stdout.decode("utf-8"))
    except json.JSONDecodeError:
        result = {
            "status": "failed",
            "changed_files": [],
            "violations": [stderr.decode("utf-8", errors="replace") or "policy_check.py did not return JSON"],
        }
    events.write("policy_check", status=result.get("status", "failed"))
    return result


async def run_agent(
    run_id: str,
    agent: dict[str, Any],
    run_dir: Path,
    repo_cwd: Path,
    config: dict[str, Any],
) -> dict[str, Any]:
    agent = dict(agent)
    agent["run_id"] = run_id
    repo_root = git_root(repo_cwd)
    agent_dir = run_dir / agent["id"]
    cleanup_agent_dir(agent_dir, repo_root)
    agent_dir.mkdir(parents=True, exist_ok=True)

    prompt_path = agent_dir / "prompt.txt"
    stdout_path = agent_dir / "stdout.log"
    stderr_path = agent_dir / "stderr.log"
    events_path = agent_dir / "events.jsonl"
    result_path = agent_dir / "result.json"
    task_path = agent_dir / "task.json"
    patch_path = agent_dir / "patch.diff"
    worktree = agent_dir / "worktree"

    prompt = generate_prompt(agent)
    write_json(task_path, agent)
    write_text(prompt_path, prompt)
    write_text(stdout_path, "")
    write_text(stderr_path, "")

    events = EventLogger(events_path, agent["id"])
    started_at = now_iso()
    started_time = time.monotonic()
    result = initial_result(run_id, agent, agent_dir, started_at)
    write_json(result_path, result)
    events.write("started", message="started")

    before_snapshot: dict[str, tuple[int, str]] | None = None
    harness_cwd = repo_cwd
    try:
        if agent["mode"] == "patch_only":
            if repo_root is None:
                raise RunnerError("patch_only requires a Git repository")
            create_worktree(repo_root, worktree)
            harness_cwd = worktree
        elif repo_root is not None:
            create_worktree(repo_root, worktree)
            harness_cwd = worktree
        else:
            before_snapshot = snapshot_files(repo_cwd)

        env = build_env(agent, agent_dir, harness_cwd)
        if agent["harness"] == "fake":
            returncode, stdout_text, stderr_text = await run_fake_harness(
                agent, harness_cwd, stdout_path, stderr_path, events
            )
            timeout_error = None
        else:
            argv = build_harness_argv(agent, prompt, prompt_path, harness_cwd, run_dir, agent_dir, config)
            returncode, stdout_bytes, stderr_bytes, timeout_error = await run_external_harness(
                argv,
                harness_cwd,
                env,
                agent["timeout_sec"],
                agent["max_output_bytes"],
                stdout_path,
                stderr_path,
                events,
            )
            stdout_text = stdout_bytes.decode("utf-8", errors="replace")
            stderr_text = stderr_bytes.decode("utf-8", errors="replace")

        parsed = parse_subagent_result(stdout_text)
        merge_result_fields(result, parsed)

        if timeout_error == "timeout":
            result["status"] = "timeout"
            result["error"] = "timeout"
        elif timeout_error:
            result["status"] = "failed"
            result["error"] = timeout_error
        elif returncode != 0:
            result["status"] = "failed"
            result["error"] = stderr_text.strip() or stdout_text.strip() or f"harness exited with code {returncode}"
        else:
            result["status"] = "completed"

        if agent["mode"] == "read_only":
            if repo_root is not None and worktree.exists():
                changed = git_status_paths(worktree)
                if changed:
                    collect_git_diff(worktree, patch_path)
                    result["files_changed"] = changed
                    result["patch_path"] = rel_display(patch_path)
                    result["status"] = "failed"
                    result["error"] = "read_only job modified files"
            elif before_snapshot is not None:
                changed = changed_snapshot_paths(before_snapshot, snapshot_files(repo_cwd))
                if changed:
                    result["files_changed"] = changed
                    result["status"] = "failed"
                    result["error"] = "read_only job modified files"

        if agent["mode"] == "patch_only":
            collect_git_diff(worktree, patch_path)
            result["patch_path"] = rel_display(patch_path)
            events.write("patch_created", path=rel_display(patch_path))
            policy = await run_policy_check(agent, patch_path, events)
            result["policy"] = policy
            if isinstance(policy, dict) and isinstance(policy.get("changed_files"), list):
                result["files_changed"] = policy["changed_files"]
            if result["status"] == "completed" and policy.get("status") != "passed":
                result["status"] = "policy_failed"
                result["error"] = "; ".join(policy.get("violations", [])) or "patch policy failed"

    except RunnerError as exc:
        result["status"] = "failed"
        result["error"] = str(exc)
    except Exception as exc:  # noqa: BLE001 - result.json must be written on all failures.
        result["status"] = "failed"
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        ended_at = now_iso()
        result["ended_at"] = ended_at
        result["duration_sec"] = round(time.monotonic() - started_time, 3)
        if result["status"] in {"completed"}:
            events.write("completed", status=result["status"])
        else:
            events.write("failed", error=result.get("error") or result["status"])
        write_json(result_path, result)
    return result


def aggregate_status(results: list[dict[str, Any]]) -> str:
    if all(result.get("status") == "completed" for result in results):
        return "completed"
    if any(result.get("status") == "running" for result in results):
        return "running"
    return "failed"


def write_run_result(run_dir: Path, run_id: str, results: list[dict[str, Any]], started_at: str) -> dict[str, Any]:
    ended_at = now_iso()
    payload = {
        "run_id": run_id,
        "status": aggregate_status(results),
        "started_at": started_at,
        "ended_at": ended_at,
        "agents": results,
    }
    write_json(run_dir / "result.json", payload)
    write_summary(run_dir, payload)
    return payload


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
                f"Model: {result.get('model') or 'none'}",
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
    run_dir = Path(".subagents") / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    write_json(run_dir / "tasks.normalized.json", packet)

    max_concurrency = args.max_concurrency or min(4, len(packet["agents"]))
    max_concurrency = max(1, max_concurrency)
    semaphore = asyncio.Semaphore(max_concurrency)
    started_at = now_iso()

    async def limited(agent: dict[str, Any]) -> dict[str, Any]:
        async with semaphore:
            return await run_agent(run_id, agent, run_dir, Path.cwd(), config)

    results = await asyncio.gather(*(limited(agent) for agent in packet["agents"]))
    aggregate = write_run_result(run_dir, run_id, results, started_at)
    print(rel_display(run_dir / "summary.md"))
    return 0 if aggregate["status"] == "completed" else 1


def load_agent_results(run_dir: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for result_path in sorted(run_dir.glob("*/result.json")):
        with result_path.open("r", encoding="utf-8") as handle:
            loaded = json.load(handle)
        if isinstance(loaded, dict):
            results.append(loaded)
    return results


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

    results = load_agent_results(run_dir)
    status = aggregate.get("status") if aggregate else aggregate_status(results) if results else "unknown"
    print(f"Run: {run_id}")
    print(f"Status: {status}")
    print()
    print("Agents:")
    if not results:
        print("- none")
    for result in results:
        print(f"- {result.get('agent_id')}: {result.get('status')}")
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
    aggregate = write_run_result(run_dir, run_dir.name, results, started_at)
    print(rel_display(run_dir / "summary.md"))
    return 0 if aggregate["status"] == "completed" else 1


def command_cancel(args: argparse.Namespace) -> int:
    print(
        "Background process management is not implemented in the MVP; no recorded process IDs were cancelled.",
        file=sys.stderr,
    )
    return 2


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
