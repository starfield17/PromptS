//! CLI blackbox tests using fake harness.

#![cfg(feature = "dev-harness")]
#![allow(clippy::unwrap_used, clippy::expect_used)]

use std::fs;
use std::path::PathBuf;
use std::process::Command;

use assert_cmd::assert::OutputAssertExt;
use assert_cmd::cargo::CommandCargoExt;
use predicates::prelude::*;
use tempfile::tempdir;

fn broker() -> Command {
    Command::cargo_bin("subagent-broker").expect("binary")
}

#[test]
fn doctor_exits_zero() {
    broker()
        .arg("doctor")
        .assert()
        .success()
        .stdout(predicate::str::contains("subagent-broker V3.1 doctor"));
}

#[test]
fn run_rejects_v2_packet_exit_2() {
    let dir = tempdir().unwrap();
    let tasks = dir.path().join("tasks.json");
    fs::write(&tasks, r#"{"schema_version":2,"run_id":"x","agents":[]}"#).unwrap();
    broker()
        .arg("run")
        .arg(&tasks)
        .arg("--cwd")
        .arg(dir.path())
        .assert()
        .failure()
        .code(2);
}

#[test]
fn fake_run_success_writes_result_and_summary() {
    let dir = tempdir().unwrap();
    fs::write(dir.path().join("README.md"), "hello").unwrap();
    let tasks = dir.path().join("tasks.json");
    fs::write(
        &tasks,
        r#"{
          "schema_version": 3,
          "run_id": "fake-ok",
          "agents": [{
            "id": "worker",
            "goal": "say hi",
            "harness": {
              "kind": "fake",
              "model": "fake-1",
              "response_summary": "hello from fake"
            },
            "mode": "read_only",
            "capabilities": ["repo_read"],
            "limits": {
              "timeout_ms": 10000,
              "idle_timeout_ms": 5000,
              "max_workspace_files": 1000,
              "max_workspace_bytes": 10485760
            }
          }]
        }"#,
    )
    .unwrap();

    broker()
        .arg("run")
        .arg(&tasks)
        .arg("--cwd")
        .arg(dir.path())
        .assert()
        .success();

    let result_path = dir.path().join(".subagents/fake-ok/result.json");
    assert!(result_path.exists(), "missing {}", result_path.display());
    let summary = dir.path().join(".subagents/fake-ok/summary.md");
    assert!(summary.exists());
    let result: serde_json::Value =
        serde_json::from_str(&fs::read_to_string(result_path).unwrap()).unwrap();
    assert_eq!(result["schema_version"], 3);
    assert_eq!(result["outcome"], "success");
    assert_eq!(result["agents"][0]["outcome"], "success");
    assert_eq!(result["agents"][0]["revision"], result["revision"]);
    assert!(result["agents"][0]["patch"].is_null());
    assert!(
        fs::metadata(dir.path().join(".subagents/fake-ok/events.jsonl"))
            .unwrap()
            .len()
            > 0
    );

    broker()
        .arg("run")
        .arg(&tasks)
        .arg("--cwd")
        .arg(dir.path())
        .assert()
        .failure()
        .code(2);
}

#[test]
fn fake_denial_blocks_and_no_patch_file() {
    let dir = tempdir().unwrap();
    fs::write(dir.path().join("README.md"), "hello").unwrap();
    let tasks = dir.path().join("tasks.json");
    fs::write(
        &tasks,
        r#"{
          "schema_version": 3,
          "run_id": "fake-deny",
          "agents": [{
            "id": "worker",
            "goal": "try bash",
            "harness": {
              "kind": "fake",
              "inject_denial": true,
              "response_summary": "claimed success"
            },
            "mode": "read_only",
            "capabilities": ["repo_read"],
            "limits": {
              "timeout_ms": 10000,
              "idle_timeout_ms": 5000,
              "max_workspace_files": 1000,
              "max_workspace_bytes": 10485760
            }
          }]
        }"#,
    )
    .unwrap();

    broker()
        .arg("run")
        .arg(&tasks)
        .arg("--cwd")
        .arg(dir.path())
        .assert()
        .failure()
        .code(1);

    let result_path = dir.path().join(".subagents/fake-deny/result.json");
    let result: serde_json::Value =
        serde_json::from_str(&fs::read_to_string(result_path).unwrap()).unwrap();
    assert_eq!(result["outcome"], "blocked");
    assert_eq!(result["agents"][0]["reason"], "permission_denied");
    let patch = dir.path().join(".subagents/fake-deny/worker/patch.diff");
    assert!(!patch.exists(), "patch must not exist on blocked");
}

#[test]
fn identity_mismatch_fixture_blocks_no_patch() {
    let dir = tempdir().unwrap();
    fs::write(dir.path().join("README.md"), "hello").unwrap();
    let fixture = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("tests/fixtures/streams/identity_mismatch_grok_as_claude.jsonl");
    let tasks = dir.path().join("tasks.json");
    let body = format!(
        r#"{{
          "schema_version": 3,
          "run_id": "id-mm",
          "agents": [{{
            "id": "worker",
            "goal": "review",
            "harness": {{
              "kind": "fake",
              "stream_fixture": "{}"
            }},
            "mode": "read_only",
            "capabilities": ["repo_read"],
            "identity": {{
              "required": true,
              "expected_provider": "anthropic",
              "expected_model_prefix": "claude-"
            }},
            "limits": {{
              "timeout_ms": 10000,
              "idle_timeout_ms": 5000,
              "max_workspace_files": 1000,
              "max_workspace_bytes": 10485760
            }}
          }}]
        }}"#,
        fixture.display()
    );
    fs::write(&tasks, body).unwrap();

    broker()
        .arg("run")
        .arg(&tasks)
        .arg("--cwd")
        .arg(dir.path())
        .assert()
        .failure()
        .code(1);

    let result_path = dir.path().join(".subagents/id-mm/result.json");
    let result: serde_json::Value =
        serde_json::from_str(&fs::read_to_string(result_path).unwrap()).unwrap();
    assert_eq!(result["agents"][0]["outcome"], "blocked");
    assert_eq!(result["agents"][0]["reason"], "provider_mismatch");
    assert!(!dir
        .path()
        .join(".subagents/id-mm/worker/patch.diff")
        .exists());
}
