//! Concurrency: max_concurrency true parallel wall-clock.

#![cfg(feature = "dev-harness")]
#![allow(clippy::unwrap_used, clippy::expect_used)]

use std::fs;
use std::process::Command;
use std::time::Instant;

use assert_cmd::cargo::CommandCargoExt;
use tempfile::tempdir;

#[test]
fn max_concurrency_two_agents_parallel_wall_clock() {
    let dir = tempdir().unwrap();
    fs::write(dir.path().join("README.md"), "x").unwrap();
    let tasks = dir.path().join("tasks.json");
    fs::write(
        &tasks,
        r#"{
          "schema_version": 3,
          "run_id": "par-run",
          "max_concurrency": 2,
          "agents": [
            {
              "id": "a1",
              "goal": "sleep",
              "harness": { "kind": "fake", "sleep_ms": 600, "response_summary": "a1" },
              "mode": "read_only",
              "capabilities": ["repo_read"],
              "limits": {
                "timeout_ms": 30000,
                "idle_timeout_ms": 30000,
                "max_workspace_files": 1000,
                "max_workspace_bytes": 10485760
              }
            },
            {
              "id": "a2",
              "goal": "sleep",
              "harness": { "kind": "fake", "sleep_ms": 600, "response_summary": "a2" },
              "mode": "read_only",
              "capabilities": ["repo_read"],
              "limits": {
                "timeout_ms": 30000,
                "idle_timeout_ms": 30000,
                "max_workspace_files": 1000,
                "max_workspace_bytes": 10485760
              }
            }
          ]
        }"#,
    )
    .unwrap();

    let start = Instant::now();
    let status = Command::cargo_bin("subagent-broker")
        .unwrap()
        .arg("run")
        .arg(&tasks)
        .arg("--cwd")
        .arg(dir.path())
        .status()
        .unwrap();
    let elapsed = start.elapsed();
    assert!(status.success(), "run failed: {status}");
    // Sequential would be ~1.2s+; parallel should finish under ~1.1s with margin.
    assert!(
        elapsed.as_millis() < 1100,
        "expected parallel run <1100ms, got {:?}",
        elapsed
    );
}
