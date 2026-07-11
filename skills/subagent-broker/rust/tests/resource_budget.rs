//! Resource and verification budget contracts.

#![allow(clippy::unwrap_used, clippy::expect_used)]

use std::fs;
use std::process::Command;

use subagent_broker::persistence::RunDirectory;
use subagent_broker::task::{Mode, RunId, TaskPacket};
use subagent_broker::workspace::{prepare_workspace_with_budget, run_verification};
use tempfile::tempdir;

#[test]
fn task_budget_rejects_agent_count_and_total_goal() {
    let packet = r#"{
      "schema_version": 3,
      "run_id": "budget",
      "resources": {"max_agents": 1, "max_total_goal_bytes": 3},
      "agents": [
        {"id":"a","goal":"one","harness":{"kind":"custom","executable":"/bin/true"},"mode":"read_only","requested_permissions":["repo_read"]},
        {"id":"b","goal":"two","harness":{"kind":"custom","executable":"/bin/true"},"mode":"read_only","requested_permissions":["repo_read"]}
      ]
    }"#;
    assert!(TaskPacket::parse_str(packet).is_err());
}

#[test]
fn workspace_rejects_single_file_budget() {
    let dir = tempdir().unwrap();
    fs::write(dir.path().join("large.txt"), vec![b'x'; 32]).unwrap();
    let err = prepare_workspace_with_budget(
        dir.path(),
        &dir.path().join("workspace"),
        Mode::ReadOnly,
        100,
        1_000_000,
        8,
        1_000_000,
    )
    .unwrap_err();
    assert!(err.to_string().contains("max_file_bytes"), "{err}");
}

#[test]
fn verification_is_argv_only_and_bounded() {
    let dir = tempdir().unwrap();
    let (ok, passed) = run_verification(
        dir.path(),
        &[vec!["/bin/sh".into(), "-c".into(), "exit 0".into()]],
        1000,
        32,
        None,
    )
    .unwrap();
    assert!(passed);
    assert_eq!(ok[0].exit_code, Some(0));

    let (failed, passed) = run_verification(
        dir.path(),
        &[vec![
            "/bin/sh".into(),
            "-c".into(),
            "printf xx; exit 7".into(),
        ]],
        1000,
        1,
        None,
    )
    .unwrap();
    assert!(!passed);
    assert_eq!(failed[0].exit_code, Some(7));
    assert!(failed[0].output_truncated);
}

#[test]
fn event_log_budget_drops_without_exceeding_limit() {
    let dir = tempdir().unwrap();
    let base = dir.path().join("runs");
    let run = RunDirectory::create(&base, &RunId::new("budget-run").unwrap()).unwrap();
    fs::write(run.root.join("events.jsonl"), b"").unwrap();
    assert!(run
        .append_event_with_limit(&serde_json::json!({"event":"one"}), 24)
        .unwrap());
    assert!(!run
        .append_event_with_limit(&serde_json::json!({"event":"this is too large"}), 24)
        .unwrap());
    assert!(fs::metadata(run.root.join("events.jsonl")).unwrap().len() <= 24);
}

#[allow(dead_code)]
fn _git_available() -> bool {
    Command::new("git").arg("--version").status().is_ok()
}
