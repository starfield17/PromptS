#!/usr/bin/env python3
"""Build harness CLI invocations and normalize their final output."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


class HarnessAdapterError(Exception):
    pass


@dataclass(frozen=True)
class HarnessInvocation:
    argv: tuple[str, ...]
    logged_argv: tuple[str, ...]


@dataclass(frozen=True)
class DecodedOutput:
    text: str
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class HarnessSpec:
    name: str
    builder: Callable[[dict[str, Any], dict[str, str]], list[str]]
    decoder: Callable[[str], DecodedOutput]
    event_normalizer: Callable[[dict[str, Any]], list[dict[str, Any]]] | None = None


def _append_common_args(
    argv: list[str],
    agent: dict[str, Any],
    *,
    model_flag: str = "--model",
    agent_flag: str | None = "--agent",
) -> None:
    model = agent.get("model")
    if model:
        argv.extend([model_flag, str(model)])
    agent_name = agent.get("agent")
    if agent_flag and agent_name:
        argv.extend([agent_flag, str(agent_name)])


def _build_opencode(agent: dict[str, Any], values: dict[str, str]) -> list[str]:
    argv = ["opencode", "run"]
    _append_common_args(argv, agent)
    if agent["approval_policy"] == "unattended":
        argv.append("--auto")
    argv.append(values["prompt"])
    return argv


def _build_claude(agent: dict[str, Any], values: dict[str, str]) -> list[str]:
    argv = ["claude", "--output-format", "stream-json", "--verbose"]
    _append_common_args(argv, agent)
    if agent["approval_policy"] == "bounded":
        default_tools = ["Read", "Glob", "Grep"]
        if agent["mode"] == "patch_only":
            default_tools.extend(["Edit", "Write"])
        allowed_tools = list(dict.fromkeys([*default_tools, *agent.get("allowed_tools", [])]))
        tool_names = list(dict.fromkeys(tool.split("(", 1)[0] for tool in allowed_tools))
        argv.extend(
            [
                "--permission-mode",
                "dontAsk",
                "--tools",
                ",".join(tool_names),
                "--allowedTools",
                ",".join(allowed_tools),
            ]
        )
    elif agent["approval_policy"] == "unattended":
        argv.append("--dangerously-skip-permissions")
    if not agent.get("session_persistence"):
        argv.append("--no-session-persistence")
    argv.extend(["-p", values["prompt"]])
    return argv


def _build_codex(agent: dict[str, Any], values: dict[str, str]) -> list[str]:
    argv = ["codex", "exec", "--json", "--ephemeral"]
    _append_common_args(argv, agent, agent_flag=None)
    if agent.get("dangerously_bypass_approvals_and_sandbox"):
        argv.append("--dangerously-bypass-approvals-and-sandbox")
    else:
        sandbox = "read-only" if agent["mode"] == "read_only" else "workspace-write"
        argv.extend(["--sandbox", sandbox])
    argv.append(values["prompt"])
    return argv


def _build_grok(agent: dict[str, Any], values: dict[str, str]) -> list[str]:
    sandbox = "read-only" if agent["mode"] == "read_only" else "workspace"
    argv = [
        "grok",
        "--output-format",
        "streaming-json",
        "--no-plan",
        "--no-subagents",
        "--no-leader",
        "--no-ask-user",
        "--no-memory",
        "--no-auto-update",
        "--sandbox",
        sandbox,
        "--cwd",
        values["cwd"],
    ]
    _append_common_args(argv, agent)
    if agent["approval_policy"] == "unattended":
        argv.append("--always-approve")
    argv.extend(["--prompt-file", values["prompt_file"]])
    return argv


def _decode_plain(stdout: str) -> DecodedOutput:
    return DecodedOutput(text=stdout)


def _message_content(event: dict[str, Any]) -> list[dict[str, Any]]:
    message = event.get("message")
    if not isinstance(message, dict):
        return []
    content = message.get("content")
    if not isinstance(content, list):
        return []
    return [item for item in content if isinstance(item, dict)]


def _decode_claude_stream_json(stdout: str) -> DecodedOutput:
    assistant_text: list[str] = []
    errors: list[str] = []
    metadata: dict[str, Any] = {}
    result_text: str | None = None
    result_seen = False
    for line_number, line in enumerate(stdout.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            return DecodedOutput(
                text=result_text or "".join(assistant_text),
                error=f"claude-code emitted invalid stream JSON on line {line_number}: {exc.msg}",
                metadata=metadata,
            )
        if not isinstance(event, dict):
            continue
        event_type = event.get("type")
        if event_type == "system" and event.get("subtype") == "init":
            if isinstance(event.get("session_id"), str):
                metadata["session_id"] = event["session_id"]
        elif event_type == "assistant":
            for block in _message_content(event):
                if block.get("type") == "text" and isinstance(block.get("text"), str):
                    assistant_text.append(block["text"])
        elif event_type == "result":
            result_seen = True
            if isinstance(event.get("result"), str):
                result_text = event["result"]
            for key in (
                "session_id",
                "duration_ms",
                "duration_api_ms",
                "num_turns",
                "total_cost_usd",
            ):
                if key in event:
                    metadata[key] = event[key]
            permission_denials = event.get("permission_denials")
            if isinstance(permission_denials, list) and permission_denials:
                safe_denials = []
                for denial in permission_denials:
                    if not isinstance(denial, dict):
                        continue
                    safe_denial = {
                        key: denial[key]
                        for key in ("tool_name", "tool_use_id")
                        if isinstance(denial.get(key), str)
                    }
                    if safe_denial:
                        safe_denials.append(safe_denial)
                if safe_denials:
                    metadata["permission_denials"] = safe_denials
                    names = sorted(
                        {
                            str(denial.get("tool_name"))
                            for denial in safe_denials
                            if denial.get("tool_name")
                        }
                    )
                    errors.append(
                        "claude-code reported denied tools: " + ", ".join(names)
                    )
            if event.get("is_error") is True or event.get("subtype") not in {None, "success"}:
                errors.append(_event_error(event))

    text = result_text if result_text is not None else "".join(assistant_text)
    if not result_seen:
        errors.append("claude-code stream did not contain a result event")
    if not text:
        errors.append("claude-code stream did not contain response text")
    return DecodedOutput(
        text=text,
        error="; ".join(dict.fromkeys(errors)) if errors else None,
        metadata=metadata,
    )


def _normalize_claude_event(event: dict[str, Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    event_type = event.get("type")
    if event_type == "assistant":
        for block in _message_content(event):
            if block.get("type") == "tool_use" and isinstance(block.get("name"), str):
                payload: dict[str, Any] = {
                    "event": "tool_started",
                    "tool_name": block["name"],
                }
                if isinstance(block.get("id"), str):
                    payload["tool_id"] = block["id"]
                normalized.append(payload)
    elif event_type == "user":
        for block in _message_content(event):
            if block.get("type") == "tool_result":
                payload = {
                    "event": "tool_finished",
                    "is_error": block.get("is_error") is True,
                }
                if isinstance(block.get("tool_use_id"), str):
                    payload["tool_id"] = block["tool_use_id"]
                normalized.append(payload)
    elif event_type == "result":
        normalized.append(
            {
                "event": "harness_result",
                "is_error": event.get("is_error") is True,
                "subtype": str(event.get("subtype") or ""),
            }
        )
    return normalized


def _event_error(event: dict[str, Any]) -> str:
    for key in ("message", "error", "detail", "data", "result"):
        value = event.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            nested = value.get("message")
            if isinstance(nested, str) and nested.strip():
                return nested.strip()
    return json.dumps(event, sort_keys=True)


def _decode_codex_jsonl(stdout: str) -> DecodedOutput:
    messages: list[str] = []
    errors: list[str] = []
    metadata: dict[str, Any] = {}
    for line_number, line in enumerate(stdout.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            return DecodedOutput(
                text="\n".join(messages),
                error=f"codex-cli emitted invalid JSONL on line {line_number}: {exc.msg}",
            )
        if not isinstance(event, dict):
            continue
        event_type = event.get("type")
        if event_type == "thread.started" and isinstance(event.get("thread_id"), str):
            metadata["thread_id"] = event["thread_id"]
        elif event_type == "item.completed":
            item = event.get("item")
            if isinstance(item, dict) and item.get("type") == "agent_message":
                text = item.get("text")
                if isinstance(text, str):
                    messages.append(text)
        elif event_type in {"error", "turn.failed"}:
            errors.append(_event_error(event))

    if errors:
        return DecodedOutput(text="\n".join(messages), error="; ".join(errors), metadata=metadata)
    if not messages:
        return DecodedOutput(
            text="",
            error="codex-cli JSONL did not contain a completed agent message",
            metadata=metadata,
        )
    return DecodedOutput(text="\n".join(messages), metadata=metadata)


def _decode_grok_streaming_json(stdout: str) -> DecodedOutput:
    chunks: list[str] = []
    errors: list[str] = []
    metadata: dict[str, Any] = {}
    end_seen = False
    for line_number, line in enumerate(stdout.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            return DecodedOutput(
                text="".join(chunks),
                error=f"grok emitted invalid streaming JSON on line {line_number}: {exc.msg}",
            )
        if not isinstance(event, dict):
            continue
        event_type = event.get("type")
        if event_type == "text":
            data = event.get("data")
            if isinstance(data, str):
                chunks.append(data)
        elif event_type == "error":
            errors.append(_event_error(event))
        elif event_type == "max_turns_reached":
            errors.append("grok reached its maximum turn limit")
        elif event_type == "end":
            end_seen = True
            for key in ("stopReason", "sessionId", "requestId"):
                if key in event:
                    metadata[key] = event[key]

    text = "".join(chunks)
    stop_reason = str(metadata.get("stopReason") or "").lower().replace("_", "")
    if stop_reason in {
        "error",
        "refusal",
        "cancelled",
        "canceled",
        "maxturnsreached",
        "maxturnrequests",
        "maxtokens",
    }:
        errors.append(f"grok ended with stop reason: {metadata.get('stopReason')}")
    if not end_seen:
        errors.append("grok streaming output did not contain an end event")
    if not text:
        errors.append("grok streaming output did not contain response text")
    if errors:
        return DecodedOutput(text=text, error="; ".join(errors), metadata=metadata)
    return DecodedOutput(text=text, metadata=metadata)


HARNESS_SPECS: dict[str, HarnessSpec] = {
    "opencode": HarnessSpec("opencode", _build_opencode, _decode_plain),
    "claude-code": HarnessSpec(
        "claude-code",
        _build_claude,
        _decode_claude_stream_json,
        _normalize_claude_event,
    ),
    "codex-cli": HarnessSpec("codex-cli", _build_codex, _decode_codex_jsonl),
    "grok-build": HarnessSpec("grok-build", _build_grok, _decode_grok_streaming_json),
}


def supported_harnesses() -> frozenset[str]:
    return frozenset({"fake", *HARNESS_SPECS})


def format_custom_argv(template: list[Any], values: dict[str, str]) -> list[str]:
    argv: list[str] = []
    index = 0
    while index < len(template):
        token = str(template[index])
        if token.startswith("-") and index + 1 < len(template):
            next_token = str(template[index + 1])
            if (
                next_token.startswith("{")
                and next_token.endswith("}")
                and values.get(next_token[1:-1], "") == ""
            ):
                index += 2
                continue
        for key, value in values.items():
            token = token.replace("{" + key + "}", value)
        if token:
            argv.append(token)
        index += 1
    return argv


def _redact_prompt(argv: list[str], prompt: str, goal: str) -> tuple[str, ...]:
    redacted: list[str] = []
    for token in argv:
        if prompt:
            token = token.replace(prompt, "<prompt>")
        if goal:
            token = token.replace(goal, "<goal>")
        redacted.append(token)
    return tuple(redacted)


def build_harness_invocation(
    agent: dict[str, Any],
    prompt: str,
    prompt_file: Path,
    cwd: Path,
    run_dir: Path,
    agent_dir: Path,
    config: dict[str, Any],
) -> HarnessInvocation:
    harness = agent["harness"]
    spec = HARNESS_SPECS.get(harness)
    if spec is None:
        raise HarnessAdapterError(f"No external adapter for harness: {harness}")

    values = {
        "model": str(agent.get("model") or ""),
        "agent": str(agent.get("agent") or ""),
        "goal": str(agent["goal"]),
        "prompt": prompt,
        "prompt_file": str(prompt_file.resolve()),
        "cwd": str(cwd.resolve()),
        "run_dir": str(run_dir.resolve()),
        "agent_dir": str(agent_dir.resolve()),
        "mode": str(agent["mode"]),
        "approval_policy": str(agent["approval_policy"]),
    }
    argv: list[str] | None = None
    harnesses = config.get("harnesses", {})
    if isinstance(harnesses, dict):
        entry = harnesses.get(harness)
        if isinstance(entry, dict) and isinstance(entry.get("argv"), list):
            argv = format_custom_argv(entry["argv"], values)
    if argv is None:
        argv = spec.builder(agent, values)
    if not argv:
        raise HarnessAdapterError(f"Harness argv is empty: {harness}")
    return HarnessInvocation(tuple(argv), _redact_prompt(argv, prompt, str(agent["goal"])))


def decode_harness_output(harness: str, stdout: str) -> DecodedOutput:
    spec = HARNESS_SPECS.get(harness)
    if spec is None:
        raise HarnessAdapterError(f"No output decoder for harness: {harness}")
    return spec.decoder(stdout)


def normalize_harness_stream_line(harness: str, line: str) -> list[dict[str, Any]]:
    spec = HARNESS_SPECS.get(harness)
    if spec is None or spec.event_normalizer is None or not line.strip():
        return []
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        return []
    if not isinstance(event, dict):
        return []
    return spec.event_normalizer(event)
